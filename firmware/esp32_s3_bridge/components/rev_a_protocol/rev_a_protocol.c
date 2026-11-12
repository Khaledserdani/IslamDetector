#include "rev_a_protocol.h"

#include <string.h>

#define MEASUREMENT_FIXED_BODY_LENGTH 29u
#define MEASUREMENT_MIN_BODY_LENGTH   (MEASUREMENT_FIXED_BODY_LENGTH + 2u)
#define MEASUREMENT_MAX_BODY_LENGTH   (MEASUREMENT_FIXED_BODY_LENGTH + 2u * REV_A_MAX_SAMPLES)
#define DEVICE_INFO_BODY_LENGTH       21u
#define DEVICE_INFO_PAYLOAD_LENGTH    17u

static uint16_t read_le16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t read_le32(const uint8_t *p) {
    return (uint32_t)p[0]
        | ((uint32_t)p[1] << 8)
        | ((uint32_t)p[2] << 16)
        | ((uint32_t)p[3] << 24);
}

static bool valid_adc_metadata(
    uint8_t model,
    uint8_t sample_format,
    uint8_t resolution,
    uint8_t input_mode) {
    switch (model) {
        case REV_A_ADC_ADS8861:
            return sample_format == REV_A_SAMPLE_TWOS_COMPLEMENT
                && resolution == 16u
                && input_mode == REV_A_INPUT_DIFFERENTIAL;
        case REV_A_ADC_ADS8860:
            return sample_format == REV_A_SAMPLE_UNSIGNED
                && resolution == 16u
                && input_mode == REV_A_INPUT_SINGLE_ENDED;
        case REV_A_ADC_ADS7054:
            return sample_format == REV_A_SAMPLE_TWOS_COMPLEMENT
                && resolution == 14u
                && input_mode == REV_A_INPUT_DIFFERENTIAL;
        case REV_A_ADC_AD7980:
            return sample_format == REV_A_SAMPLE_UNSIGNED
                && resolution == 16u
                && input_mode == REV_A_INPUT_PSEUDO_DIFFERENTIAL;
        default:
            return false;
    }
}

uint16_t rev_a_crc16_ccitt_false(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFFu;
    if (data == NULL && length != 0u) {
        return 0u;
    }

    for (size_t i = 0u; i < length; ++i) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (uint8_t bit = 0u; bit < 8u; ++bit) {
            if ((crc & 0x8000u) != 0u) {
                crc = (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

static bool frame_envelope_valid(
    const uint8_t *frame,
    size_t frame_length,
    uint8_t expected_type,
    uint16_t expected_body_length) {
    if (frame == NULL || frame_length < 8u) {
        return false;
    }
    if (frame[0] != REV_A_SYNC_BYTE_0 || frame[1] != REV_A_SYNC_BYTE_1) {
        return false;
    }
    if (frame[2] != REV_A_PROTOCOL_VERSION || frame[3] != expected_type) {
        return false;
    }

    const uint16_t body_length = read_le16(&frame[4]);
    if (body_length != expected_body_length
        || frame_length != (size_t)body_length + 4u) {
        return false;
    }

    const uint16_t received_crc = read_le16(&frame[frame_length - 2u]);
    return rev_a_crc16_ccitt_false(&frame[2], body_length) == received_crc;
}

bool rev_a_decode_measurement(
    const uint8_t *frame,
    size_t frame_length,
    rev_a_measurement_t *measurement) {
    if (frame == NULL || measurement == NULL || frame_length < 35u) {
        return false;
    }
    if (frame[0] != REV_A_SYNC_BYTE_0 || frame[1] != REV_A_SYNC_BYTE_1
        || frame[2] != REV_A_PROTOCOL_VERSION
        || frame[3] != REV_A_TYPE_MEASUREMENT) {
        return false;
    }

    const uint16_t body_length = read_le16(&frame[4]);
    if (body_length < MEASUREMENT_MIN_BODY_LENGTH
        || body_length > MEASUREMENT_MAX_BODY_LENGTH
        || frame_length != (size_t)body_length + 4u) {
        return false;
    }

    const uint8_t sample_count = frame[30];
    if (sample_count == 0u || sample_count > REV_A_MAX_SAMPLES
        || body_length != MEASUREMENT_FIXED_BODY_LENGTH + 2u * sample_count) {
        return false;
    }

    const uint8_t valid_mask = frame[29];
    const uint16_t allowed_mask = (uint16_t)((1u << sample_count) - 1u);
    if (((uint16_t)valid_mask & (uint16_t)~allowed_mask) != 0u) {
        return false;
    }

    const uint16_t flags = read_le16(&frame[15]);
    if ((flags & REV_A_FLAG_SWEEP_COMPLETE) != 0u
        && sample_count != REV_A_MAX_SAMPLES) {
        return false;
    }
    if (read_le16(&frame[21]) == 0u) {
        return false;
    }

    const uint16_t received_crc = read_le16(&frame[frame_length - 2u]);
    if (rev_a_crc16_ccitt_false(&frame[2], body_length) != received_crc) {
        return false;
    }

    memset(measurement, 0, sizeof(*measurement));
    measurement->sequence = read_le32(&frame[6]);
    measurement->timestamp_us = read_le32(&frame[10]);
    measurement->profile_id = frame[14];
    measurement->flags = flags;
    measurement->pulse_width_ns = read_le32(&frame[17]);
    measurement->pulse_rate_hz = read_le16(&frame[21]);
    measurement->supply_mv = read_le16(&frame[23]);
    measurement->tx_current_ma = read_le16(&frame[25]);
    const uint16_t raw_temperature = read_le16(&frame[27]);
    measurement->temp_centi_c = raw_temperature <= 0x7FFFu
        ? (int16_t)raw_temperature
        : (int16_t)((int32_t)raw_temperature - 65536);
    measurement->valid_mask = valid_mask;
    measurement->sample_count = sample_count;
    measurement->crc16 = received_crc;

    for (uint8_t i = 0u; i < sample_count; ++i) {
        measurement->samples[i] = read_le16(&frame[31u + 2u * i]);
    }
    return true;
}

bool rev_a_decode_device_info(
    const uint8_t *frame,
    size_t frame_length,
    rev_a_device_info_t *device_info) {
    if (device_info == NULL
        || !frame_envelope_valid(
            frame, frame_length, REV_A_TYPE_DEVICE_INFO, DEVICE_INFO_BODY_LENGTH)) {
        return false;
    }
    if (frame_length != 25u) {
        return false;
    }

    rev_a_device_info_t decoded;
    decoded.hw_rev = frame[6];
    decoded.fw_major = frame[7];
    decoded.fw_minor = frame[8];
    decoded.fw_patch = frame[9];
    decoded.adc_model_id = frame[10];
    decoded.sample_format_id = frame[11];
    decoded.adc_resolution_bits = frame[12];
    decoded.adc_input_mode_id = frame[13];
    decoded.adc_vref_uv = read_le32(&frame[14]);
    decoded.active_profile_id = frame[18];
    decoded.profile_crc32 = read_le32(&frame[19]);
    decoded.crc16 = read_le16(&frame[23]);

    if (!valid_adc_metadata(
            decoded.adc_model_id,
            decoded.sample_format_id,
            decoded.adc_resolution_bits,
            decoded.adc_input_mode_id)) {
        return false;
    }

    *device_info = decoded;
    return true;
}

bool rev_a_interpret_sample(
    uint16_t raw_word,
    uint8_t sample_format_id,
    uint8_t resolution_bits,
    int32_t *interpreted_value) {
    if (interpreted_value == NULL || (resolution_bits != 14u && resolution_bits != 16u)) {
        return false;
    }

    const uint32_t maximum = (1u << resolution_bits) - 1u;
    if ((uint32_t)raw_word > maximum) {
        return false;
    }

    if (sample_format_id == REV_A_SAMPLE_UNSIGNED) {
        *interpreted_value = (int32_t)raw_word;
        return true;
    }
    if (sample_format_id != REV_A_SAMPLE_TWOS_COMPLEMENT) {
        return false;
    }

    const uint32_t sign_bit = 1u << (resolution_bits - 1u);
    if (((uint32_t)raw_word & sign_bit) != 0u) {
        *interpreted_value = (int32_t)raw_word - (int32_t)(1u << resolution_bits);
    } else {
        *interpreted_value = (int32_t)raw_word;
    }
    return true;
}

void rev_a_parser_init(rev_a_parser_t *parser) {
    if (parser != NULL) {
        memset(parser, 0, sizeof(*parser));
    }
}

static void discard_prefix(rev_a_parser_t *parser, size_t count) {
    if (count == 0u) {
        return;
    }
    if (count < parser->used) {
        memmove(parser->buffer, &parser->buffer[count], parser->used - count);
    }
    parser->used -= count;
    parser->discarded_bytes += (uint32_t)count;
}

static bool measurement_length_valid(uint16_t length) {
    return length >= MEASUREMENT_MIN_BODY_LENGTH
        && length <= MEASUREMENT_MAX_BODY_LENGTH;
}

static size_t parse_available(
    rev_a_parser_t *parser,
    rev_a_frame_callback_t callback,
    void *user_context) {
    size_t accepted = 0u;

    for (;;) {
        size_t sync_at = 0u;
        while (sync_at + 1u < parser->used
            && !(parser->buffer[sync_at] == REV_A_SYNC_BYTE_0
                && parser->buffer[sync_at + 1u] == REV_A_SYNC_BYTE_1)) {
            ++sync_at;
        }

        if (sync_at + 1u >= parser->used) {
            const size_t keep = parser->used > 0u
                && parser->buffer[parser->used - 1u] == REV_A_SYNC_BYTE_0 ? 1u : 0u;
            discard_prefix(parser, parser->used - keep);
            return accepted;
        }
        if (sync_at != 0u) {
            discard_prefix(parser, sync_at);
        }
        if (parser->used < 6u) {
            return accepted;
        }

        const uint8_t version = parser->buffer[2];
        const uint8_t type = parser->buffer[3];
        const uint16_t body_length = read_le16(&parser->buffer[4]);
        const bool length_valid =
            (type == REV_A_TYPE_MEASUREMENT && measurement_length_valid(body_length))
            || (type == REV_A_TYPE_DEVICE_INFO && body_length == DEVICE_INFO_BODY_LENGTH);

        if (version != REV_A_PROTOCOL_VERSION || !length_valid) {
            discard_prefix(parser, 1u);
            ++parser->rejected_frames;
            continue;
        }

        const size_t frame_length = (size_t)body_length + 4u;
        if (parser->used < frame_length) {
            return accepted;
        }

        rev_a_frame_t decoded;
        bool valid = false;
        if (type == REV_A_TYPE_MEASUREMENT) {
            valid = rev_a_decode_measurement(
                parser->buffer, frame_length, &decoded.value.measurement);
        } else {
            valid = rev_a_decode_device_info(
                parser->buffer, frame_length, &decoded.value.device_info);
        }

        if (!valid) {
            discard_prefix(parser, 1u);
            ++parser->rejected_frames;
            continue;
        }

        decoded.type = type;
        if (callback != NULL) {
            callback(user_context, &decoded);
        }
        ++accepted;
        discard_prefix(parser, frame_length);
    }
}

size_t rev_a_parser_feed(
    rev_a_parser_t *parser,
    const uint8_t *data,
    size_t length,
    rev_a_frame_callback_t callback,
    void *user_context) {
    if (parser == NULL || (data == NULL && length != 0u)) {
        return 0u;
    }

    size_t accepted = 0u;
    for (size_t i = 0u; i < length; ++i) {
        if (parser->used >= sizeof(parser->buffer)) {
            discard_prefix(parser, 1u);
            ++parser->rejected_frames;
        }
        parser->buffer[parser->used++] = data[i];
        accepted += parse_available(parser, callback, user_context);
    }
    return accepted;
}
