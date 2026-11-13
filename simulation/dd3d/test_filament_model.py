#!/usr/bin/env python3
"""Numerical verification tests for the 3D filament reference kernel."""
import unittest
import math
import numpy as np
from filament_model import circular_loop, circular_loop_axis_field, field_at_points, mutual_inductance, path_length_m

class FilamentModelTests(unittest.TestCase):
    def test_circular_loop_axis_field_converges_to_analytic_solution(self):
        radius, z = 0.16, 0.10
        exact = circular_loop_axis_field(radius, z)
        errors = []
        for segments in (100, 200, 400, 800):
            actual = field_at_points(circular_loop(radius, segments), [[0.0, 0.0, z]])[0, 2]
            errors.append(abs(actual - exact) / exact)
        self.assertLess(errors[-1], 1e-5)
        self.assertTrue(all(errors[i + 1] < errors[i] for i in range(len(errors) - 1)))

    def test_circular_path_length_matches_analytic_circumference(self):
        radius = 0.16
        path = circular_loop(radius, 2048)
        actual = path_length_m(path)
        exact = 2.0 * math.pi * radius
        self.assertLess(abs(actual - exact) / exact, 1e-6)

    def test_field_scales_with_current_and_turns(self):
        loop = circular_loop(0.12, 512)
        p = [[0.0, 0.0, 0.04]]
        one = field_at_points(loop, p, current_a=1.0, turns=1)
        scaled = field_at_points(loop, p, current_a=2.5, turns=20)
        np.testing.assert_allclose(scaled, one * 50.0, rtol=1e-12, atol=1e-18)

    def test_mutual_inductance_is_reciprocal(self):
        tx = circular_loop(0.12, 256, z_m=0.0)
        rx = circular_loop(0.10, 256, z_m=0.015)
        mab = mutual_inductance(tx, rx, turns_a=20, turns_b=30)
        mba = mutual_inductance(rx, tx, turns_a=30, turns_b=20)
        self.assertGreater(mab, 0.0)
        self.assertAlmostEqual(mab, mba, delta=abs(mab) * 1e-12)

    def test_reversing_one_loop_reverses_mutual_inductance_sign(self):
        tx = circular_loop(0.12, 256, z_m=0.0)
        rx = circular_loop(0.10, 256, z_m=0.015)
        forward = mutual_inductance(tx, rx)
        reverse = mutual_inductance(tx, rx[::-1])
        self.assertAlmostEqual(forward, -reverse, delta=abs(forward) * 1e-12)

    def test_rejects_non_finite_geometry(self):
        with self.assertRaises(ValueError):
            field_at_points([[0,0,0],[1,0,0],[1,1,0],[float("nan"),0,0]], [[0,0,1]])

    def test_rejects_intersecting_filaments(self):
        a = [[-1,0,0],[1,0,0],[1,1,0],[-1,1,0],[-1,0,0]]
        b = [[0,-1,0],[0,1,0],[1,1,1],[1,-1,1],[0,-1,0]]
        with self.assertRaises(ValueError):
            mutual_inductance(a, b)

if __name__ == "__main__":
    unittest.main(verbosity=2)
