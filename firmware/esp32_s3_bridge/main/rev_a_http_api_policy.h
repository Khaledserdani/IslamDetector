#ifndef ISLAM_REV_A_HTTP_API_POLICY_H
#define ISLAM_REV_A_HTTP_API_POLICY_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int http_status;
    bool accepted;
    const char *state;
    const char *reason;
} rev_a_http_command_result_t;

/*
 * Conservative Rev A policy:
 * - STOP is idempotently accepted while the TX path is not implemented.
 * - START remains blocked until an independently verified hardware interlock exists.
 * - CALIBRATE remains blocked until a real ADC measurement path is installed.
 */
void rev_a_http_command_decide(
    const char *command,
    rev_a_http_command_result_t *result_out);

#ifdef __cplusplus
}
#endif

#endif


typedef struct {
    bool uart_running;
    bool device_info_valid;
    uint8_t adc_model_id;
    uint8_t sample_format_id;
    uint8_t adc_resolution_bits;
    uint8_t adc_input_mode_id;
    uint32_t adc_vref_uv;
} rev_a_http_device_status_t;

/* Build a truthful /status snapshot. Measurements and TX remain unavailable
 * until a real ADC producer and independently verified TX interlock exist. */
bool rev_a_http_build_status_json(
    const rev_a_http_device_status_t *device_status,
    char *buffer,
    size_t buffer_capacity);
