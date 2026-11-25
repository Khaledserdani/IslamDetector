#include "sdkconfig.h"
#include "rev_a_http_api.h"

#include <stdio.h>
#include <string.h>

#include "cJSON.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "rev_a_http_api_policy.h"
#include "rev_a_uart_bridge.h"

#define TAG "rev_a_http"
#define CONTROL_BODY_MAX 128u

static httpd_handle_t s_http_server;

static esp_err_t send_json(
    httpd_req_t *request,
    const char *status,
    const char *body) {
    httpd_resp_set_status(request, status);
    httpd_resp_set_type(request, "application/json");
    httpd_resp_set_hdr(request, "Cache-Control", "no-store");
    return httpd_resp_sendstr(request, body);
}

static esp_err_t status_get_handler(httpd_req_t *request) {
    rev_a_uart_bridge_status_t bridge_status = {0};
    rev_a_uart_bridge_get_status(&bridge_status);

    rev_a_http_device_status_t device_status = {0};
    device_status.uart_running = bridge_status.running;
    device_status.device_info_valid =
        bridge_status.running && bridge_status.device_info_valid;
    if (device_status.device_info_valid) {
        device_status.adc_model_id = bridge_status.device_info.adc_model_id;
        device_status.sample_format_id = bridge_status.device_info.sample_format_id;
        device_status.adc_resolution_bits = bridge_status.device_info.adc_resolution_bits;
        device_status.adc_input_mode_id = bridge_status.device_info.adc_input_mode_id;
        device_status.adc_vref_uv = bridge_status.device_info.adc_vref_uv;
    }

    char body[640];
    if (!rev_a_http_build_status_json(&device_status, body, sizeof(body))) {
        return ESP_FAIL;
    }
    return send_json(request, "200 OK", body);
}

static const char *status_phrase(int status_code) {
    if (status_code == 200) {
        return "200 OK";
    }
    if (status_code == 409) {
        return "409 Conflict";
    }
    return "400 Bad Request";
}

static esp_err_t control_post_handler(httpd_req_t *request) {
    char body[CONTROL_BODY_MAX + 1u];
    if (request->content_len == 0u || request->content_len > CONTROL_BODY_MAX) {
        return send_json(request, "400 Bad Request",
            "{\"accepted\":false,\"reason\":\"INVALID_BODY\"}");
    }

    size_t received_total = 0u;
    while (received_total < request->content_len) {
        const int received = httpd_req_recv(
            request,
            body + received_total,
            request->content_len - received_total);
        if (received <= 0) {
            ESP_LOGW(TAG, "Control request body receive failed");
            return ESP_FAIL;
        }
        received_total += (size_t)received;
    }
    body[received_total] = '\0';

    cJSON *root = cJSON_Parse(body);
    if (root == NULL) {
        return send_json(request, "400 Bad Request",
            "{\"accepted\":false,\"reason\":\"INVALID_JSON\"}");
    }

    const cJSON *command_item = cJSON_GetObjectItemCaseSensitive(root, "command");
    if (!cJSON_IsString(command_item) || command_item->valuestring == NULL) {
        cJSON_Delete(root);
        return send_json(request, "400 Bad Request",
            "{\"accepted\":false,\"reason\":\"COMMAND_REQUIRED\"}");
    }

    rev_a_http_command_result_t decision;
    rev_a_http_command_decide(command_item->valuestring, &decision);
    cJSON_Delete(root);

    char response[192];
    const int length = snprintf(
        response,
        sizeof(response),
        "{\"accepted\":%s,\"state\":\"%s\",\"reason\":\"%s\"}",
        decision.accepted ? "true" : "false",
        decision.state,
        decision.reason);
    if (length < 0 || (size_t)length >= sizeof(response)) {
        return ESP_FAIL;
    }

    return send_json(request, status_phrase(decision.http_status), response);
}

esp_err_t rev_a_http_api_start(void) {
    if (s_http_server != NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    const size_t ssid_length = strlen(CONFIG_REV_A_WIFI_SSID);
    const size_t password_length = strlen(CONFIG_REV_A_WIFI_PASSWORD);
    if (ssid_length == 0u || ssid_length > 32u ||
        password_length < 8u || password_length > 63u) {
        ESP_LOGE(TAG, "SoftAP requires SSID 1..32 bytes and WPA2 password 8..63 bytes");
        return ESP_ERR_INVALID_ARG;
    }

    esp_err_t error = nvs_flash_init();
    if (error != ESP_OK) {
        ESP_LOGE(TAG, "NVS initialization failed: %s", esp_err_to_name(error));
        return error;
    }

    error = esp_netif_init();
    if (error != ESP_OK && error != ESP_ERR_INVALID_STATE) {
        return error;
    }

    error = esp_event_loop_create_default();
    if (error != ESP_OK && error != ESP_ERR_INVALID_STATE) {
        return error;
    }

    if (esp_netif_create_default_wifi_ap() == NULL) {
        return ESP_FAIL;
    }

    const wifi_init_config_t wifi_init = WIFI_INIT_CONFIG_DEFAULT();
    error = esp_wifi_init(&wifi_init);
    if (error != ESP_OK) {
        return error;
    }

    error = esp_wifi_set_storage(WIFI_STORAGE_RAM);
    if (error != ESP_OK) {
        return error;
    }

    wifi_config_t access_point = {0};
    memcpy(access_point.ap.ssid, CONFIG_REV_A_WIFI_SSID, ssid_length);
    access_point.ap.ssid_len = (uint8_t)ssid_length;
    memcpy(access_point.ap.password, CONFIG_REV_A_WIFI_PASSWORD, password_length);
    access_point.ap.channel = 1;
    access_point.ap.max_connection = 2;
    access_point.ap.authmode = WIFI_AUTH_WPA2_PSK;
    access_point.ap.pmf_cfg.capable = true;
    access_point.ap.pmf_cfg.required = false;

    error = esp_wifi_set_mode(WIFI_MODE_AP);
    if (error != ESP_OK) {
        return error;
    }
    error = esp_wifi_set_config(WIFI_IF_AP, &access_point);
    if (error != ESP_OK) {
        return error;
    }
    error = esp_wifi_start();
    if (error != ESP_OK) {
        return error;
    }

    httpd_config_t server_config = HTTPD_DEFAULT_CONFIG();
    server_config.max_uri_handlers = 2;
    server_config.stack_size = 4096;
    error = httpd_start(&s_http_server, &server_config);
    if (error != ESP_OK) {
        s_http_server = NULL;
        (void)esp_wifi_stop();
        return error;
    }

    const httpd_uri_t status_uri = {
        .uri = "/status",
        .method = HTTP_GET,
        .handler = status_get_handler,
        .user_ctx = NULL
    };
    const httpd_uri_t control_uri = {
        .uri = "/control",
        .method = HTTP_POST,
        .handler = control_post_handler,
        .user_ctx = NULL
    };

    error = httpd_register_uri_handler(s_http_server, &status_uri);
    if (error == ESP_OK) {
        error = httpd_register_uri_handler(s_http_server, &control_uri);
    }
    if (error != ESP_OK) {
        (void)httpd_stop(s_http_server);
        s_http_server = NULL;
        (void)esp_wifi_stop();
        return error;
    }

    ESP_LOGI(TAG, "WPA2 SoftAP started (SSID=%s, gateway=192.168.4.1)", CONFIG_REV_A_WIFI_SSID);
    ESP_LOGW(TAG, "Measurement values are unavailable; START and CALIBRATE remain blocked");
    return ESP_OK;
}
