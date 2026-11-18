import math
import unittest

from mono_spiral_pi_model import (
    charge_injection_step,
    clamp_decay_time,
    pulse_current,
    rc_recovery_time,
    serial_recovery_budget,
    stored_energy,
    valid_window_mask,
    square_spiral_estimate,
    square_spiral_axis_field,
    low_side_clamp_stress,
    current_limit_response,
)


class MonoSpiralModelTests(unittest.TestCase):
    # Synthetic fixtures only: these values are not the project's measured coil.
    def test_pulse_current_matches_series_rl_equation(self):
        current = pulse_current(12.0, 1.6, 350e-6, 20e-6)
        expected = (12.0 / 1.6) * (1.0 - math.exp(-(20e-6 * 1.6 / 350e-6)))
        self.assertAlmostEqual(current, expected, places=12)

    def test_zero_resistance_limit(self):
        self.assertAlmostEqual(pulse_current(10.0, 0.0, 200e-6, 10e-6), 0.5)

    def test_zero_width_has_zero_current(self):
        self.assertEqual(pulse_current(12.0, 1.0, 300e-6, 0.0), 0.0)

    def test_energy(self):
        self.assertAlmostEqual(stored_energy(300e-6, 2.0), 0.0006)

    def test_clamp_decay_zero_resistance_limit(self):
        self.assertAlmostEqual(clamp_decay_time(300e-6, 0.0, 30.0, 2.0, 0.5), 15e-6)

    def test_clamp_decay_decreases_with_higher_clamp_voltage(self):
        slow = clamp_decay_time(300e-6, 1.0, 20.0, 2.0, 0.1)
        fast = clamp_decay_time(300e-6, 1.0, 40.0, 2.0, 0.1)
        self.assertLess(fast, slow)

    def test_invalid_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            pulse_current(12.0, -1.0, 300e-6, 20e-6)
        with self.assertRaises(ValueError):
            clamp_decay_time(300e-6, 1.0, 20.0, 1.0, 1.0)


    def test_charge_injection_uses_capacitive_divider(self):
        self.assertAlmostEqual(charge_injection_step(2e-12, 12.0, 100e-12), 0.24)

    def test_zero_feedthrough_has_no_voltage_step(self):
        self.assertEqual(charge_injection_step(0.0, 12.0, 100e-12), 0.0)

    def test_rc_recovery_time_matches_logarithmic_settling(self):
        expected = 10_000.0 * 1e-9 * math.log(1.0 / 0.001)
        self.assertAlmostEqual(rc_recovery_time(10_000.0, 1e-9, 1.0, 0.001), expected)

    def test_rc_recovery_is_zero_when_already_inside_error_band(self):
        self.assertEqual(rc_recovery_time(10_000.0, 1e-9, 0.0005, 0.001), 0.0)

    def test_serial_recovery_budget_sums_conservative_stages(self):
        self.assertAlmostEqual(serial_recovery_budget(1e-6, 2e-6, 3e-6, 4e-6, 0.29e-6, 0.5e-6), 10.79e-6)

    def test_recovery_budget_rejects_negative_stage(self):
        with self.assertRaises(ValueError):
            serial_recovery_budget(1e-6, -1e-6, 0.0, 0.0, 0.0)


    def test_valid_window_mask_skips_windows_before_recovery_budget(self):
        delays = [8e-6, 12e-6, 16e-6, 24e-6, 36e-6, 52e-6, 72e-6, 100e-6]
        self.assertEqual(valid_window_mask(delays, 8.1e-6), 0xFE)
        self.assertEqual(valid_window_mask(delays, 24e-6), 0xF8)

    def test_valid_window_mask_rejects_unsorted_delays(self):
        with self.assertRaises(ValueError):
            valid_window_mask([8e-6, 16e-6, 12e-6], 8e-6)

    def test_valid_window_mask_rejects_empty_windows(self):
        with self.assertRaises(ValueError):
            valid_window_mask([], 8e-6)


    def test_square_spiral_geometry_estimate(self):
        result = square_spiral_estimate(0.350, 13, 0.0006, 0.001, 0.0006)
        self.assertAlmostEqual(result["wire_length_m"], 17.1704, places=4)
        self.assertAlmostEqual(result["dcr_20c_ohm"], 1.04695, places=4)
        self.assertAlmostEqual(result["inductance_wheeler_h"] * 1e6, 141.47, places=1)
        self.assertAlmostEqual(result["inductance_current_sheet_h"] * 1e6, 159.56, places=1)

    def test_square_spiral_rejects_collapsed_inner_opening(self):
        with self.assertRaises(ValueError):
            square_spiral_estimate(0.350, 13, 0.0006, 0.020, 0.0006)

    def test_square_spiral_rejects_single_turn_and_oversized_copper(self):
        with self.assertRaises(ValueError):
            square_spiral_estimate(0.350, 1, 0.0006, 0.001, 0.0006)
        with self.assertRaises(ValueError):
            square_spiral_estimate(0.350, 13, 0.0006, 0.001, 0.0007)


    def test_square_spiral_axis_field_matches_single_loop_sum_at_center(self):
        field = square_spiral_axis_field(0.350, 13, 0.0006, 0.001, 1.5, 0.0)
        self.assertGreater(field, 0.0)
        self.assertLess(field, 200e-6)
        self.assertAlmostEqual(field * 1e6, 66.9013, places=3)

    def test_square_spiral_axis_field_decreases_with_depth(self):
        near = square_spiral_axis_field(0.350, 13, 0.0006, 0.001, 1.5, 0.0)
        far = square_spiral_axis_field(0.350, 13, 0.0006, 0.001, 1.5, 0.2)
        self.assertGreater(near, far)

    def test_square_spiral_axis_field_zero_current_is_zero(self):
        self.assertEqual(square_spiral_axis_field(0.350, 13, 0.0006, 0.001, 0.0, 0.1), 0.0)

    def test_clamp_decay_sensitivity_for_conservative_coil_scenario(self):
        slow = clamp_decay_time(180e-6, 0.9, 30.0, 3.0, 0.05)
        fast = clamp_decay_time(180e-6, 0.9, 60.0, 3.0, 0.05)
        self.assertAlmostEqual(slow * 1e6, 16.94, places=2)
        self.assertAlmostEqual(fast * 1e6, 8.65, places=2)
        self.assertGreater(slow, fast)


    def test_low_side_clamp_stress_energy_balance(self):
        result = low_side_clamp_stress(12.0, 85e-6, 0.9, 2.5445991387, 30.0, 100.0)
        self.assertAlmostEqual(result["initial_magnetic_energy_j"] * 1e3, 0.275187, places=5)
        self.assertAlmostEqual(result["clamp_energy_per_pulse_j"] * 1e3, 0.261938, places=5)
        self.assertAlmostEqual(result["coil_resistive_loss_per_pulse_j"] * 1e3, 0.013249, places=5)
        self.assertAlmostEqual(result["clamp_energy_per_pulse_j"] + result["coil_resistive_loss_per_pulse_j"], result["released_magnetic_energy_j"], places=12)

    def test_low_side_clamp_stress_predicts_ideal_vds_and_rate_power(self):
        one_hundred = low_side_clamp_stress(12.0, 85e-6, 0.9, 2.5445991387, 30.0, 100.0)
        one_thousand = low_side_clamp_stress(12.0, 85e-6, 0.9, 2.5445991387, 30.0, 1000.0)
        self.assertEqual(one_hundred["ideal_mosfet_vds_v"], 42.0)
        self.assertAlmostEqual(one_thousand["clamp_average_power_w"], 10.0 * one_hundred["clamp_average_power_w"], places=12)

    def test_low_side_clamp_stress_zero_coil_resistance(self):
        result = low_side_clamp_stress(12.0, 100e-6, 0.0, 2.0, 40.0, 100.0)
        self.assertAlmostEqual(result["clamp_energy_per_pulse_j"], 0.5 * 100e-6 * 4.0, places=12)
        self.assertEqual(result["coil_resistive_loss_per_pulse_j"], 0.0)

    def test_low_side_clamp_stress_rejects_invalid_current_or_rate(self):
        with self.assertRaises(ValueError):
            low_side_clamp_stress(12.0, 100e-6, 0.9, 1.0, 30.0, 100.0, 1.0)
        with self.assertRaises(ValueError):
            low_side_clamp_stress(12.0, 100e-6, 0.9, 1.0, 30.0, 0.0)

    def test_low_side_clamp_stress_is_numerically_stable_at_tiny_resistance(self):
        ideal = low_side_clamp_stress(12.0, 85e-6, 0.0, 2.0, 30.0, 100.0)
        tiny = low_side_clamp_stress(12.0, 85e-6, 1e-12, 2.0, 30.0, 100.0)
        self.assertAlmostEqual(tiny["clamp_energy_per_pulse_j"], ideal["clamp_energy_per_pulse_j"], places=14)
        self.assertGreaterEqual(tiny["coil_resistive_loss_per_pulse_j"], 0.0)


    def test_current_limit_response_includes_comparator_delay_overshoot(self):
        result = current_limit_response(12.0, 0.9, 50e-6, 3.0, 1e-6, 20e-6)
        self.assertAlmostEqual(result["threshold_crossing_s"] * 1e6, 14.1607, places=3)
        self.assertAlmostEqual(result["current_at_cutoff_a"], 3.194, places=2)
        self.assertTrue(result["comparator_cuts_before_timeout"])

    def test_current_limit_response_one_shot_remains_hard_upper_bound(self):
        result = current_limit_response(12.0, 0.9, 50e-6, 3.0, 10e-6, 20e-6)
        self.assertAlmostEqual(result["cutoff_time_s"], 20e-6, places=12)
        self.assertAlmostEqual(result["current_at_cutoff_a"], result["current_without_comparator_a"], places=12)
        self.assertFalse(result["comparator_cuts_before_timeout"])

    def test_current_limit_response_handles_threshold_never_reached(self):
        result = current_limit_response(12.0, 0.9, 180e-6, 3.0, 1e-6, 20e-6)
        self.assertFalse(result["threshold_reached_before_timeout"])
        self.assertEqual(result["cutoff_time_s"], 20e-6)

    def test_current_limit_response_rejects_invalid_parameters(self):
        with self.assertRaises(ValueError):
            current_limit_response(12.0, 0.9, 50e-6, 0.0, 1e-6, 20e-6)
        with self.assertRaises(ValueError):
            current_limit_response(12.0, 0.9, 50e-6, 3.0, 1e-6, 0.0)


if __name__ == "__main__":
    unittest.main()
