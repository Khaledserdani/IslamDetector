import math
import unittest

from axisymmetric_disk_cells import (
    MeridionalCell,
    converged_mutual_inductance_h,
    mutual_inductance_h,
    resistance_matrix_ohm,
)


class FiniteCellAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.a = MeridionalCell(0.010, 0.012, -0.001, 0.001)
        self.b = MeridionalCell(0.016, 0.018, 0.002, 0.004)

    def test_mutual_inductance_is_symmetric(self):
        ab = mutual_inductance_h(self.a, self.b, order=5)
        ba = mutual_inductance_h(self.b, self.a, order=5)
        self.assertAlmostEqual(ab, ba, delta=1.0e-12 * abs(ab))

    def test_mutual_inductance_is_positive_and_finite(self):
        value = mutual_inductance_h(self.a, self.b, order=5)
        self.assertTrue(math.isfinite(value))
        self.assertGreater(value, 0.0)

    def test_touching_cells_are_rejected(self):
        touching = MeridionalCell(0.012, 0.014, -0.001, 0.001)
        with self.assertRaisesRegex(ValueError, "singularity-aware"):
            mutual_inductance_h(self.a, touching)

    def test_self_cell_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "singularity-aware"):
            mutual_inductance_h(self.a, self.a)

    def test_resistance_uses_cylindrical_volume_weighting(self):
        sigma = 3.5e6
        matrix = resistance_matrix_ohm((self.a, self.b), sigma)
        expected = (
            math.pi * (self.a.r1_m**2 - self.a.r0_m**2)
            * (self.a.z1_m - self.a.z0_m)
            / (sigma * self.a.area_m2**2)
        )
        self.assertAlmostEqual(matrix[0][0], expected, places=14)
        self.assertEqual(matrix[0][1], 0.0)
        self.assertEqual(matrix[1][0], 0.0)
        self.assertGreater(matrix[1][1], 0.0)

    def test_quadrature_convergence_api(self):
        value, order = converged_mutual_inductance_h(
            self.a, self.b, orders=(4, 6, 8, 10), relative_tolerance=1.0e-4
        )
        self.assertGreater(value, 0.0)
        self.assertIn(order, (6, 8, 10))


if __name__ == "__main__":
    unittest.main()
