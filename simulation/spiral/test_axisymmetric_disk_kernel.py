import math
import unittest

from axisymmetric_disk_kernel import (
    azimuthal_cosine_kernel_per_m,
    azimuthally_integrated_neumann_kernel_per_m,
    finite_cell_inductance_integrand_h_per_m2,
)


class AxisymmetricDiskKernelTests(unittest.TestCase):
    def test_double_azimuth_kernel_is_two_pi_times_relative_angle_kernel(self):
        args = (0.012, 0.003, 0.007, 0.021)
        single = azimuthal_cosine_kernel_per_m(*args)
        double = azimuthally_integrated_neumann_kernel_per_m(*args)
        self.assertAlmostEqual(double, 2.0 * math.pi * single, places=14)

    def test_kernel_is_symmetric(self):
        ab = azimuthally_integrated_neumann_kernel_per_m(
            0.012, 0.003, 0.007, 0.021
        )
        ba = azimuthally_integrated_neumann_kernel_per_m(
            0.007, 0.021, 0.012, 0.003
        )
        self.assertAlmostEqual(ab, ba, delta=1.0e-12 * abs(ab))

    def test_far_separation_matches_leading_dipole_kernel(self):
        ra, rb, dz = 0.010, 0.015, 1.5
        actual = azimuthally_integrated_neumann_kernel_per_m(ra, 0.0, rb, dz)
        a = ra * ra + rb * rb + dz * dz
        b = 2.0 * ra * rb
        expected = math.pi * math.pi * b / (a ** 1.5)
        self.assertLess(abs(actual - expected) / expected, 1.0e-6)

    def test_axis_point_has_zero_azimuthal_coupling(self):
        self.assertEqual(
            azimuthally_integrated_neumann_kernel_per_m(0.0, 0.0, 0.01, 0.02),
            0.0,
        )

    def test_coincident_meridional_points_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "singular"):
            azimuthally_integrated_neumann_kernel_per_m(0.01, 0.02, 0.01, 0.02)

    def test_finite_cell_density_is_positive_and_finite_off_diagonal(self):
        value = finite_cell_inductance_integrand_h_per_m2(
            0.012, 0.003, 0.007, 0.021, 1.0e-6, 2.0e-6
        )
        self.assertTrue(math.isfinite(value))
        self.assertGreater(value, 0.0)

    def test_invalid_cell_area_is_rejected(self):
        with self.assertRaises(ValueError):
            finite_cell_inductance_integrand_h_per_m2(
                0.012, 0.003, 0.007, 0.021, 0.0, 2.0e-6
            )


if __name__ == "__main__":
    unittest.main()
