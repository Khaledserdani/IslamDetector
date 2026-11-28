#include "rev_a_http_api_policy.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    rev_a_http_command_result_t result;

    rev_a_http_command_decide("stop", &result);
    assert(result.http_status == 200);
    assert(result.accepted);
    assert(strcmp(result.state, "idle") == 0);
    assert(strcmp(result.reason, "SAFE_IDLE_NO_TX_PATH") == 0);

    rev_a_http_command_decide("start", &result);
    assert(result.http_status == 409);
    assert(!result.accepted);
    assert(strcmp(result.reason, "TX_INTERLOCK_NOT_IMPLEMENTED") == 0);

    rev_a_http_command_decide("calibrate", &result);
    assert(result.http_status == 409);
    assert(!result.accepted);
    assert(strcmp(result.reason, "ADC_NOT_INSTALLED") == 0);

    rev_a_http_command_decide("unknown", &result);
    assert(result.http_status == 400);
    assert(!result.accepted);

    rev_a_http_command_decide(NULL, &result);
    assert(result.http_status == 400);
    assert(!result.accepted);


    char status_json[768];
    rev_a_http_device_status_t device_status = {0};

    assert(!rev_a_http_build_status_json(NULL, NULL, sizeof(status_json)));
    assert(!rev_a_http_build_status_json(NULL, status_json, 0u));
    assert(rev_a_http_build_status_json(NULL, status_json, sizeof(status_json)));
    assert(strstr(status_json, "\"uart_running\":false") != NULL);
    assert(strstr(status_json, "\"device_info_valid\":false") != NULL);
    assert(strstr(status_json, "\"adc_present\":false") != NULL);
    assert(strstr(status_json, "\"measurement_available\":false") != NULL);
    assert(strstr(status_json, "\"tx_armed\":false") != NULL);
    assert(strstr(status_json, "\"availability_reason\":\"UART_DISABLED_OR_STOPPED\"") != NULL);

    device_status.uart_running = true;
    device_status.device_info_valid = true;
    assert(rev_a_http_build_status_json(&device_status, status_json, sizeof(status_json)));
    assert(strstr(status_json, "\"uart_running\":true") != NULL);
    assert(strstr(status_json, "\"device_info_valid\":true") != NULL);
    assert(strstr(status_json, "\"adc_present\":false") != NULL);
    assert(strstr(status_json, "\"availability_reason\":\"ADC_NOT_INSTALLED\"") != NULL);

    device_status.adc_model_id = 1u;
    device_status.sample_format_id = 1u;
    device_status.adc_resolution_bits = 16u;
    device_status.adc_input_mode_id = 1u;
    device_status.adc_vref_uv = 4096000u;
    assert(rev_a_http_build_status_json(&device_status, status_json, sizeof(status_json)));
    assert(strstr(status_json, "\"adc_present\":true") != NULL);
    assert(strstr(status_json, "\"adc_model_id\":1") != NULL);
    assert(strstr(status_json, "\"adc_vref_uv\":4096000") != NULL);
    assert(strstr(status_json, "\"measurement_available\":false") != NULL);
    assert(strstr(status_json, "\"availability_reason\":\"MEASUREMENT_PIPELINE_NOT_IMPLEMENTED\"") != NULL);

    char tiny_buffer[8];
    assert(!rev_a_http_build_status_json(&device_status, tiny_buffer, sizeof(tiny_buffer)));

    return 0;
}
