#include "rev_a_protocol.h"

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
    write_le16(&frame[27], 2534u);
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

    puts("PASS: Rev A C parser CRC, DEVICE_INFO metadata, sample formats, fragmented/noisy streams and SYNC recovery");
    return 0;
}
