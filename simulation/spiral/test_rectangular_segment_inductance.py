import math
import unittest

from rectangular_cross_section_gmd import rectangular_cross_section_gmd
from rectangular_segment_inductance import (
    rectangular_adjacent_segment_mutual_inductance,
    rectangular_parallel_segment_mutual_inductance,
    rectangular_segment_self_inductance,
)


class RectangularSegmentInductanceTests(unittest.TestCase):
    def test_segment_self_term_is_positive_and_finite(self):
        value = rectangular_segment_self_inductance(0.005, 0.0006, 0.0006)
        self.assertGreater(value, 0.0)
        self.assertTrue(math.isfinite(value))

    def test_inductance_scales_linearly_with_all_dimensions(self):
        base = rectangular_segment_self_inductance(0.005, 0.0006, 0.0004, order=96)
        scaled = rectangular_segment_self_inductance(0.015, 0.0018, 0.0012, order=96)
        self.assertAlmostEqual(scaled / base, 3.0, places=11)

    def test_cross_section_rotation_preserves_result(self):
        first = rectangular_segment_self_inductance(0.005, 0.0008, 0.0003, order=96)
        second = rectangular_segment_self_inductance(0.005, 0.0003, 0.0008, order=96)
        self.assertAlmostEqual(first, second, places=18)

    def test_quadrature_converges_for_thin_wire_section(self):
        medium = rectangular_segment_self_inductance(0.005, 0.0006, 0.0006, order=96)
        high = rectangular_segment_self_inductance(0.005, 0.0006, 0.0006, order=160)
        self.assertLess(abs(high - medium) / high, 1e-8)

    def test_long_segment_approaches_gmd_logarithmic_asymptote(self):
        length, width, height = 1.0, 0.0006, 0.0006
        actual = rectangular_segment_self_inductance(length, width, height, order=128)
        gmd = rectangular_cross_section_gmd(width, height, order=128)
        asymptote = 2e-7 * length * (math.log(2.0 * length / gmd) - 1.0)
        self.assertLess(abs(actual - asymptote) / actual, 5e-5)


    def test_adjacent_segment_mutual_is_reciprocal(self):
        first = rectangular_adjacent_segment_mutual_inductance(
            0.003, 0.002, 0.0006, 0.0006, order=96
        )
        second = rectangular_adjacent_segment_mutual_inductance(
            0.002, 0.003, 0.0006, 0.0006, order=96
        )
        self.assertGreater(first, 0.0)
        self.assertAlmostEqual(first, second, places=20)

    def test_splitting_a_straight_conductor_preserves_total_energy(self):
        whole = rectangular_segment_self_inductance(
            0.005, 0.0006, 0.0006, order=96
        )
        first_self = rectangular_segment_self_inductance(
            0.003, 0.0006, 0.0006, order=96
        )
        second_self = rectangular_segment_self_inductance(
            0.002, 0.0006, 0.0006, order=96
        )
        mutual = rectangular_adjacent_segment_mutual_inductance(
            0.003, 0.002, 0.0006, 0.0006, order=96
        )
        reconstructed = first_self + second_self + 2.0 * mutual
        self.assertAlmostEqual(reconstructed, whole, delta=1e-18)


    def test_parallel_mutual_reduces_to_adjacent_collinear_case(self):
        adjacent = rectangular_adjacent_segment_mutual_inductance(
            0.003, 0.002, 0.0006, 0.0006, order=96
        )
        general = rectangular_parallel_segment_mutual_inductance(
            0.003, 0.002, 0.0006, 0.0006,
            axial_offset_m=0.003, order=96
        )
        self.assertAlmostEqual(general, adjacent, delta=1e-18)

    def test_parallel_mutual_is_reciprocal_with_offsets_reversed(self):
        first = rectangular_parallel_segment_mutual_inductance(
            0.003, 0.002, 0.0006, 0.0004,
            transverse_offset_x_m=0.004,
            transverse_offset_y_m=-0.002,
            axial_offset_m=0.001,
            order=96,
        )
        reverse = rectangular_parallel_segment_mutual_inductance(
            0.002, 0.003, 0.0006, 0.0004,
            transverse_offset_x_m=-0.004,
            transverse_offset_y_m=0.002,
            axial_offset_m=-0.001,
            order=96,
        )
        self.assertGreater(first, 0.0)
        self.assertAlmostEqual(first, reverse, delta=1e-18)

    def test_parallel_mutual_matches_far_field_limit(self):
        a, b = 0.001, 0.0015
        dx, dy, offset = 0.10, 0.05, 0.03
        actual = rectangular_parallel_segment_mutual_inductance(
            a, b, 0.0006, 0.0006,
            transverse_offset_x_m=dx,
            transverse_offset_y_m=dy,
            axial_offset_m=offset,
            order=96,
        )
        center_z = offset + (b - a) / 2.0
        distance = math.sqrt(dx * dx + dy * dy + center_z * center_z)
        expected = 1e-7 * a * b / distance
        self.assertLess(abs(actual - expected) / expected, 0.002)

    def test_invalid_dimensions_and_order_are_rejected(self):
        for dims in ((0.0, 0.001, 0.001), (0.001, -0.001, 0.001),
                     (0.001, 0.001, float("inf"))):
            with self.assertRaises(ValueError):
                rectangular_segment_self_inductance(*dims)
        with self.assertRaises(ValueError):
            rectangular_segment_self_inductance(0.001, 0.001, 0.001, order=4)


if __name__ == "__main__":
    unittest.main()
