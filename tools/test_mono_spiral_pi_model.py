import math
import unittest

from mono_spiral_pi_model import clamp_decay_time, pulse_current, stored_energy


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


if __name__ == "__main__":
    unittest.main()
