#!/usr/bin/env python3
"""Regression checks for the first-order PI sanity models.

Run from repository root:
    python -m unittest discover -s tools -p 'test_*.py'
"""

import unittest

from pi_frontend_sanity import bucking_gyrator, coil_current, time_to_current
from pi_tx_clamp_model import simulate


class FrontendSanityTests(unittest.TestCase):
    def test_300us_pulse_exceeds_5a_for_shorter_coils(self):
        self.assertGreater(coil_current(12.0, 1.5, 180e-6, 300e-6), 7.3)
        self.assertGreater(coil_current(12.0, 1.5, 400e-6, 300e-6), 5.3)

    def test_time_to_5a_scales_with_inductance(self):
        t180 = time_to_current(12.0, 1.5, 180e-6, 5.0)
        t400 = time_to_current(12.0, 1.5, 400e-6, 5.0)
        self.assertAlmostEqual(t180 * 1e6, 117.7, delta=0.5)
        self.assertAlmostEqual(t400 * 1e6, 261.6, delta=0.5)

    def test_published_gyrator_reference_values(self):
        lvar, tau = bucking_gyrator(250e3, 100.0, 100e-12)
        self.assertAlmostEqual(lvar * 1e3, 2.5, places=6)
        self.assertAlmostEqual(tau * 1e6, 25.0, places=6)


class ClampModelTests(unittest.TestCase):
    def test_conservative_vbrmax_clamp_estimate(self):
        r5 = simulate(inductance_uH=300.0, current_A=5.0)
        r6 = simulate(inductance_uH=300.0, current_A=6.0)
        self.assertAlmostEqual(r5.peak_mosfet_vds_V, 138.2, delta=1.0)
        self.assertAlmostEqual(r6.peak_mosfet_vds_V, 139.6, delta=1.0)
        self.assertLess(abs(r5.energy_error_percent), 0.2)
        self.assertLess(abs(r6.energy_error_percent), 0.2)

    def test_flyback_decay_increases_with_inductance(self):
        short = simulate(inductance_uH=180.0, current_A=5.0)
        long = simulate(inductance_uH=400.0, current_A=5.0)
        self.assertLess(short.decay_us, long.decay_us)
        self.assertGreater(long.initial_energy_mJ, short.initial_energy_mJ)


if __name__ == "__main__":
    unittest.main()
