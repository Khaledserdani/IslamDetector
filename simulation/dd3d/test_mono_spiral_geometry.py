#!/usr/bin/env python3
"""Tests for parametric Mono Spiral geometry candidates."""
import math
import unittest
import numpy as np

from mono_spiral_geometry import build_spiral, rounded_rectangle_loop
from filament_model import path_length_m


class MonoSpiralGeometryTests(unittest.TestCase):
    def test_rounded_rectangle_perimeter_matches_analytic_value(self):
        w, h, r = 0.30, 0.28, 0.04
        path = rounded_rectangle_loop(w, h, r, arc_step_deg=0.25)
        exact = 2 * (w + h - 4 * r) + 2 * math.pi * r
        self.assertLess(abs(path_length_m(path) - exact), 2e-7)

    def test_circle_spiral_is_one_open_continuous_path(self):
        path, report = build_spiral(
            "circle", turns=5, pitch_m=0.004,
            insulation_outer_diameter_m=0.001,
            min_surface_clearance_m=0.002,
            arc_step_deg=1.0, outer_radius_m=0.16)
        self.assertEqual(report["turns"], 5)
        self.assertTrue(report["path_is_open"])
        self.assertAlmostEqual(path_length_m(path), report["centerline_length_m"], delta=1e-10)\n        self.assertGreater(path_length_m(path), sum(report["turn_lengths_m"]))
        self.assertEqual(path.shape[1], 3)
        self.assertGreater(report["path_vertices"], 5 * 100)

    def test_rounded_square_spiral_generates_nested_turns(self):
        path, report = build_spiral(
            "rounded-square", turns=6, pitch_m=0.004,
            insulation_outer_diameter_m=0.001,
            min_surface_clearance_m=0.002,
            arc_step_deg=1.0, outer_width_m=0.32,
            outer_height_m=0.32, outer_corner_radius_m=0.025)
        self.assertEqual(len(report["per_turn"]), 6)
        self.assertAlmostEqual(report["per_turn"][1]["width_m"], 0.312)
        self.assertAlmostEqual(report["per_turn"][1]["corner_radius_m"], 0.025)\n        self.assertAlmostEqual(path_length_m(path), report["centerline_length_m"], delta=1e-10)\n        self.assertGreater(report["centerline_length_m"], 6.0)
        self.assertTrue(np.isfinite(path).all())

    def test_rejects_insufficient_turn_clearance(self):
        with self.assertRaises(ValueError):
            build_spiral("circle", 4, 0.001, 0.001, 0.0005, 2.0,
                         outer_radius_m=0.15)

    def test_rejects_collapsed_inner_turn(self):
        with self.assertRaises(ValueError):
            build_spiral("circle", 20, 0.005, 0.001, 0.001, 2.0,
                         outer_radius_m=0.05)

    def test_rejects_missing_shape_parameters(self):
        with self.assertRaises(ValueError):
            build_spiral("rounded-square", 4, 0.004, 0.001, 0.001, 2.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
