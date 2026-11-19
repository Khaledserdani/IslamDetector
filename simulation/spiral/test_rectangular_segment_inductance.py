import math
import unittest

from rectangular_cross_section_gmd import rectangular_cross_section_gmd
from rectangular_segment_inductance import rectangular_segment_self_inductance


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

    def test_invalid_dimensions_and_order_are_rejected(self):
        for dims in ((0.0, 0.001, 0.001), (0.001, -0.001, 0.001),
                     (0.001, 0.001, float("inf"))):
            with self.assertRaises(ValueError):
                rectangular_segment_self_inductance(*dims)
        with self.assertRaises(ValueError):
            rectangular_segment_self_inductance(0.001, 0.001, 0.001, order=4)


if __name__ == "__main__":
    unittest.main()
