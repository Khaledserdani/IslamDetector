import math
import unittest

from mono_spiral_geometry import MonoSpiral, square_loop_center_field_tesla


class MonoSpiralGeometryTests(unittest.TestCase):
    def setUp(self):
        self.coil = MonoSpiral()

    def test_reference_dimensions(self):
        self.assertEqual(self.coil.turns, 13)
        self.assertAlmostEqual(self.coil.outer_side_m, 0.350)
        self.assertAlmostEqual(self.coil.inner_side_m, 0.3212)
        self.assertAlmostEqual(self.coil.clear_gap_m, 0.0006)

    def test_reference_wire_length_and_resistance(self):
        self.assertAlmostEqual(self.coil.copper_path_length_m, 17.4512, places=6)
        self.assertAlmostEqual(self.coil.copper_resistance_20c_ohm, 1.0641, places=3)

    def test_mohan_planar_inductance_estimates_are_independent_methods(self):
        current_sheet = self.coil.mohan_current_sheet_inductance_h
        modified_wheeler = self.coil.mohan_modified_wheeler_inductance_h
        self.assertAlmostEqual(current_sheet, 175.8e-6, delta=0.5e-6)
        self.assertAlmostEqual(modified_wheeler, 149.2e-6, delta=0.5e-6)
        method_spread = abs(current_sheet - modified_wheeler) / current_sheet
        self.assertGreater(method_spread, 0.15)
        self.assertLess(method_spread, 0.20)

    def test_planar_inductance_estimates_reject_single_turn_fill_ratio(self):
        single_turn = MonoSpiral(turns=1)
        with self.assertRaises(ValueError):
            _ = single_turn.mohan_current_sheet_inductance_h
        with self.assertRaises(ValueError):
            _ = single_turn.mohan_modified_wheeler_inductance_h

    def test_continuous_spiral_has_all_turns_and_connectors(self):
        segments = self.coil.continuous_spiral_segments()
        self.assertEqual(len(segments), 4 * self.coil.turns + self.coil.turns - 1)
        for first, second in zip(segments, segments[1:]):
            self.assertEqual(first[1], second[0])

    def test_continuous_path_length_matches_copper_perimeter_sum(self):
        segments = self.coil.continuous_spiral_segments()
        length = sum(math.dist(start, end) for start, end in segments)
        self.assertAlmostEqual(length, self.coil.copper_path_length_m, places=12)

    def test_single_square_loop_centre_field_matches_analytic_solution(self):
        side = 0.35
        coil = MonoSpiral(outer_side_m=side, turns=1, pitch_m=0.0012)
        bx, by, bz = coil.magnetic_field_tesla(
            (0.0, 0.0, 0.0), segments_per_side=300
        )
        expected = square_loop_center_field_tesla(side)
        self.assertAlmostEqual(bx, 0.0, places=12)
        self.assertAlmostEqual(by, 0.0, places=12)
        self.assertLess(abs(bz - expected) / expected, 2e-4)

    def test_multi_turn_centre_field_is_finite_and_positive(self):
        bx, by, bz = self.coil.magnetic_field_tesla(
            (0.0, 0.0, 0.0), segments_per_side=100
        )
        self.assertAlmostEqual(bx, 0.0, places=12)
        self.assertAlmostEqual(by, 0.0, places=12)
        self.assertGreater(bz, 0.0)
        self.assertTrue(math.isfinite(bz))

    def test_rejects_pitch_smaller_than_wire(self):
        with self.assertRaises(ValueError):
            MonoSpiral(pitch_m=0.0005)


if __name__ == "__main__":
    unittest.main()
