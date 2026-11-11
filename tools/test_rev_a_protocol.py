import unittest

from rev_a_protocol import (
    FLAG_SWEEP_COMPLETE,
    INVALID_CURRENT_MA,
    INVALID_TEMPERATURE_CENTI_C,
    MeasurementStreamDecoder,
    SAMPLE_FORMAT_TWOS_COMPLEMENT,
    SAMPLE_FORMAT_UNSIGNED,
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

    def test_adc_sample_format_metadata_interpretation(self):
        self.assertEqual(interpret_sample(0x0001, SAMPLE_FORMAT_TWOS_COMPLEMENT), 1)
        self.assertEqual(interpret_sample(0x7FFF, SAMPLE_FORMAT_TWOS_COMPLEMENT), 32767)
        self.assertEqual(interpret_sample(0x8000, SAMPLE_FORMAT_TWOS_COMPLEMENT), -32768)
        self.assertEqual(interpret_sample(0xFFFF, SAMPLE_FORMAT_TWOS_COMPLEMENT), -1)
        self.assertEqual(interpret_sample(0xFFFF, SAMPLE_FORMAT_UNSIGNED), 65535)
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
