import unittest

from mono_spiral_transient import Coil, Pulse, Target, simulate, window_peak_abs


class CoupledTransientTests(unittest.TestCase):
    def setUp(self):
        self.coil = Coil()
        self.pulse = Pulse(time_step_s=0.5e-6)

    def test_zero_mutual_coupling_gives_zero_rx(self):
        target = Target(0.05, 20e-6, 0.0)
        rows = simulate(self.coil, target, self.pulse)
        self.assertEqual(window_peak_abs(rows, 0.0, 1e-3), 0.0)

    def test_nonzero_coupling_gives_finite_rx(self):
        target = Target(0.05, 20e-6, 5e-6)
        rows = simulate(self.coil, target, self.pulse)
        peak = max(abs(row.get("rx_voltage_v", 0.0)) for row in rows)
        self.assertGreater(peak, 0.0)
        self.assertTrue(peak < float("inf"))

    def test_target_current_decays_after_isolation(self):
        target = Target(0.05, 20e-6, 5e-6)
        rows = simulate(self.coil, target, self.pulse)
        rx_rows = [r for r in rows if r["phase"] == 2.0]
        self.assertGreater(len(rx_rows), 2)
        self.assertGreater(abs(rx_rows[0]["target_current_a"]),
                           abs(rx_rows[-1]["target_current_a"]))

    def test_rejects_nonphysical_mutual_inductance(self):
        target = Target(0.05, 20e-6, 100e-6)
        with self.assertRaises(ValueError):
            simulate(self.coil, target, self.pulse)

    def test_rx_window_peak_is_zero_outside_rx_phase(self):
        target = Target(0.05, 20e-6, 5e-6)
        rows = simulate(self.coil, target, self.pulse)
        self.assertEqual(window_peak_abs(rows, 0.0, 1e-9), 0.0)


if __name__ == "__main__":
    unittest.main()
