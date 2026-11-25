#include "rev_a_http_api_policy.h"

#include <string.h>
#include <stdio.h>

void rev_a_http_command_decide(
    const char *command,
    rev_a_http_command_result_t *result_out) {
    if (result_out == NULL) {
        return;
    }

    result_out->http_status = 400;
    result_out->accepted = false;
    result_out->state = "idle";
    result_out->reason = "UNKNOWN_COMMAND";

    if (command == NULL) {
        return;
    }

    if (strcmp(command, "stop") == 0) {
        result_out->http_status = 200;
        result_out->accepted = true;
        result_out->reason = "SAFE_IDLE_NO_TX_PATH";
    } else if (strcmp(command, "start") == 0) {
        result_out->http_status = 409;
        result_out->reason = "TX_INTERLOCK_NOT_IMPLEMENTED";
    } else if (strcmp(command, "calibrate") == 0) {
        result_out->http_status = 409;
        result_out->reason = "ADC_NOT_INSTALLED";
    }
}


bool rev_a_http_build_status_json(
    const rev_a_http_device_status_t *device_status,
    char *buffer,
    size_t buffer_capacity) {
    if (buffer == NULL || buffer_capacity == 0u) {
        return false;
    }

    const bool uart_running = device_status != NULL && device_status->uart_running;
    const bool device_info_valid =
        uart_running && device_status != NULL && device_status->device_info_valid;
    const uint8_t adc_model_id =
        device_info_valid ? device_status->adc_model_id : 0u;
    const uint8_t sample_format_id =
        device_info_valid ? device_status->sample_format_id : 0u;
    const uint8_t adc_resolution_bits =
        device_info_valid ? device_status->adc_resolution_bits : 0u;
    const uint8_t adc_input_mode_id =
        device_info_valid ? device_status->adc_input_mode_id : 0u;
    const uint32_t adc_vref_uv =
        device_info_valid ? device_status->adc_vref_uv : 0u;
    const bool adc_present = device_info_valid && adc_model_id != 0u;

    const char *availability_reason = !uart_running
        ? "UART_DISABLED_OR_STOPPED"
        : (!device_info_valid
            ? "WAITING_FOR_DEVICE_INFO"
            : (!adc_present
                ? "ADC_NOT_INSTALLED"
                : "MEASUREMENT_PIPELINE_NOT_IMPLEMENTED"));

    const int written = snprintf(
        buffer,
        buffer_capacity,
        "{\"device\":\"Islam Detector\","
        "\"state\":\"idle\","
        "\"signal\":null,"
        "\"confidence\":null,"
        "\"depth_cm\":null,"
        "\"calibrated\":false,"
        "\"calibration_percent\":null,"
        "\"tx_armed\":false,"
        "\"measurement_available\":false,"
        "\"adc_present\":%s,"
        "\"adc_model_id\":%u,"
        "\"sample_format_id\":%u,"
        "\"adc_resolution_bits\":%u,"
        "\"adc_input_mode_id\":%u,"
        "\"adc_vref_uv\":%lu,"
        "\"device_info_valid\":%s,"
        "\"uart_running\":%s,"
        "\"measurement_source\":\"none\","
        "\"availability_reason\":\"%s\"}",
        adc_present ? "true" : "false",
        (unsigned)adc_model_id,
        (unsigned)sample_format_id,
        (unsigned)adc_resolution_bits,
        (unsigned)adc_input_mode_id,
        (unsigned long)adc_vref_uv,
        device_info_valid ? "true" : "false",
        uart_running ? "true" : "false",
        availability_reason);
    return written >= 0 && (size_t)written < buffer_capacity;
}
