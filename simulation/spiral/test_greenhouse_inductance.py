import math
import unittest

from greenhouse_inductance import (
    MU0,
    _gauss_legendre_unit_interval,
    _uniform_disk_quadrature,
    calculate_mono_spiral_inductance,
    merge_collinear_segments,
    parallel_segment_mutual_inductance_h,
    round_wire_segment_self_inductance_h,
)
from mono_spiral_geometry import MonoSpiral


def direct_filament_mutual(segment_a, segment_b, samples=300):
    """Independent midpoint double integral of the Neumann kernel."""
    a0, a1 = segment_a
    b0, b1 = segment_b
    da = tuple(a1[i] - a0[i] for i in range(3))
    db = tuple(b1[i] - b0[i] for i in range(3))
    total = 0.0
    for i in range(samples):
        pa = tuple(a0[k] + (i + 0.5) * da[k] / samples for k in range(3))
        for j in range(samples):
            pb = tuple(b0[k] + (j + 0.5) * db[k] / samples for k in range(3))
            distance = math.dist(pa, pb)
            dot = sum(da[k] * db[k] for k in range(3))
            total += dot / (samples * samples * distance)
    return MU0 / (4.0 * math.pi) * total


class GreenhouseInductanceTests(unittest.TestCase):
    def setUp(self):
        self.geometry = MonoSpiral()

    def test_gauss_legendre_weights_integrate_constant(self):
        for order in (1, 2, 4, 8, 16):
            nodes = _gauss_legendre_unit_interval(order)
            self.assertAlmostEqual(sum(weight for _, weight in nodes), 1.0, places=14)

    def test_disk_quadrature_weights_are_area_normalized(self):
        points = _uniform_disk_quadrature(0.0003, 4, 16)
        self.assertEqual(len(points), 64)
        self.assertAlmostEqual(sum(point[2] for point in points), 1.0, places=14)

    def test_disk_quadrature_rejects_odd_angular_order(self):
        with self.assertRaises(ValueError):
            _uniform_disk_quadrature(0.0003, 4, 15)

    def test_round_wire_self_term_is_positive_and_finite(self):
        value = round_wire_segment_self_inductance_h(0.35, 0.0003)
        self.assertTrue(math.isfinite(value))
        self.assertGreater(value, 0.0)

    def test_round_wire_self_term_rejects_invalid_dimensions(self):
        for length, radius in ((0.0, 0.001), (0.1, 0.0), (-1.0, 0.001)):
            with self.assertRaises(ValueError):
                round_wire_segment_self_inductance_h(length, radius)

    def test_merge_collinear_contiguous_same_direction_segments(self):
        pieces = (
            ((0.0, 0.0, 0.0), (0.4, 0.0, 0.0)),
            ((0.4, 0.0, 0.0), (1.0, 0.0, 0.0)),
        )
        merged = merge_collinear_segments(pieces)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0], (pieces[0][0], pieces[1][1]))

    def test_merge_does_not_join_reversed_or_noncollinear_segments(self):
        pieces = (
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
            ((1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        )
        self.assertEqual(len(merge_collinear_segments(pieces)), 3)

    def test_merge_rejects_zero_length_segments(self):
        with self.assertRaises(ValueError):
            merge_collinear_segments((((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),))

    def test_geometry_reduces_64_raw_segments_to_52_physical_straights(self):
        raw = self.geometry.continuous_spiral_segments()
        merged = merge_collinear_segments(raw)
        self.assertEqual(len(raw), 64)
        self.assertEqual(len(merged), 52)

    def test_merge_preserves_path_length_and_connectivity(self):
        raw = self.geometry.continuous_spiral_segments()
        merged = merge_collinear_segments(raw)
        raw_length = sum(math.dist(a, b) for a, b in raw)
        merged_length = sum(math.dist(a, b) for a, b in merged)
        self.assertAlmostEqual(raw_length, 17.4512, places=10)
        self.assertAlmostEqual(merged_length, raw_length, places=12)
        for first, second in zip(merged, merged[1:]):
            self.assertLessEqual(math.dist(first[1], second[0]), 1e-12)

    def test_parallel_mutual_matches_independent_midpoint_neumann_integral(self):
        first = ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0))
        second = ((0.02, 0.02, 0.0), (0.10, 0.02, 0.0))
        actual = parallel_segment_mutual_inductance_h(
            first, second, 0.0003, radial_order=4, angular_order=16
        )
        reference = direct_filament_mutual(first, second, samples=300)
        self.assertLess(abs(actual - reference) / reference, 2e-4)

    def test_parallel_mutual_is_reciprocal(self):
        first = ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0))
        second = ((0.02, 0.02, 0.0), (0.10, 0.02, 0.0))
        ab = parallel_segment_mutual_inductance_h(first, second, 0.0003)
        ba = parallel_segment_mutual_inductance_h(second, first, 0.0003)
        self.assertAlmostEqual(ab, ba, delta=1e-15)

    def test_reversing_one_segment_reverses_mutual_sign(self):
        first = ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0))
        second = ((0.02, 0.02, 0.0), (0.10, 0.02, 0.0))
        reversed_second = (second[1], second[0])
        positive = parallel_segment_mutual_inductance_h(first, second, 0.0003)
        negative = parallel_segment_mutual_inductance_h(first, reversed_second, 0.0003)
        self.assertAlmostEqual(positive, -negative, delta=1e-15)

    def test_parallel_mutual_rejects_touching_wire_sections(self):
        first = ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0))
        second = ((0.0, 0.0006, 0.0), (0.1, 0.0006, 0.0))
        with self.assertRaises(ValueError):
            parallel_segment_mutual_inductance_h(first, second, 0.0003)

    def test_parallel_mutual_rejects_nonparallel_segments(self):
        first = ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0))
        second = ((0.0, 0.02, 0.0), (0.0, 0.1, 0.0))
        with self.assertRaises(ValueError):
            parallel_segment_mutual_inductance_h(first, second, 0.0003)

    def test_reference_coil_report_has_expected_pair_counts(self):
        report = calculate_mono_spiral_inductance(self.geometry)
        self.assertEqual(report.segment_count, 52)
        self.assertEqual(report.parallel_pair_count, 650)
        self.assertEqual(report.perpendicular_pair_count, 676)
        self.assertAlmostEqual(report.path_length_m, 17.4512, places=10)

    def test_reference_coil_report_reproduces_independent_diagnostic(self):
        report = calculate_mono_spiral_inductance(
            self.geometry, radial_order=4, angular_order=16
        )
        self.assertAlmostEqual(report.self_sum_h * 1e6, 24.307039, places=5)
        self.assertAlmostEqual(report.mutual_positive_h * 1e6, 84.474332, places=5)
        self.assertAlmostEqual(report.mutual_negative_h * 1e6, -10.594241, places=5)
        self.assertAlmostEqual(report.inductance_h * 1e6, 172.067221, places=5)

    def test_increasing_quadrature_order_is_stable_for_reference_coil(self):
        coarse = calculate_mono_spiral_inductance(
            self.geometry, radial_order=2, angular_order=8
        )
        fine = calculate_mono_spiral_inductance(
            self.geometry, radial_order=4, angular_order=16
        )
        relative_change = abs(fine.inductance_h - coarse.inductance_h) / fine.inductance_h
        self.assertLess(relative_change, 1e-6)

    def test_calculator_rejects_invalid_wire_diameter(self):
        with self.assertRaises(ValueError):
            calculate_mono_spiral_inductance(self.geometry, wire_diameter_m=0.0)


if __name__ == "__main__":
    unittest.main()
