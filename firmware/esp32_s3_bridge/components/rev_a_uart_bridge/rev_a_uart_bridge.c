#include "rev_a_uart_bridge.h"
#include <limits.h>
#include <string.h>
#include "driver/uart.h"
#include "esp_log.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#define TAG "rev_a_uart"
#define DEFAULT_BAUD_RATE 921600
#define DEFAULT_RX_BUFFER 4096u
#define DEFAULT_TX_BUFFER 512u
#define DEFAULT_EVENT_QUEUE 16u
#define DEFAULT_MEASUREMENT_QUEUE 8u
#define DEFAULT_TASK_STACK_BYTES 4096u
#define DEFAULT_TASK_PRIORITY 10u
#define DEFAULT_INFO_RETRY_MS 1000u
#define UART_READ_CHUNK 128u
static volatile bool s_initialized;
static volatile bool s_running;
static uart_port_t s_uart_port = UART_NUM_1;
static QueueHandle_t s_event_queue;
static QueueHandle_t s_measurement_queue;
static SemaphoreHandle_t s_tx_mutex;
static TaskHandle_t s_task;
static rev_a_parser_t s_parser;
static rev_a_session_t s_session;
static uint32_t s_info_retry_ms = DEFAULT_INFO_RETRY_MS;
static TickType_t s_last_info_request_tick;
static bool s_info_request_sent;
static portMUX_TYPE s_status_mux = portMUX_INITIALIZER_UNLOCKED;
static rev_a_uart_bridge_status_t s_status;

static void status_set_running(bool value) {
    portENTER_CRITICAL(&s_status_mux); s_status.running = value; portEXIT_CRITICAL(&s_status_mux);
}
static void status_add(uint32_t *field, uint32_t amount) {
    portENTER_CRITICAL(&s_status_mux); *field += amount; portEXIT_CRITICAL(&s_status_mux);
}
static void status_set_parser_counters(void) {
    portENTER_CRITICAL(&s_status_mux);
    s_status.parser_rejections = s_parser.rejected_frames;
    s_status.parser_discarded_bytes = s_parser.discarded_bytes;
    s_status.rejected_measurements_without_info = s_session.rejected_measurements_without_info;
    portEXIT_CRITICAL(&s_status_mux);
}
static void status_set_device_info(const rev_a_device_info_t *info) {
    portENTER_CRITICAL(&s_status_mux);
    if (info != NULL) { s_status.device_info = *info; s_status.device_info_valid = true; }
    else { memset(&s_status.device_info, 0, sizeof(s_status.device_info)); s_status.device_info_valid = false; }
    portEXIT_CRITICAL(&s_status_mux);
}

esp_err_t rev_a_uart_bridge_send_command(uint8_t type, const uint8_t *payload, uint8_t payload_length) {
    if (!s_initialized || !s_running || s_tx_mutex == NULL) return ESP_ERR_INVALID_STATE;
    uint8_t frame[REV_A_MAX_COMMAND_FRAME_SIZE]; size_t frame_length = 0u;
    if (!rev_a_encode_command(type, payload, payload_length, frame, sizeof(frame), &frame_length))
        return ESP_ERR_INVALID_ARG;
    if (xSemaphoreTake(s_tx_mutex, pdMS_TO_TICKS(200)) != pdTRUE) {
        status_add(&s_status.tx_errors, 1u); return ESP_ERR_TIMEOUT;
    }
    esp_err_t result = ESP_OK;
    if (!s_running) result = ESP_ERR_INVALID_STATE;
    else {
        const int written = uart_write_bytes(s_uart_port, (const char *)frame, frame_length);
        result = written == (int)frame_length
            ? uart_wait_tx_done(s_uart_port, pdMS_TO_TICKS(100)) : ESP_FAIL;
    }
    xSemaphoreGive(s_tx_mutex);
    if (result != ESP_OK) status_add(&s_status.tx_errors, 1u);
    else if (type == REV_A_TYPE_GET_INFO) {
        s_last_info_request_tick = xTaskGetTickCount(); s_info_request_sent = true;
        status_add(&s_status.info_requests, 1u);
    }
    return result;
}
static void request_device_info(void) {
    const esp_err_t result = rev_a_uart_bridge_send_command(REV_A_TYPE_GET_INFO, NULL, 0u);
    if (result != ESP_OK) ESP_LOGW(TAG, "GET_INFO send failed: %s", esp_err_to_name(result));
}
static void parser_frame_callback(void *ctx, const rev_a_frame_t *frame) {
    (void)ctx;
    if (frame == NULL) return;
    if (frame->type == REV_A_TYPE_DEVICE_INFO) {
        const rev_a_session_result_t result = rev_a_session_accept_frame(&s_session, frame, NULL);
        if (result == REV_A_SESSION_DEVICE_INFO_ACCEPTED) {
            s_info_request_sent = true;
            status_set_device_info(&s_session.device_info);
            status_add(&s_status.accepted_device_info, 1u);
            ESP_LOGI(TAG, "DEVICE_INFO accepted: ADC=%u format=%u resolution=%u input=%u VREF=%lu uV",
                (unsigned)s_session.device_info.adc_model_id,
                (unsigned)s_session.device_info.sample_format_id,
                (unsigned)s_session.device_info.adc_resolution_bits,
                (unsigned)s_session.device_info.adc_input_mode_id,
                (unsigned long)s_session.device_info.adc_vref_uv);
        }
        return;
    }
    if (frame->type == REV_A_TYPE_MEASUREMENT) {
        rev_a_session_measurement_t item;
        const rev_a_session_result_t result = rev_a_session_accept_frame(&s_session, frame, &item);
        if (result == REV_A_SESSION_MEASUREMENT_ACCEPTED) {
            if (s_measurement_queue == NULL || xQueueSend(s_measurement_queue, &item, 0) != pdTRUE)
                status_add(&s_status.dropped_measurements, 1u);
            else status_add(&s_status.accepted_measurements, 1u);
        }
        status_set_parser_counters();
    }
}
static void process_uart_bytes(const uint8_t *bytes, size_t length) {
    for (size_t i = 0u; i < length; ++i) {
        const uint32_t before = s_parser.rejected_frames;
        (void)rev_a_parser_feed(&s_parser, &bytes[i], 1u, parser_frame_callback, NULL);
        if (s_parser.rejected_frames != before) {
            status_set_parser_counters();
            if (s_session.device_info_valid) {
                rev_a_session_invalidate_device_info(&s_session);
                status_set_device_info(NULL);
                s_info_request_sent = false;
            }
        }
    }
    status_set_parser_counters();
}
static void drain_uart_rx(void) {
    uint8_t buffer[UART_READ_CHUNK];
    for (;;) {
        size_t available = 0u;
        if (uart_get_buffered_data_len(s_uart_port, &available) != ESP_OK || available == 0u) break;
        const size_t wanted = available > sizeof(buffer) ? sizeof(buffer) : available;
        const int received = uart_read_bytes(s_uart_port, buffer, wanted, pdMS_TO_TICKS(20));
        if (received <= 0) break;
        status_add(&s_status.rx_bytes, (uint32_t)received);
        process_uart_bytes(buffer, (size_t)received);
    }
}
static void recover_uart_stream(uart_event_type_t reason) {
    switch (reason) {
        case UART_FIFO_OVF: status_add(&s_status.uart_fifo_overflows, 1u); break;
        case UART_BUFFER_FULL: status_add(&s_status.uart_buffer_full_events, 1u); break;
        case UART_FRAME_ERR: status_add(&s_status.uart_frame_errors, 1u); break;
        case UART_PARITY_ERR: status_add(&s_status.uart_parity_errors, 1u); break;
        case UART_BREAK: status_add(&s_status.uart_break_events, 1u); break;
        default: break;
    }
    (void)uart_flush_input(s_uart_port);
    if (s_event_queue != NULL) (void)xQueueReset(s_event_queue);
    rev_a_parser_init(&s_parser);
    rev_a_session_invalidate_device_info(&s_session);
    status_set_device_info(NULL); status_set_parser_counters();
    s_info_request_sent = false; s_last_info_request_tick = 0;
    ESP_LOGW(TAG, "UART stream reset after event %d; DEVICE_INFO required again", (int)reason);
}
static void rev_a_uart_task(void *arg) {
    (void)arg;
    const TickType_t t = pdMS_TO_TICKS(s_info_retry_ms == 0u ? DEFAULT_INFO_RETRY_MS : s_info_retry_ms);
    const TickType_t retry = t == 0u ? 1u : t;
    while (s_running) {
        uart_event_t event;
        if (xQueueReceive(s_event_queue, &event, pdMS_TO_TICKS(100)) == pdTRUE) {
            switch (event.type) {
                case UART_DATA: drain_uart_rx(); break;
                case UART_FIFO_OVF:
                case UART_BUFFER_FULL:
                case UART_FRAME_ERR:
                case UART_PARITY_ERR:
                case UART_BREAK: recover_uart_stream(event.type); break;
                default: break;
            }
        }
        if (s_running && !s_session.device_info_valid) {
            const TickType_t now = xTaskGetTickCount();
            if (!s_info_request_sent || (TickType_t)(now - s_last_info_request_tick) >= retry)
                request_device_info();
        }
    }
    vTaskDelete(NULL);
}
static void release_resources(bool installed) {
    if (s_task != NULL) { vTaskDelete(s_task); s_task = NULL; }
    if (installed) (void)uart_driver_delete(s_uart_port);
    if (s_measurement_queue != NULL) { vQueueDelete(s_measurement_queue); s_measurement_queue = NULL; }
    if (s_tx_mutex != NULL) { vSemaphoreDelete(s_tx_mutex); s_tx_mutex = NULL; }
    s_event_queue = NULL; s_initialized = false; s_running = false; status_set_running(false);
}
esp_err_t rev_a_uart_bridge_start(const rev_a_uart_bridge_config_t *cfg) {
    if (cfg == NULL || s_initialized) return ESP_ERR_INVALID_ARG;
    if (cfg->uart_port <= UART_NUM_0 || cfg->uart_port >= UART_NUM_MAX ||
        cfg->tx_gpio_num < 0 || cfg->rx_gpio_num < 0 || cfg->tx_gpio_num == cfg->rx_gpio_num)
        return ESP_ERR_INVALID_ARG;
    const int baud = cfg->baud_rate == 0 ? DEFAULT_BAUD_RATE : cfg->baud_rate;
    const size_t rx = cfg->rx_buffer_size == 0u ? DEFAULT_RX_BUFFER : cfg->rx_buffer_size;
    const size_t tx = cfg->tx_buffer_size == 0u ? DEFAULT_TX_BUFFER : cfg->tx_buffer_size;
    const size_t events = cfg->event_queue_length == 0u ? DEFAULT_EVENT_QUEUE : cfg->event_queue_length;
    const size_t measurements = cfg->measurement_queue_length == 0u ? DEFAULT_MEASUREMENT_QUEUE : cfg->measurement_queue_length;
    const uint32_t stack = cfg->task_stack_size_bytes == 0u ? DEFAULT_TASK_STACK_BYTES : cfg->task_stack_size_bytes;
    const UBaseType_t priority = cfg->task_priority == 0u ? DEFAULT_TASK_PRIORITY : cfg->task_priority;
    if (baud < 9600 || baud > 2000000 || rx < 256u || rx > (size_t)INT_MAX ||
        tx < 256u || tx > (size_t)INT_MAX || events < 4u || events > 128u ||
        measurements == 0u || measurements > 64u || stack < 2048u || stack > 16384u)
        return ESP_ERR_INVALID_ARG;
    s_uart_port = cfg->uart_port;
    s_info_retry_ms = cfg->device_info_retry_ms == 0u ? DEFAULT_INFO_RETRY_MS : cfg->device_info_retry_ms;
    s_last_info_request_tick = 0; s_info_request_sent = false;
    rev_a_parser_init(&s_parser); rev_a_session_reset(&s_session);
    portENTER_CRITICAL(&s_status_mux); memset(&s_status, 0, sizeof(s_status)); portEXIT_CRITICAL(&s_status_mux);
    s_measurement_queue = xQueueCreate((UBaseType_t)measurements, sizeof(rev_a_session_measurement_t));
    s_tx_mutex = xSemaphoreCreateMutex();
    if (s_measurement_queue == NULL || s_tx_mutex == NULL) { release_resources(false); return ESP_ERR_NO_MEM; }
    const uart_config_t uart_cfg = {
        .baud_rate = baud, .data_bits = UART_DATA_8_BITS, .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1, .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .rx_flow_ctrl_thresh = 0, .source_clk = UART_SCLK_DEFAULT,
    };
    esp_err_t err = uart_param_config(s_uart_port, &uart_cfg);
    if (err != ESP_OK) { release_resources(false); return err; }
    err = uart_driver_install(s_uart_port, (int)rx, (int)tx, (int)events, &s_event_queue, 0);
    if (err != ESP_OK) { release_resources(false); return err; }
    err = uart_set_pin(s_uart_port, cfg->tx_gpio_num, cfg->rx_gpio_num,
                       UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (err != ESP_OK) { release_resources(true); return err; }
    (void)uart_flush_input(s_uart_port);
    s_initialized = true; s_running = true; status_set_running(true);
    if (xTaskCreate(rev_a_uart_task, "rev_a_uart", stack, NULL, priority, &s_task) != pdPASS) {
        release_resources(true); return ESP_ERR_NO_MEM;
    }
    ESP_LOGI(TAG, "UART bridge started: UART%d TX GPIO%d RX GPIO%d baud=%d; no GPIO defaults assumed",
             (int)s_uart_port, cfg->tx_gpio_num, cfg->rx_gpio_num, baud);
    const esp_err_t hello = rev_a_uart_bridge_send_command(REV_A_TYPE_HELLO, NULL, 0u);
    if (hello != ESP_OK) ESP_LOGW(TAG, "HELLO send failed: %s", esp_err_to_name(hello));
    request_device_info();
    return ESP_OK;
}
esp_err_t rev_a_uart_bridge_stop(void) {
    if (!s_initialized) return ESP_ERR_INVALID_STATE;
    if (s_tx_mutex != NULL && xSemaphoreTake(s_tx_mutex, pdMS_TO_TICKS(200)) == pdTRUE) {
        s_running = false; xSemaphoreGive(s_tx_mutex);
    } else s_running = false;
    status_set_running(false);
    if (s_task != NULL) { vTaskDelete(s_task); s_task = NULL; }
    const esp_err_t err = uart_driver_delete(s_uart_port);
    s_event_queue = NULL;
    if (s_measurement_queue != NULL) { vQueueDelete(s_measurement_queue); s_measurement_queue = NULL; }
    if (s_tx_mutex != NULL) { vSemaphoreDelete(s_tx_mutex); s_tx_mutex = NULL; }
    s_initialized = false;
    return err;
}
QueueHandle_t rev_a_uart_bridge_measurement_queue(void) { return s_measurement_queue; }
void rev_a_uart_bridge_get_status(rev_a_uart_bridge_status_t *out) {
    if (out == NULL) return;
    portENTER_CRITICAL(&s_status_mux); *out = s_status; portEXIT_CRITICAL(&s_status_mux);
}
