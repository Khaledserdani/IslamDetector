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
        # Later points: 319 cycles through conversion/readout, then JMP Y and OUT
        # add 2 cycles; the delay loop adds (X+1) cycles.
        intervals = [322 + value for value in counts[1:]]
        cumulative = [first_cycles]
        for interval in intervals:
            cumulative.append(cumulative[-1] + interval)

        self.assertEqual(cumulative, [1000, 1500, 2000, 3000, 4500, 6500, 9000, 12500])
        self.assertEqual([cycles / 125 for cycles in cumulative],
                         [8, 12, 16, 24, 36, 52, 72, 100])

    def test_convst_width_and_sclk_budget(self):
        # CONVST HIGH: SET [15] plus five NOP [15] = 96 cycles.
        convst_high_cycles = 6 * 16
        self.assertEqual(convst_high_cycles, 96)
        self.assertEqual(convst_high_cycles * 8, 768)  # ns at 125 MHz
        self.assertGreater(768, 710)  # ADS8861 t_conv max, ns

        # One SCLK period: IN [5] = 6 cycles high; JMP [6] = 7 low.
        sclk_period_cycles = 6 + 7
        self.assertEqual(sclk_period_cycles, 13)
        self.assertAlmostEqual(125_000_000 / sclk_period_cycles, 9_615_384.615, places=2)
        self.assertGreaterEqual(6 / 13, 0.45)
        self.assertGreaterEqual(7 / 13, 0.45)
        self.assertIn("set pins, 1 side 0 [15]", self.pio_source)
        self.assertEqual(self.pio_source.count("nop side 0 [15]"), 5)

    def test_capture_shift_width_matches_one_adc_word(self):
        self.assertIn("sm_config_set_in_shift(&capture_config, false, true, 16u)", self.c_source)
        self.assertIn("in pins, 1 side 1 [5]", self.pio_source)
        self.assertIn("uint32_t capture_buffer[ADS8861_SWEEP_SAMPLES]", self.c_source)
        self.assertIn("(uint16_t)(capture_buffer[i] & 0xFFFFu)", self.c_source)

    def test_first_dout_sample_waits_for_msb_valid(self):
        # CONVST-low instruction [11] = 12 cycles, SET X = 1,
        # NOP [1] = 2 cycles; first SCLK edge follows after 15 cycles.
        first_sclk_delay_cycles = 12 + 1 + 2
        self.assertEqual(first_sclk_delay_cycles, 15)
        self.assertEqual(first_sclk_delay_cycles * 8, 120)  # ns at 125 MHz
        self.assertGreater(120, 12.3)  # ADS8861 t_d-CNV-DO max, ns
        self.assertIn("set pins, 0 side 0 [11]", self.pio_source)
        self.assertIn("nop side 0 [1]", self.pio_source)

    def test_adc_conversion_and_serial_readout_fit_minimum_window_gap(self):
        # CONVST high: SET [15] + five NOP [15] instructions = 96 cycles.
        conversion_cycles = 6 * 16
        # SCLK: IN [5] = 6 cycles high; JMP [6] = 7 cycles low.
        read_cycles = 16 * (6 + 7)
        # CONVST low instruction [11], SET X, NOP [1], JMP Y, OUT X.
        control_cycles = 12 + 1 + 2 + 1 + 1
        total_before_wait = conversion_cycles + read_cycles + control_cycles
        self.assertEqual(conversion_cycles, 96)
        self.assertEqual(read_cycles, 208)
        self.assertEqual(total_before_wait, 321)
        # First two gaps are 4 us = 500 cycles; at least 1 us remains.
        self.assertEqual(500 - total_before_wait, 179)

    def test_pio_is_one_pulse_triggered_and_keeps_capture_disabled_by_default(self):
        self.assertIn("wait 1 gpio 4", self.pio_source)
        self.assertIn("wait 0 gpio 4", self.pio_source)
        self.assertIn("set y, 7", self.pio_source)
        self.assertIn("out x, 12", self.pio_source)
        self.assertIn("in pins, 1 side 1 [5]", self.pio_source)
        self.assertIn("jmp x-- bitloop side 0 [6]", self.pio_source)
        self.assertIn("#define ENABLE_ADS8861_CAPTURE 0", self.main_source)
        self.assertIn("clock_get_hz(clk_sys) != ADS8861_SYS_CLOCK_HZ", self.c_source)
        self.assertIn("pio_encode_pull(false, true)", self.c_source)
        self.assertIn("sm_config_set_out_shift(&capture_config, true, true, 24u)", self.c_source)
        self.assertIn("dma_channel_configure", self.c_source)
        self.assertIn("pio_get_dreq(pio, sm, false)", self.c_source)
        self.assertNotIn("sm_config_set_fifo_join(", self.c_source)

    def test_pwm_sample_marker_offsets_match_tx_falling_edge(self):
        # GP4 carries the 20 us logic-only TX pulse; GP5 falls at
        # (20 us + requested delay), so its falling edge is delay-relative
        # to the GP4 falling edge. At 125 MHz / 20, one PWM tick is 160 ns.
        delays = [8, 12, 16, 24, 36, 52, 72, 100]
        pulse_us = 20
        pwm_tick_hz = 125_000_000 / 20
        ticks_per_us = pwm_tick_hz / 1_000_000
        marker_ticks = [round((pulse_us + delay) * ticks_per_us) for delay in delays]
        self.assertEqual(marker_ticks, [175, 200, 225, 275, 350, 450, 575, 750])
        self.assertTrue(all(tick < 62499 for tick in marker_ticks))
        self.assertIn("#define TX_TEST_PIN       4u", self.main_source)
        self.assertIn("#define SAMPLE_MARKER_PIN 5u", self.main_source)
        self.assertIn("#define PWM_WRAP_VALUE    62499u", self.main_source)
        self.assertIn("pwm_config_set_clkdiv(&config, pwm_divider)", self.main_source)
        self.assertIn("pwm_set_chan_level(slice_num, PWM_CHAN_A, pulse_ticks)", self.main_source)
        self.assertIn("pwm_set_chan_level(slice_num, PWM_CHAN_B, sample_compare_ticks[0])", self.main_source)
        self.assertIn("START_PULSE_US + sample_delays_us[i]", self.main_source)

    def test_pwm_compare_pipeline_is_primed_without_startup_duplicate(self):
        # RP2040 CC is double-buffered: writes while running latch at the
        # next wrap. Prime profile 1 immediately after enabling PWM so the
        # first wrap switches from profile 0 to profile 1, not one wrap later.
        self.assertIn("static volatile uint8_t active_profile_index = 0u;", self.main_source)
        self.assertIn("static volatile uint8_t queued_profile_index = 1u;", self.main_source)
        enable_at = self.main_source.index("pwm_set_enabled(slice_num, true);")
        prime_at = self.main_source.index(
            "pwm_set_chan_level(slice_num, PWM_CHAN_B, sample_compare_ticks[1]);",
            enable_at,
        )
        self.assertLess(enable_at, prime_at)
        self.assertIn("active_profile_index = queued_profile_index;", self.main_source)
        self.assertIn("sample_compare_ticks[queued_profile_index]", self.main_source)

        active, queued = 0, 1
        observed = [active]
        for _ in range(8):
            active = queued
            queued = (active + 1) & 0x07
            observed.append(active)
        self.assertEqual(observed, [0, 1, 2, 3, 4, 5, 6, 7, 0])


if __name__ == "__main__":
    unittest.main()
