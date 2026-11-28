import unittest

from rev_a_protocol import (
    FLAG_SWEEP_COMPLETE,
    INVALID_CURRENT_MA,
    INVALID_TEMPERATURE_CENTI_C,
    MeasurementStreamDecoder,
    SAMPLE_FORMAT_UNKNOWN,
    SAMPLE_FORMAT_TWOS_COMPLEMENT,
    SAMPLE_FORMAT_UNSIGNED,
    ADC_MODEL_NONE,
    ADC_MODEL_ADS8861,
    ADC_MODEL_ADS8860,
    ADC_MODEL_ADS7054,
    ADC_MODEL_AD7980,
    ADC_INPUT_UNKNOWN,
    ADC_INPUT_DIFFERENTIAL,
    ADC_INPUT_SINGLE_ENDED,
    ADC_INPUT_PSEUDO_DIFFERENTIAL,
    TYPE_DEVICE_INFO,
    TYPE_ACK,
    TYPE_HELLO,
    TYPE_GET_INFO,
    TYPE_START,
    TYPE_SET_PROFILE,
    TYPE_STOP,
    ACK_STATUS_OK,
    ACK_STATUS_REJECTED,
    ACK_REASON_NONE,
    ACK_REASON_TX_NOT_ARMED,
    ProtocolStreamDecoder,
    encode_device_info,
    decode_device_info,
    encode_command,
    decode_command,
    encode_ack,
    decode_ack,
    interpret_sample,
    ProtocolError,
    crc16_ccitt_false,
    decode_measurement,
    encode_measurement,
)


class ProtocolTests(unittest.TestCase):
    def sample_frame(self):
        return encode_measurement(
            sequence=0x12345678,
            timestamp_us=0x01020304,
            profile_id=2,
            flags=0x0040 | FLAG_SWEEP_COMPLETE,
            pulse_width_ns=20_000,
            pulse_rate_hz=100,
            supply_mv=12_000,
            tx_current_ma=1_250,
            temp_centi_c=2534,
            valid_mask=0xFF,
            samples=[1200, 1100, 900, 700, 500, 300, 200, 100],
        )

    def test_crc_known_vector(self):
        self.assertEqual(crc16_ccitt_false(b"123456789"), 0x29B1)

    def test_eight_sample_sweep_round_trip(self):
        frame = self.sample_frame()
        self.assertEqual(len(frame), 49)
        decoded = decode_measurement(frame)
        self.assertEqual(decoded["sequence"], 0x12345678)
        self.assertEqual(decoded["timestamp_us"], 0x01020304)
        self.assertEqual(decoded["sample_count"], 8)
        self.assertEqual(decoded["samples"], [1200, 1100, 900, 700, 500, 300, 200, 100])
        self.assertEqual(decoded["valid_mask"], 0xFF)

    def test_invalid_sensor_sentinels(self):
        frame = encode_measurement(
            sequence=1, timestamp_us=2, profile_id=0, flags=0,
            pulse_width_ns=20_000, pulse_rate_hz=100, supply_mv=12_000,
            tx_current_ma=INVALID_CURRENT_MA,
            temp_centi_c=INVALID_TEMPERATURE_CENTI_C,
            valid_mask=0x01, samples=[0x1234],
        )
        decoded = decode_measurement(frame)
        self.assertEqual(decoded["tx_current_ma"], INVALID_CURRENT_MA)
        self.assertEqual(decoded["temp_centi_c"], INVALID_TEMPERATURE_CENTI_C)

    def test_corrupt_crc_is_rejected(self):
        frame = bytearray(self.sample_frame())
        frame[35] ^= 0x01
        with self.assertRaises(ProtocolError):
            decode_measurement(bytes(frame))

    def test_bad_sync_is_rejected(self):
        frame = bytearray(self.sample_frame())
        frame[0] = 0
        with self.assertRaises(ProtocolError):
            decode_measurement(bytes(frame))

    def test_complete_sweep_requires_eight_samples(self):
        with self.assertRaises(ProtocolError):
            encode_measurement(
                sequence=1, timestamp_us=2, profile_id=0,
                flags=FLAG_SWEEP_COMPLETE, pulse_width_ns=20_000,
                pulse_rate_hz=100, supply_mv=12_000, tx_current_ma=100,
                temp_centi_c=2000, valid_mask=0x7F,
                samples=[1, 2, 3, 4, 5, 6, 7],
            )

    def test_stream_decoder_handles_fragmented_frame(self):
        frame = self.sample_frame()
        parser = MeasurementStreamDecoder()
        self.assertEqual(parser.feed(frame[:5]), [])
        self.assertEqual(parser.feed(frame[5:24]), [])
        decoded = parser.feed(frame[24:])
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0]["samples"], [1200, 1100, 900, 700, 500, 300, 200, 100])

    def test_stream_decoder_handles_noise_and_concatenated_frames(self):
        frame = self.sample_frame()
        parser = MeasurementStreamDecoder()
        decoded = parser.feed(b"noise" + frame + frame)
        self.assertEqual(len(decoded), 2)
        self.assertGreaterEqual(parser.discarded_bytes, 5)

    def test_stream_decoder_recovers_after_corrupt_frame(self):
        good = self.sample_frame()
        corrupt = bytearray(good)
        corrupt[-3] ^= 0x80
        parser = MeasurementStreamDecoder()
        decoded = parser.feed(bytes(corrupt) + good)
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0]["sequence"], 0x12345678)
        self.assertGreater(parser.rejected_frames, 0)

    def test_stream_decoder_preserves_split_sync_byte(self):
        frame = self.sample_frame()
        parser = MeasurementStreamDecoder()
        self.assertEqual(parser.feed(b"junkI"), [])
        decoded = parser.feed(frame[1:])
        self.assertEqual(len(decoded), 1)

    def test_device_info_round_trip(self):
        frame = encode_device_info(
            hw_rev=1, fw_major=0, fw_minor=1, fw_patch=0,
            adc_model_id=ADC_MODEL_ADS8861,
            sample_format_id=SAMPLE_FORMAT_TWOS_COMPLEMENT,
            adc_resolution_bits=16,
            adc_input_mode_id=ADC_INPUT_DIFFERENTIAL,
            adc_vref_uv=4096000,
            active_profile_id=2,
            profile_crc32=0x1234ABCD,
        )
        decoded = decode_device_info(frame)
        self.assertEqual(decoded["adc_model_id"], ADC_MODEL_ADS8861)
        self.assertEqual(decoded["sample_format_id"], SAMPLE_FORMAT_TWOS_COMPLEMENT)
        self.assertEqual(decoded["adc_vref_uv"], 4096000)
        self.assertEqual(decoded["profile_crc32"], 0x1234ABCD)

    def test_protocol_stream_decoder_accepts_device_info_and_measurement(self):
        info = encode_device_info(
            hw_rev=1, fw_major=0, fw_minor=1, fw_patch=0,
            adc_model_id=ADC_MODEL_ADS8861,
            sample_format_id=SAMPLE_FORMAT_TWOS_COMPLEMENT,
            adc_resolution_bits=16,
            adc_input_mode_id=ADC_INPUT_DIFFERENTIAL,
            adc_vref_uv=4096000,
            active_profile_id=2,
            profile_crc32=0x1234ABCD,
        )
        measurement = self.sample_frame()
        parser = ProtocolStreamDecoder()
        decoded = parser.feed(info + measurement)
        self.assertEqual([item["type"] for item in decoded], [TYPE_DEVICE_INFO, 0x10])

    def test_ads7054_device_info_uses_signed_14bit_format(self):
        frame = encode_device_info(
            hw_rev=1, fw_major=0, fw_minor=1, fw_patch=0,
            adc_model_id=0x03,
            sample_format_id=SAMPLE_FORMAT_TWOS_COMPLEMENT,
            adc_resolution_bits=14,
            adc_input_mode_id=ADC_INPUT_DIFFERENTIAL,
            adc_vref_uv=3300000,
            active_profile_id=2,
            profile_crc32=0x1234ABCD,
        )
        decoded = decode_device_info(frame)
        self.assertEqual(decoded["sample_format_id"], SAMPLE_FORMAT_TWOS_COMPLEMENT)
        self.assertEqual(decoded["adc_resolution_bits"], 14)
        self.assertEqual(decoded["adc_vref_uv"], 3300000)

    def test_device_info_vref_ranges_are_model_specific(self):
        cases = (
            (ADC_MODEL_ADS8861, SAMPLE_FORMAT_TWOS_COMPLEMENT, 16,
             ADC_INPUT_DIFFERENTIAL, 2_500_000, 5_000_000),
            (ADC_MODEL_ADS8860, SAMPLE_FORMAT_UNSIGNED, 16,
             ADC_INPUT_SINGLE_ENDED, 2_500_000, 5_000_000),
            (ADC_MODEL_ADS7054, SAMPLE_FORMAT_TWOS_COMPLEMENT, 14,
             ADC_INPUT_DIFFERENTIAL, 1_650_000, 3_600_000),
            (ADC_MODEL_AD7980, SAMPLE_FORMAT_UNSIGNED, 16,
             ADC_INPUT_PSEUDO_DIFFERENTIAL, 2_400_000, 5_100_000),
        )
        for model, sample_format, resolution, input_mode, minimum, maximum in cases:
            common = dict(
                hw_rev=1, fw_major=0, fw_minor=1, fw_patch=0,
                adc_model_id=model, sample_format_id=sample_format,
                adc_resolution_bits=resolution, adc_input_mode_id=input_mode,
                active_profile_id=2, profile_crc32=0x1234ABCD,
            )
            for vref in (minimum, maximum):
                with self.subTest(model=model, vref=vref):
                    frame = encode_device_info(**common, adc_vref_uv=vref)
                    self.assertEqual(decode_device_info(frame)["adc_vref_uv"], vref)
            for vref in (minimum - 1, maximum + 1):
                with self.subTest(model=model, invalid_vref=vref):
                    with self.assertRaises(ProtocolError):
                        encode_device_info(**common, adc_vref_uv=vref)
            with self.subTest(model=model, unknown_vref=0):
                frame = encode_device_info(**common, adc_vref_uv=0)
                self.assertEqual(decode_device_info(frame)["adc_vref_uv"], 0)

        # Decoder must enforce the same model-specific range after a valid CRC.
        frame = bytearray(encode_device_info(
            hw_rev=1, fw_major=0, fw_minor=1, fw_patch=0,
            adc_model_id=ADC_MODEL_ADS8861,
            sample_format_id=SAMPLE_FORMAT_TWOS_COMPLEMENT,
            adc_resolution_bits=16, adc_input_mode_id=ADC_INPUT_DIFFERENTIAL,
            adc_vref_uv=4_096_000, active_profile_id=2, profile_crc32=0x1234ABCD,
        ))
        frame[14:18] = (5_000_001).to_bytes(4, "little")
        frame[-2:] = crc16_ccitt_false(bytes(frame[2:-2])).to_bytes(2, "little")
        with self.assertRaises(ProtocolError):
            decode_device_info(bytes(frame))

    def test_device_info_rejects_inconsistent_adc_metadata(self):
        with self.assertRaises(ProtocolError):
            encode_device_info(
                hw_rev=1, fw_major=0, fw_minor=1, fw_patch=0,
                adc_model_id=ADC_MODEL_ADS8861,
                sample_format_id=SAMPLE_FORMAT_UNSIGNED,
                adc_resolution_bits=16,
                adc_input_mode_id=ADC_INPUT_DIFFERENTIAL,
                adc_vref_uv=4096000,
                active_profile_id=2,
                profile_crc32=0x1234ABCD,
            )

    def test_device_info_rejects_bad_crc(self):
        frame = bytearray(encode_device_info(
            hw_rev=1, fw_major=0, fw_minor=1, fw_patch=0,
            adc_model_id=ADC_MODEL_ADS8861,
            sample_format_id=SAMPLE_FORMAT_TWOS_COMPLEMENT,
            adc_resolution_bits=16,
            adc_input_mode_id=ADC_INPUT_DIFFERENTIAL,
            adc_vref_uv=4096000,
            active_profile_id=2,
            profile_crc32=0x1234ABCD,
        ))
        frame[-3] ^= 0x01
        with self.assertRaises(ProtocolError):
            decode_device_info(bytes(frame))

    def test_adc_sample_format_metadata_interpretation(self):
        self.assertEqual(interpret_sample(0x0001, SAMPLE_FORMAT_TWOS_COMPLEMENT), 1)
        self.assertEqual(interpret_sample(0x7FFF, SAMPLE_FORMAT_TWOS_COMPLEMENT), 32767)
        self.assertEqual(interpret_sample(0x8000, SAMPLE_FORMAT_TWOS_COMPLEMENT), -32768)
        self.assertEqual(interpret_sample(0xFFFF, SAMPLE_FORMAT_TWOS_COMPLEMENT), -1)
        self.assertEqual(interpret_sample(0xFFFF, SAMPLE_FORMAT_UNSIGNED), 65535)
        self.assertEqual(interpret_sample(0x1FFF, SAMPLE_FORMAT_TWOS_COMPLEMENT, 14), 8191)
        self.assertEqual(interpret_sample(0x2000, SAMPLE_FORMAT_TWOS_COMPLEMENT, 14), -8192)
        self.assertEqual(interpret_sample(0x3FFF, SAMPLE_FORMAT_TWOS_COMPLEMENT, 14), -1)
        with self.assertRaises(ProtocolError):
            interpret_sample(0x4000, SAMPLE_FORMAT_TWOS_COMPLEMENT, 14)
        with self.assertRaises(ProtocolError):
            interpret_sample(0x10000, SAMPLE_FORMAT_UNSIGNED)
        with self.assertRaises(ProtocolError):
            interpret_sample(0x1234, 0x7F)

    def test_stream_decoder_reset_clears_buffer_and_counters(self):
        frame = self.sample_frame()
        parser = MeasurementStreamDecoder()
        self.assertEqual(parser.feed(b"noiseI"), [])
        self.assertGreater(parser.discarded_bytes, 0)
        parser.reset()
        self.assertEqual(parser.discarded_bytes, 0)
        self.assertEqual(parser.rejected_frames, 0)
        self.assertEqual(parser.feed(frame), [decode_measurement(frame)])


    def test_adc_none_device_info_round_trip(self):
        frame = encode_device_info(
            hw_rev=0, fw_major=0, fw_minor=1, fw_patch=0,
            adc_model_id=ADC_MODEL_NONE,
            sample_format_id=SAMPLE_FORMAT_UNKNOWN,
            adc_resolution_bits=0,
            adc_input_mode_id=ADC_INPUT_UNKNOWN,
            adc_vref_uv=0,
            active_profile_id=1,
            profile_crc32=0x71E6D9DD,
        )
        decoded = decode_device_info(frame)
        self.assertEqual(decoded["adc_model_id"], ADC_MODEL_NONE)
        self.assertEqual(decoded["sample_format_id"], SAMPLE_FORMAT_UNKNOWN)
        self.assertEqual(decoded["adc_resolution_bits"], 0)
        self.assertEqual(decoded["adc_input_mode_id"], ADC_INPUT_UNKNOWN)
        self.assertEqual(decoded["adc_vref_uv"], 0)

    def test_adc_none_rejects_nonzero_vref(self):
        with self.assertRaises(ProtocolError):
            encode_device_info(
                hw_rev=0, fw_major=0, fw_minor=1, fw_patch=0,
                adc_model_id=ADC_MODEL_NONE,
                sample_format_id=SAMPLE_FORMAT_UNKNOWN,
                adc_resolution_bits=0,
                adc_input_mode_id=ADC_INPUT_UNKNOWN,
                adc_vref_uv=3300000,
                active_profile_id=1,
                profile_crc32=0x71E6D9DD,
            )

    def test_command_round_trip_and_payload_contract(self):
        for command_type in (TYPE_HELLO, TYPE_GET_INFO, TYPE_STOP):
            frame = encode_command(command_type)
            self.assertEqual(len(frame), 8)
            self.assertEqual(decode_command(frame)["type"], command_type)
        profile = encode_command(TYPE_SET_PROFILE, profile_id=1)
        self.assertEqual(len(profile), 9)
        self.assertEqual(decode_command(profile)["profile_id"], 1)
        with self.assertRaises(ProtocolError):
            encode_command(TYPE_HELLO, profile_id=1)
        with self.assertRaises(ProtocolError):
            encode_command(TYPE_SET_PROFILE)
        with self.assertRaises(ProtocolError):
            decode_command(encode_command(TYPE_HELLO)[:-1])

    def test_ack_round_trip_and_status_reason_contract(self):
        frame = encode_ack(TYPE_START, ACK_STATUS_REJECTED, ACK_REASON_TX_NOT_ARMED)
        self.assertEqual(len(frame), 11)
        decoded = decode_ack(frame)
        self.assertEqual(decoded["type"], TYPE_ACK)
        self.assertEqual(decoded["command_type"], 0x03)
        self.assertEqual(decoded["status"], ACK_STATUS_REJECTED)
        self.assertEqual(decoded["reason"], ACK_REASON_TX_NOT_ARMED)
        self.assertEqual(
            decode_ack(encode_ack(TYPE_STOP, ACK_STATUS_OK, ACK_REASON_NONE))["status"],
            ACK_STATUS_OK,
        )
        with self.assertRaises(ProtocolError):
            encode_ack(TYPE_STOP, ACK_STATUS_OK, ACK_REASON_TX_NOT_ARMED)
        with self.assertRaises(ProtocolError):
            encode_ack(TYPE_STOP, ACK_STATUS_REJECTED, ACK_REASON_NONE)

    def test_stream_decoder_accepts_commands_ack_and_adc_none(self):
        command = encode_command(TYPE_GET_INFO)
        ack = encode_ack(TYPE_GET_INFO, ACK_STATUS_OK, ACK_REASON_NONE)
        info = encode_device_info(
            hw_rev=0, fw_major=0, fw_minor=1, fw_patch=0,
            adc_model_id=ADC_MODEL_NONE,
            sample_format_id=SAMPLE_FORMAT_UNKNOWN,
            adc_resolution_bits=0,
            adc_input_mode_id=ADC_INPUT_UNKNOWN,
            adc_vref_uv=0,
            active_profile_id=1,
            profile_crc32=0x71E6D9DD,
        )
        measurement = self.sample_frame()
        parser = ProtocolStreamDecoder()
        decoded = parser.feed(b"noise" + command[:4])
        self.assertEqual(decoded, [])
        decoded = parser.feed(command[4:] + ack + info + measurement)
        self.assertEqual(
            [item["type"] for item in decoded],
            [TYPE_GET_INFO, TYPE_ACK, TYPE_DEVICE_INFO, 0x10],
        )
        self.assertEqual(decoded[2]["adc_model_id"], ADC_MODEL_NONE)
        self.assertEqual(decoded[1]["command_type"], TYPE_GET_INFO)

    def test_invalid_mask_is_rejected(self):
        with self.assertRaises(ProtocolError):
            encode_measurement(
                sequence=1, timestamp_us=2, profile_id=0, flags=0,
                pulse_width_ns=20_000, pulse_rate_hz=100, supply_mv=12_000,
                tx_current_ma=100, temp_centi_c=2000,
                valid_mask=0x02, samples=[100],
            )


if __name__ == "__main__":
    unittest.main()
