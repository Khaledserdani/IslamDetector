#ifndef ISLAM_REV_A_PROTOCOL_H
#define ISLAM_REV_A_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REV_A_PROTOCOL_VERSION       1u
#define REV_A_SYNC_BYTE_0             0x49u
#define REV_A_SYNC_BYTE_1             0x53u
#define REV_A_TYPE_MEASUREMENT        0x10u
#define REV_A_TYPE_DEVICE_INFO        0x82u
#define REV_A_MAX_SAMPLES             8u
#define REV_A_MAX_FRAME_SIZE          49u
#define REV_A_PARSER_CAPACITY         64u
#define REV_A_FLAG_SWEEP_COMPLETE     (1u << 8)
#define REV_A_INVALID_CURRENT_MA      0xFFFFu
#define REV_A_INVALID_TEMPERATURE     0x7FFF

#define REV_A_ADC_ADS8861             0x01u
#define REV_A_ADC_ADS8860             0x02u
#define REV_A_ADC_ADS7054             0x03u
#define REV_A_ADC_AD7980              0x04u

#define REV_A_SAMPLE_TWOS_COMPLEMENT  0x01u
#define REV_A_SAMPLE_UNSIGNED         0x02u

#define REV_A_INPUT_DIFFERENTIAL      0x01u
#define REV_A_INPUT_SINGLE_ENDED      0x02u
#define REV_A_INPUT_PSEUDO_DIFFERENTIAL 0x03u

typedef struct {
    uint32_t sequence;
    uint32_t timestamp_us;
    uint8_t profile_id;
    uint16_t flags;
    uint32_t pulse_width_ns;
    uint16_t pulse_rate_hz;
    uint16_t supply_mv;
    uint16_t tx_current_ma;
    int16_t temp_centi_c;
    uint8_t valid_mask;
    uint8_t sample_count;
    uint16_t samples[REV_A_MAX_SAMPLES];
    uint16_t crc16;
} rev_a_measurement_t;

typedef struct {
    uint8_t hw_rev;
    uint8_t fw_major;
    uint8_t fw_minor;
    uint8_t fw_patch;
    uint8_t adc_model_id;
    uint8_t sample_format_id;
    uint8_t adc_resolution_bits;
    uint8_t adc_input_mode_id;
    uint32_t adc_vref_uv;
    uint8_t active_profile_id;
    uint32_t profile_crc32;
    uint16_t crc16;
} rev_a_device_info_t;

typedef struct {
    uint8_t type;
    union {
        rev_a_measurement_t measurement;
        rev_a_device_info_t device_info;
    } value;
} rev_a_frame_t;

typedef void (*rev_a_frame_callback_t)(
    void *user_context,
    const rev_a_frame_t *frame);

typedef struct {
    uint8_t buffer[REV_A_PARSER_CAPACITY];
    size_t used;
    uint32_t discarded_bytes;
    uint32_t rejected_frames;
} rev_a_parser_t;

uint16_t rev_a_crc16_ccitt_false(const uint8_t *data, size_t length);

bool rev_a_decode_measurement(
    const uint8_t *frame,
    size_t frame_length,
    rev_a_measurement_t *measurement);

bool rev_a_decode_device_info(
    const uint8_t *frame,
    size_t frame_length,
    rev_a_device_info_t *device_info);

/* raw_word is right-justified; ADS7054 uses only bits 13..0. */
bool rev_a_interpret_sample(
    uint16_t raw_word,
    uint8_t sample_format_id,
    uint8_t resolution_bits,
    int32_t *interpreted_value);

void rev_a_parser_init(rev_a_parser_t *parser);

/*
 * Feed arbitrary UART byte fragments. Complete, CRC-valid MEASUREMENT and
 * DEVICE_INFO frames are delivered synchronously through callback.
 * The callback must copy any data it needs after it returns and must not block.
 * Unknown types, malformed headers and bad CRCs are discarded with SYNC recovery.
 * The return value is the number of accepted frames in this call.
 */
size_t rev_a_parser_feed(
    rev_a_parser_t *parser,
    const uint8_t *data,
    size_t length,
    rev_a_frame_callback_t callback,
    void *user_context);

#ifdef __cplusplus
}
#endif

#endif
