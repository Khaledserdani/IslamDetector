import math
import unittest

from transient_circuit import RLCInputError, simulate_series_rlc


class SeriesRLCLabTests(unittest.TestCase):
    def test_ac_resonance_matches_series_resistance(self):
        r, l, c = 12.0, 0.01, 100e-6
        f0 = 1.0 / (2.0 * math.pi * math.sqrt(l*c))
        result = simulate_series_rlc({
            "mode": "ac", "resistance_ohm": r, "inductance_h": l,
            "capacitance_f": c, "source_voltage_v": 12.0, "frequency_hz": f0,
        })
        self.assertAlmostEqual(result["impedance_magnitude_ohm"], r, places=7)
        self.assertAlmostEqual(result["current_rms_a"], 1.0, places=7)
        self.assertAlmostEqual(result["power_factor"], 1.0, places=7)

    def test_ac_inductive_and_capacitive_phase_signs(self):
        base = {"mode": "ac", "resistance_ohm": 10.0, "inductance_h": 0.1,
                "capacitance_f": 1e-3, "source_voltage_v": 5.0}
        low = simulate_series_rlc(dict(base, frequency_hz=1.0))
        high = simulate_series_rlc(dict(base, frequency_hz=100.0))
        self.assertGreater(low["current_phase_deg"], 0.0)
        self.assertLess(high["current_phase_deg"], 0.0)

    def test_transient_dc_step_approaches_zero_current_and_source_cap_voltage(self):
        result = simulate_series_rlc({
            "mode": "transient", "resistance_ohm": 100.0,
            "inductance_h": 0.01, "capacitance_f": 1e-3,
            "source_voltage_v": 5.0, "duration_s": 0.5,
            "time_step_s": 1e-5, "initial_current_a": 0.0,
            "initial_capacitor_voltage_v": 0.0,
        })
        self.assertAlmostEqual(result["current_a"][-1], 0.0, places=4)
        self.assertAlmostEqual(result["capacitor_voltage_v"][-1], 5.0, places=3)
        self.assertTrue(result["verified_numerically"])

    def test_rejects_excessive_sample_count_and_ideal_resonance(self):
        with self.assertRaises(RLCInputError):
            simulate_series_rlc({
                "mode": "transient", "resistance_ohm": 1.0,
                "inductance_h": 1.0, "capacitance_f": 1.0,
                "source_voltage_v": 1.0, "duration_s": 20.0,
                "time_step_s": 1e-9, "initial_current_a": 0.0,
                "initial_capacitor_voltage_v": 0.0,
            })
        with self.assertRaises(RLCInputError):
            simulate_series_rlc({
                "mode": "ac", "resistance_ohm": 0.0,
                "inductance_h": 0.01, "capacitance_f": 100e-6,
                "source_voltage_v": 1.0,
                "frequency_hz": 1.0/(2.0*math.pi*math.sqrt(0.01*100e-6)),
            })


if __name__ == "__main__":
    unittest.main()
