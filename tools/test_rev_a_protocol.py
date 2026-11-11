import unittest

from rev_a_protocol import (
    FLAG_SWEEP_COMPLETE,
    INVALID_CURRENT_MA,
    INVALID_TEMPERATURE_CENTI_C,
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
