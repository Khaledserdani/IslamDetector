#include "rev_a_session.h"

#include <string.h>

void rev_a_session_reset(rev_a_session_t *session) {
    if (session != NULL) {
        memset(session, 0, sizeof(*session));
    }
}

void rev_a_session_invalidate_device_info(rev_a_session_t *session) {
    if (session == NULL) {
        return;
    }

    session->device_info_valid = false;
    memset(&session->device_info, 0, sizeof(session->device_info));
    ++session->info_generation;
}

static bool measurement_shape_valid(const rev_a_measurement_t *measurement) {
    if (measurement == NULL
        || measurement->sample_count == 0u
        || measurement->sample_count > REV_A_MAX_SAMPLES
        || measurement->pulse_rate_hz == 0u) {
        return false;
    }

    const uint16_t allowed_mask =
        (uint16_t)((1u << measurement->sample_count) - 1u);
    if (((uint16_t)measurement->valid_mask & (uint16_t)~allowed_mask) != 0u) {
        return false;
    }
    if ((measurement->flags & REV_A_FLAG_SWEEP_COMPLETE) != 0u
        && measurement->sample_count != REV_A_MAX_SAMPLES) {
        return false;
    }
    return true;
}

rev_a_session_result_t rev_a_session_accept_frame(
    rev_a_session_t *session,
    const rev_a_frame_t *frame,
    rev_a_session_measurement_t *measurement_out) {
    if (session == NULL || frame == NULL) {
        return REV_A_SESSION_INVALID_ARGUMENT;
    }

    if (frame->type == REV_A_TYPE_DEVICE_INFO) {
        if (!rev_a_device_info_valid(&frame->value.device_info)) {
            rev_a_session_invalidate_device_info(session);
            return REV_A_SESSION_INVALID_DEVICE_INFO;
        }

        session->device_info = frame->value.device_info;
        session->device_info_valid = true;
        ++session->info_generation;
        return REV_A_SESSION_DEVICE_INFO_ACCEPTED;
    }

    if (frame->type != REV_A_TYPE_MEASUREMENT) {
        return REV_A_SESSION_UNSUPPORTED_FRAME;
    }

    if (!session->device_info_valid) {
        ++session->rejected_measurements_without_info;
        return REV_A_SESSION_WAITING_FOR_DEVICE_INFO;
    }
    if (measurement_out == NULL) {
        return REV_A_SESSION_INVALID_ARGUMENT;
    }

    const rev_a_measurement_t *raw = &frame->value.measurement;
    if (!measurement_shape_valid(raw)) {
        return REV_A_SESSION_INVALID_MEASUREMENT;
    }

    rev_a_session_measurement_t decoded;
    memset(&decoded, 0, sizeof(decoded));
    decoded.raw = *raw;
    decoded.adc_model_id = session->device_info.adc_model_id;
    decoded.sample_format_id = session->device_info.sample_format_id;
    decoded.adc_resolution_bits = session->device_info.adc_resolution_bits;
    decoded.adc_input_mode_id = session->device_info.adc_input_mode_id;
    decoded.adc_vref_uv = session->device_info.adc_vref_uv;
    decoded.info_generation = session->info_generation;
    decoded.interpreted_mask = raw->valid_mask;

    for (uint8_t i = 0u; i < raw->sample_count; ++i) {
        if ((raw->valid_mask & (uint8_t)(1u << i)) == 0u) {
            continue;
        }
        if (!rev_a_interpret_sample(
                raw->samples[i],
                session->device_info.sample_format_id,
                session->device_info.adc_resolution_bits,
                &decoded.interpreted_samples[i])) {
            return REV_A_SESSION_INVALID_MEASUREMENT;
        }
    }

    *measurement_out = decoded;
    ++session->accepted_measurements;
    return REV_A_SESSION_MEASUREMENT_ACCEPTED;
}
