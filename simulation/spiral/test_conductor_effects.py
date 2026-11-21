"""Unit tests for frequency-scale helpers used in the PI conductor study."""
from __future__ import annotations

import math
import unittest

from conductor_effects import (
    first_order_edge_knee_hz,
    frequency_at_skin_depth_m,
    skin_depth_m,
)


class ConductorEffectsTests(unittest.TestCase):
    def test_copper_skin_depth_reference_values(self) -> None:
        self.assertAlmostEqual(skin_depth_m(1_000) * 1e3, 2.0897, delta=0.001)
        self.assertAlmostEqual(skin_depth_m(10_000) * 1e3, 0.6608, delta=0.001)
        self.assertAlmostEqual(skin_depth_m(100_000) * 1e3, 0.2090, delta=0.001)
        self.assertAlmostEqual(skin_depth_m(1_000_000) * 1e3, 0.0661, delta=0.001)

    def test_skin_depth_scales_with_inverse_sqrt_frequency(self) -> None:
        self.assertAlmostEqual(skin_depth_m(4_000), skin_depth_m(1_000) / 2.0)

    def test_radius_crossover_for_project_wire(self) -> None:
        crossover = frequency_at_skin_depth_m(0.30e-3)
        self.assertAlmostEqual(crossover, 48_521.6, delta=2.0)

    def test_edge_knee_is_only_the_035_over_rise_time_scale(self) -> None:
        self.assertAlmostEqual(first_order_edge_knee_hz(10e-6), 35_000.0)

    def test_rejects_nonpositive_and_nonfinite_inputs(self) -> None:
        for bad in (0.0, -1.0, math.inf, math.nan):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    skin_depth_m(bad)
                with self.assertRaises(ValueError):
                    frequency_at_skin_depth_m(bad)
                with self.assertRaises(ValueError):
                    first_order_edge_knee_hz(bad)


if __name__ == "__main__":
    unittest.main()
