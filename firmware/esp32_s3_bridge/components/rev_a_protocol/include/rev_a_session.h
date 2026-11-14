#ifndef ISLAM_REV_A_SESSION_H
#define ISLAM_REV_A_SESSION_H

#include "rev_a_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    REV_A_SESSION_INVALID_ARGUMENT = 0,
    REV_A_SESSION_DEVICE_INFO_ACCEPTED,
    REV_A_SESSION_MEASUREMENT_ACCEPTED,
    REV_A_SESSION_WAITING_FOR_DEVICE_INFO,
    REV_A_SESSION_INVALID_DEVICE_INFO,
    REV_A_SESSION_INVALID_MEASUREMENT,
    REV_A_SESSION_UNSUPPORTED_FRAME
} rev_a_session_result_t;

typedef struct {
    bool device_info_valid;
    rev_a_device_info_t device_info;
    uint32_t info_generation;
    uint32_t accepted_measurements;
    uint32_t rejected_measurements_without_info;
} rev_a_session_t;

/*
 * Each accepted measurement carries both untouched raw 16-bit words and a
 * metadata snapshot. interpreted_samples[i] is meaningful only when bit i
 * is set in interpreted_mask. Invalid raw windows are never replaced.
 */
typedef struct {
    rev_a_measurement_t raw;
    uint8_t adc_model_id;
    uint8_t sample_format_id;
    uint8_t adc_resolution_bits;
    uint8_t adc_input_mode_id;
    uint32_t adc_vref_uv;
    uint32_t info_generation;
    uint8_t interpreted_mask;
    int32_t interpreted_samples[REV_A_MAX_SAMPLES];
} rev_a_session_measurement_t;

void rev_a_session_reset(rev_a_session_t *session);

/*
 * Invalidate DEVICE_INFO after UART overflow, reconnect, framing loss or a
 * device reset. Counters are preserved; a fresh DEVICE_INFO is required.
 */
void rev_a_session_invalidate_device_info(rev_a_session_t *session);

/*
 * Consume one CRC-validated frame from rev_a_parser_feed().
 * DEVICE_INFO opens/refreshes the metadata session. MEASUREMENT is rejected
 * until metadata is valid, then copied with raw samples and signed values
 * gated by VALID_MASK and the advertised ADC format.
 */
rev_a_session_result_t rev_a_session_accept_frame(
    rev_a_session_t *session,
    const rev_a_frame_t *frame,
    rev_a_session_measurement_t *measurement_out);

#ifdef __cplusplus
}
#endif

#endif
