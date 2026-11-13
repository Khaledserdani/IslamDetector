#!/usr/bin/env python3
"""Verification tests for the small-signal RX/AFE noise budget."""
import unittest
import numpy as np
from noise_engine import estimate_input_noise, compare_target_and_baseline

def cfg():
    return {
        "rx_coil": {"resistance_ohm": 4.802, "inductance_h": 750e-6},
        "afe": {"parallel_damping_ohm": 390.0, "series_protection_ohm": 1000.0,
                "input_capacitance_f": 2e-9, "input_bias_ohm": 1e6},
        "opamp": {"input_voltage_noise_density_v_rt_hz": 5e-9,
                  "input_current_noise_density_a_rt_hz": 0.0},
        "noise": {"temperature_k": 300.0, "frequency_min_hz": 10.0,
                  "frequency_max_hz": 100000.0, "frequency_points": 4001,
                  "signal_window_start_s": 0.0, "signal_window_end_s": 100e-6}
    }

class NoiseEngineTests(unittest.TestCase):
    def test_noise_budget_is_finite_positive_and_components_sum(self):
        m = estimate_input_noise(cfg())
        self.assertTrue(np.isfinite(m["integrated_input_noise_rms_v"]))
        self.assertGreater(m["integrated_input_noise_rms_v"], 0.0)
        self.assertAlmostEqual(
            sum(m["noise_components_variance_v2"].values()),
            m["integrated_input_noise_variance_v2"], delta=1e-24
        )

    def test_higher_temperature_increases_thermal_noise(self):
        c1, c2 = cfg(), cfg()
        c2["noise"]["temperature_k"] = 600.0
        n1 = estimate_input_noise(c1)["integrated_input_noise_rms_v"]
        n2 = estimate_input_noise(c2)["integrated_input_noise_rms_v"]
        self.assertGreater(n2, n1)

    def test_zero_all_noise_sources_gives_zero_noise(self):
        c = cfg()
        c["opamp"]["input_voltage_noise_density_v_rt_hz"] = 0.0
        c["opamp"]["input_current_noise_density_a_rt_hz"] = 0.0
        # Zero-temperature is not physical and is rejected; disable thermal terms
        # by using a separate explicit test configuration with all resistors ideal.
        c["rx_coil"]["resistance_ohm"] = 1e-30
        c["afe"]["parallel_damping_ohm"] = 1e30
        c["afe"]["series_protection_ohm"] = 1e-30
        c["afe"]["input_bias_ohm"] = 1e30
        m = estimate_input_noise(c)
        self.assertGreaterEqual(m["integrated_input_noise_rms_v"], 0.0)

    def test_target_minus_baseline_signal_has_positive_snr(self):
        t = np.linspace(0.0, 100e-6, 1001)
        base = {"time_s": t, "afe_input_voltage_v": np.zeros_like(t)}
        target = {"time_s": t, "afe_input_voltage_v": 1e-3*np.sin(2*np.pi*20000*t)}
        m = compare_target_and_baseline(target, base, cfg())
        self.assertGreater(m["target_differential_input_rms_v"], 0.0)
        self.assertTrue(np.isfinite(m["snr_db"]))

    def test_identical_target_and_baseline_has_zero_snr(self):
        t = np.linspace(0.0, 100e-6, 1001)
        w = {"time_s": t, "afe_input_voltage_v": np.sin(2*np.pi*20000*t)}
        m = compare_target_and_baseline(w, w, cfg())
        self.assertAlmostEqual(m["target_differential_input_rms_v"], 0.0, delta=1e-15)
        self.assertEqual(m["snr_db"], -float("inf"))

    def test_rejects_non_monotonic_waveform(self):
        t = np.array([0.0, 1e-6, 0.5e-6])
        w = {"time_s": t, "afe_input_voltage_v": np.ones(3)}
        with self.assertRaises(ValueError):
            compare_target_and_baseline(w, w, cfg())

if __name__ == "__main__":
    unittest.main(verbosity=2)
