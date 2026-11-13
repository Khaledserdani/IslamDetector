#include "rev_a_protocol.h"
#include "rev_a_session.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #condition); \
        return 1; \
    } \
} while (0)

typedef struct {
    size_t count;
    rev_a_frame_t frames[8];
} frame_sink_t;

static void write_le16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
}

static uint16_t read_le16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static void write_le32(uint8_t *p, uint32_t value) {
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16);
    p[3] = (uint8_t)(value >> 24);
}

static void finish_frame(uint8_t *frame, size_t body_length) {
    const uint16_t crc = rev_a_crc16_ccitt_false(&frame[2], body_length);
    write_le16(&frame[2u + body_length], crc);
}

static size_t make_measurement(uint8_t frame[REV_A_MAX_FRAME_SIZE]) {
    const uint16_t body_length = 45u;
    memset(frame, 0, REV_A_MAX_FRAME_SIZE);
    frame[0] = REV_A_SYNC_BYTE_0;
    frame[1] = REV_A_SYNC_BYTE_1;
    frame[2] = REV_A_PROTOCOL_VERSION;
    frame[3] = REV_A_TYPE_MEASUREMENT;
    write_le16(&frame[4], body_length);
    write_le32(&frame[6], 0x12345678u);
    write_le32(&frame[10], 0x01020304u);
    frame[14] = 2u;
    write_le16(&frame[15], REV_A_FLAG_SWEEP_COMPLETE);
    write_le32(&frame[17], 20000u);
    write_le16(&frame[21], 100u);
    write_le16(&frame[23], 12000u);
    write_le16(&frame[25], 1250u);
    write_le16(&frame[27], (uint16_t)(int16_t)-123);
    frame[29] = 0xFFu;
    frame[30] = 8u;
    const uint16_t samples[8] = {
        0x0001u, 0x7FFFu, 0x8000u, 0xFFFFu,
        0x1234u, 0x2345u, 0x3456u, 0x4567u
    };
    for (size_t i = 0u; i < 8u; ++i) {
        write_le16(&frame[31u + 2u * i], samples[i]);
    }
    finish_frame(frame, body_length);
    return REV_A_MAX_FRAME_SIZE;
}

static size_t make_device_info(uint8_t frame[25], uint8_t sample_format) {
    const uint16_t body_length = 21u;
    memset(frame, 0, 25u);
    frame[0] = REV_A_SYNC_BYTE_0;
    frame[1] = REV_A_SYNC_BYTE_1;
    frame[2] = REV_A_PROTOCOL_VERSION;
    frame[3] = REV_A_TYPE_DEVICE_INFO;
    write_le16(&frame[4], body_length);
    frame[6] = 1u;  /* HW_REV */
    frame[7] = 0u;  /* FW_MAJOR */
    frame[8] = 1u;  /* FW_MINOR */
    frame[9] = 0u;  /* FW_PATCH */
    frame[10] = REV_A_ADC_ADS8861;
    frame[11] = sample_format;
    frame[12] = 16u;
    frame[13] = REV_A_INPUT_DIFFERENTIAL;
    write_le32(&frame[14], 4096000u);
    frame[18] = 2u;
    write_le32(&frame[19], 0x1234ABCDu);
    finish_frame(frame, body_length);
    return 25u;
}

static void collect_frame(void *context, const rev_a_frame_t *frame) {
    frame_sink_t *sink = (frame_sink_t *)context;
    if (sink->count < (sizeof(sink->frames) / sizeof(sink->frames[0]))) {
        sink->frames[sink->count++] = *frame;
    }
}

int main(void) {
    CHECK(rev_a_crc16_ccitt_false((const uint8_t *)"123456789", 9u) == 0x29B1u);
    uint8_t command_frame[REV_A_MAX_COMMAND_FRAME_SIZE];
    size_t command_length = 0u;
    CHECK(rev_a_encode_command(
        REV_A_TYPE_GET_INFO, NULL, 0u,
        command_frame, sizeof(command_frame), &command_length));
    CHECK(command_length == 8u);
    CHECK(command_frame[0] == REV_A_SYNC_BYTE_0);
    CHECK(command_frame[1] == REV_A_SYNC_BYTE_1);
    CHECK(command_frame[3] == REV_A_TYPE_GET_INFO);
    CHECK(read_le16(&command_frame[4]) == 4u);
    CHECK(read_le16(&command_frame[6]) ==
          rev_a_crc16_ccitt_false(&command_frame[2], 4u));

    const uint8_t profile_id = 2u;
    CHECK(rev_a_encode_command(
        REV_A_TYPE_SET_PROFILE, &profile_id, 1u,
        command_frame, sizeof(command_frame), &command_length));
    CHECK(command_length == 9u);
    CHECK(command_frame[3] == REV_A_TYPE_SET_PROFILE);
    CHECK(read_le16(&command_frame[4]) == 5u);
    CHECK(command_frame[6] == profile_id);
    CHECK(read_le16(&command_frame[7]) ==
          rev_a_crc16_ccitt_false(&command_frame[2], 5u));
    CHECK(!rev_a_encode_command(
        REV_A_TYPE_GET_INFO, &profile_id, 1u,
        command_frame, sizeof(command_frame), &command_length));
    CHECK(!rev_a_encode_command(
        REV_A_TYPE_SET_PROFILE, NULL, 0u,
        command_frame, sizeof(command_frame), &command_length));
    CHECK(!rev_a_encode_command(
        0x7Fu, NULL, 0u,
        command_frame, sizeof(command_frame), &command_length));
    CHECK(!rev_a_encode_command(
        REV_A_TYPE_SET_PROFILE, &profile_id, 1u,
        command_frame, 8u, &command_length));

    uint8_t measurement_bytes[REV_A_MAX_FRAME_SIZE];
    const size_t measurement_length = make_measurement(measurement_bytes);
    rev_a_measurement_t measurement;
    CHECK(rev_a_decode_measurement(
        measurement_bytes, measurement_length, &measurement));
    CHECK(measurement.sequence == 0x12345678u);
    CHECK(measurement.timestamp_us == 0x01020304u);
    CHECK(measurement.sample_count == 8u);
    CHECK(measurement.samples[2] == 0x8000u);
    CHECK(measurement.tx_current_ma == 1250u);
    CHECK(measurement.temp_centi_c == -123);

    uint8_t info_bytes[25];
    const size_t info_length = make_device_info(info_bytes, REV_A_SAMPLE_TWOS_COMPLEMENT);
    rev_a_device_info_t info;
    CHECK(rev_a_decode_device_info(info_bytes, info_length, &info));
    CHECK(info.adc_model_id == REV_A_ADC_ADS8861);
    CHECK(info.adc_vref_uv == 4096000u);
    CHECK(info.profile_crc32 == 0x1234ABCDu);

    int32_t interpreted = 0;
    CHECK(rev_a_interpret_sample(0x8000u, REV_A_SAMPLE_TWOS_COMPLEMENT, 16u, &interpreted));
    CHECK(interpreted == -32768);
    CHECK(rev_a_interpret_sample(0xFFFFu, REV_A_SAMPLE_TWOS_COMPLEMENT, 16u, &interpreted));
    CHECK(interpreted == -1);
    CHECK(rev_a_interpret_sample(0x2000u, REV_A_SAMPLE_TWOS_COMPLEMENT, 14u, &interpreted));
    CHECK(interpreted == -8192);
    CHECK(rev_a_interpret_sample(0x3FFFu, REV_A_SAMPLE_TWOS_COMPLEMENT, 14u, &interpreted));
    CHECK(interpreted == -1);
    CHECK(!rev_a_interpret_sample(0x4000u, REV_A_SAMPLE_TWOS_COMPLEMENT, 14u, &interpreted));

    uint8_t invalid_info[25];
    make_device_info(invalid_info, REV_A_SAMPLE_UNSIGNED);
    CHECK(!rev_a_decode_device_info(invalid_info, sizeof(invalid_info), &info));

    frame_sink_t sink;
    memset(&sink, 0, sizeof(sink));
    rev_a_parser_t parser;
    rev_a_parser_init(&parser);

    CHECK(rev_a_parser_feed(
        &parser, measurement_bytes, 7u, collect_frame, &sink) == 0u);
    CHECK(rev_a_parser_feed(
        &parser, &measurement_bytes[7], measurement_length - 7u,
        collect_frame, &sink) == 1u);
    CHECK(sink.count == 1u);
    CHECK(sink.frames[0].type == REV_A_TYPE_MEASUREMENT);

    rev_a_parser_init(&parser);
    memset(&sink, 0, sizeof(sink));
    const uint8_t noise[] = {0x00u, 0x49u, 0x00u, 0xFFu};
    CHECK(rev_a_parser_feed(&parser, noise, sizeof(noise), collect_frame, &sink) == 0u);
    const uint8_t split_sync_prefix[] = {0x49u};
    CHECK(rev_a_parser_feed(&parser, split_sync_prefix, sizeof(split_sync_prefix), collect_frame, &sink) == 0u);
    CHECK(rev_a_parser_feed(&parser, &measurement_bytes[1], measurement_length - 1u, collect_frame, &sink) == 1u);
    CHECK(sink.count == 1u);
    rev_a_parser_init(&parser);
    memset(&sink, 0, sizeof(sink));
    uint8_t combined[25u + REV_A_MAX_FRAME_SIZE];
    memcpy(combined, info_bytes, info_length);
    memcpy(&combined[info_length], measurement_bytes, measurement_length);
    CHECK(rev_a_parser_feed(
        &parser, combined, info_length + measurement_length,
        collect_frame, &sink) == 2u);
    CHECK(sink.count == 2u);
    CHECK(sink.frames[0].type == REV_A_TYPE_DEVICE_INFO);
    CHECK(sink.frames[1].type == REV_A_TYPE_MEASUREMENT);

    rev_a_parser_init(&parser);
    memset(&sink, 0, sizeof(sink));
    uint8_t damaged[REV_A_MAX_FRAME_SIZE];
    memcpy(damaged, measurement_bytes, measurement_length);
    damaged[measurement_length - 3u] ^= 0x80u;
    uint8_t damaged_then_good[2u * REV_A_MAX_FRAME_SIZE];
    memcpy(damaged_then_good, damaged, measurement_length);
    memcpy(&damaged_then_good[measurement_length], measurement_bytes, measurement_length);
    CHECK(rev_a_parser_feed(
        &parser, damaged_then_good, 2u * measurement_length,
        collect_frame, &sink) == 1u);
    CHECK(sink.count == 1u);
    CHECK(sink.frames[0].value.measurement.sequence == 0x12345678u);
    CHECK(parser.rejected_frames > 0u);

    rev_a_session_t session;
    rev_a_session_measurement_t session_measurement;
    rev_a_frame_t session_frame;
    memset(&session_frame, 0, sizeof(session_frame));
    rev_a_session_reset(&session);

    session_frame.type = REV_A_TYPE_MEASUREMENT;
    session_frame.value.measurement = measurement;
    session_frame.value.measurement.valid_mask = 0x0Du;
    session_frame.value.measurement.samples[1] = 0xDEADu;
    CHECK(rev_a_session_accept_frame(
        &session, &session_frame, &session_measurement)
        == REV_A_SESSION_WAITING_FOR_DEVICE_INFO);
    CHECK(session.rejected_measurements_without_info == 1u);

    session_frame.type = REV_A_TYPE_DEVICE_INFO;
    session_frame.value.device_info = info;
    CHECK(rev_a_session_accept_frame(
        &session, &session_frame, NULL) == REV_A_SESSION_DEVICE_INFO_ACCEPTED);
    CHECK(session.device_info_valid);
    session_frame.type = REV_A_TYPE_MEASUREMENT;
    session_frame.value.measurement = measurement;
    session_frame.value.measurement.valid_mask = 0x0Du;
    session_frame.value.measurement.samples[1] = 0xDEADu;
    CHECK(rev_a_session_accept_frame(
        &session, &session_frame, &session_measurement)
        == REV_A_SESSION_MEASUREMENT_ACCEPTED);
    CHECK(session_measurement.adc_model_id == REV_A_ADC_ADS8861);
    CHECK(session_measurement.adc_vref_uv == 4096000u);
    CHECK(session_measurement.raw.samples[1] == 0xDEADu);
    CHECK(session_measurement.interpreted_mask == 0x0Du);
    CHECK(session_measurement.interpreted_samples[0] == 1);
    CHECK(session_measurement.interpreted_samples[2] == -32768);
    CHECK(session_measurement.interpreted_samples[3] == -1);
    CHECK(session_measurement.info_generation == session.info_generation);
    CHECK(session.accepted_measurements == 1u);

    rev_a_session_invalidate_device_info(&session);
    CHECK(!session.device_info_valid);
    CHECK(rev_a_session_accept_frame(
        &session, &session_frame, &session_measurement)
        == REV_A_SESSION_WAITING_FOR_DEVICE_INFO);
    CHECK(session.rejected_measurements_without_info == 2u);

    rev_a_device_info_t bad_info = info;
    bad_info.sample_format_id = REV_A_SAMPLE_UNSIGNED;
    CHECK(!rev_a_device_info_valid(&bad_info));
    session_frame.type = REV_A_TYPE_DEVICE_INFO;
    session_frame.value.device_info = bad_info;
    CHECK(rev_a_session_accept_frame(
        &session, &session_frame, NULL) == REV_A_SESSION_INVALID_DEVICE_INFO);
    CHECK(!session.device_info_valid);

    rev_a_device_info_t info14;
    memset(&info14, 0, sizeof(info14));
    info14.adc_model_id = REV_A_ADC_ADS7054;
    info14.sample_format_id = REV_A_SAMPLE_TWOS_COMPLEMENT;
    info14.adc_resolution_bits = 14u;
    info14.adc_input_mode_id = REV_A_INPUT_DIFFERENTIAL;
    info14.adc_vref_uv = 3300000u;
    CHECK(rev_a_device_info_valid(&info14));
    session_frame.type = REV_A_TYPE_DEVICE_INFO;
    session_frame.value.device_info = info14;
    CHECK(rev_a_session_accept_frame(
        &session, &session_frame, NULL) == REV_A_SESSION_DEVICE_INFO_ACCEPTED);
    session_frame.type = REV_A_TYPE_MEASUREMENT;
    session_frame.value.measurement = measurement;
    session_frame.value.measurement.valid_mask = 0x01u;
    session_frame.value.measurement.samples[0] = 0x2000u;
    CHECK(rev_a_session_accept_frame(
        &session, &session_frame, &session_measurement)
        == REV_A_SESSION_MEASUREMENT_ACCEPTED);
    CHECK(session_measurement.adc_model_id == REV_A_ADC_ADS7054);
    CHECK(session_measurement.raw.samples[0] == 0x2000u);
    CHECK(session_measurement.interpreted_samples[0] == -8192);
    CHECK(session_measurement.interpreted_mask == 0x01u);

    session_frame.type = 0x7Fu;
    CHECK(rev_a_session_accept_frame(
        &session, &session_frame, &session_measurement)
        == REV_A_SESSION_UNSUPPORTED_FRAME);

    puts("PASS: Rev A parser CRC, DEVICE_INFO, metadata-gated sessions, raw preservation, signed ADC formats and SYNC recovery");
    return 0;
}
