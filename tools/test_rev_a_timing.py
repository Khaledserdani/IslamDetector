"""Arithmetic guard tests for the one-pulse, eight-window ADS8861 PIO schedule."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_C = ROOT / "firmware/rp2040_timing_test/src/ads8861_capture.c"
CAPTURE_PIO = ROOT / "firmware/rp2040_timing_test/pio/ads8861_capture.pio"
MAIN_C = ROOT / "firmware/rp2040_timing_test/src/main.c"


class RevATimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c_source = CAPTURE_C.read_text(encoding="utf-8")
        cls.pio_source = CAPTURE_PIO.read_text(encoding="utf-8")
        cls.main_source = MAIN_C.read_text(encoding="utf-8")

    def test_delay_words_unpack_to_eight_expected_loop_counts(self):
        words = [
            int(value, 16)
            for value in re.findall(r"0x([0-9A-Fa-f]{8})u", self.c_source)
        ]
        self.assertEqual(len(words), 4)
        counts = []
        for word in words:
            counts.extend((word & 0xFFF, (word >> 12) & 0xFFF))
        self.assertEqual(counts, [995, 178, 178, 678, 1178, 1678, 2178, 3178])

    def test_delay_loop_instruction_budget_hits_eight_nominal_windows(self):
        words = [
            int(value, 16)
            for value in re.findall(r"0x([0-9A-Fa-f]{8})u", self.c_source)
        ]
        counts = []
        for word in words:
            counts.extend((word & 0xFFF, (word >> 12) & 0xFFF))

        # First point: 2 input-sync + SET Y + OUT + (X+1) loop cycles.
        first_cycles = counts[0] + 5
        # Later points: 320 cycles conversion/readout/loop control,
        # OUT=1 cycle, and the delay loop (X+1).
        intervals = [322 + value for value in counts[1:]]
        cumulative = [first_cycles]
        for interval in intervals:
            cumulative.append(cumulative[-1] + interval)

        self.assertEqual(cumulative, [1000, 1500, 2000, 3000, 4500, 6500, 9000, 12500])
        self.assertEqual([cycles / 125 for cycles in cumulative],
                         [8, 12, 16, 24, 36, 52, 72, 100])

    def test_adc_conversion_and_serial_readout_fit_minimum_window_gap(self):
        # CONVST high: SET [31] + NOP [31] + NOP [31] = 96 cycles.
        conversion_cycles = 3 * 32
        # SCLK: IN [5] = 6 cycles high; JMP [6] = 7 cycles low.
        read_cycles = 16 * (6 + 7)
        # CONVST low instruction [11], SET X, NOP [1], JMP Y, OUT X.
        control_cycles = 12 + 1 + 2 + 1 + 1
        total_before_wait = conversion_cycles + read_cycles + control_cycles
        self.assertEqual(conversion_cycles, 96)
        self.assertEqual(read_cycles, 208)
        self.assertEqual(total_before_wait, 319)
        # First two gaps are 4 us = 500 cycles; at least 1 us remains.
        self.assertGreaterEqual(500 - total_before_wait, 125)

    def test_pio_is_one_pulse_triggered_and_keeps_capture_disabled_by_default(self):
        self.assertIn("wait 1 gpio 4", self.pio_source)
        self.assertIn("wait 0 gpio 4", self.pio_source)
        self.assertIn("set y, 7", self.pio_source)
        self.assertIn("out x, 12", self.pio_source)
        self.assertIn("in pins, 1 side 1 [5]", self.pio_source)
        self.assertIn("jmp x-- bitloop side 0 [6]", self.pio_source)
        self.assertIn("#define ENABLE_ADS8861_CAPTURE 0", self.main_source)
        self.assertIn("clock_get_hz(clk_sys) != ADS8861_SYS_CLOCK_HZ", self.c_source)


if __name__ == "__main__":
    unittest.main()
