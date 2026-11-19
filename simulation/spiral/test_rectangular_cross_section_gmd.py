import unittest

from rectangular_cross_section_gmd import rectangular_cross_section_gmd


class RectangularCrossSectionGmdTests(unittest.TestCase):
    def test_reference_thin_rectangle(self):
        # Independent high-order quadrature reference for a 5 mm x 1 mm section.
        value = rectangular_cross_section_gmd(0.005, 0.001, order=128)
        self.assertAlmostEqual(value, 0.0013421195215, delta=2e-12)

    def test_square_section_reference(self):
        value = rectangular_cross_section_gmd(0.001, 0.001, order=128)
        self.assertAlmostEqual(value, 0.0004470491557, delta=2e-12)

    def test_gmd_scales_linearly(self):
        base = rectangular_cross_section_gmd(0.002, 0.001, order=96)
        scaled = rectangular_cross_section_gmd(0.010, 0.005, order=96)
        self.assertAlmostEqual(scaled / base, 5.0, places=11)

    def test_gmd_is_symmetric_in_dimensions(self):
        first = rectangular_cross_section_gmd(0.005, 0.001, order=96)
        second = rectangular_cross_section_gmd(0.001, 0.005, order=96)
        self.assertAlmostEqual(first, second, places=14)

    def test_quadrature_order_converges(self):
        medium = rectangular_cross_section_gmd(0.002, 0.001, order=80)
        high = rectangular_cross_section_gmd(0.002, 0.001, order=128)
        self.assertLess(abs(high - medium) / high, 1e-8)

    def test_invalid_dimensions_and_order_are_rejected(self):
        for width, height in ((0.0, 0.001), (-0.001, 0.001), (float("inf"), 0.001)):
            with self.assertRaises(ValueError):
                rectangular_cross_section_gmd(width, height)
        with self.assertRaises(ValueError):
            rectangular_cross_section_gmd(0.001, 0.001, order=4)


if __name__ == "__main__":
    unittest.main()
