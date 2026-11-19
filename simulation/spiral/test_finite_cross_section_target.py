import unittest

from finite_cross_section_target import (
    AnnularCell,
    build_finite_cross_section_matrix,
)


class FiniteCrossSectionTargetTests(unittest.TestCase):
    def setUp(self):
        self.cells = [
            AnnularCell(0.020, 0.022, 0.040, 0.041),
            AnnularCell(0.022, 0.024, 0.040, 0.041),
        ]

    def test_matrix_is_symmetric_positive_and_finite(self):
        matrix, diagnostics = build_finite_cross_section_matrix(
            self.cells, radial_subdivisions=4, axial_subdivisions=4
        )
        self.assertEqual(len(matrix), 2)
        self.assertAlmostEqual(matrix[0][1], matrix[1][0], places=18)
        self.assertTrue(all(value > 0.0 for row in matrix for value in row))
        self.assertEqual(diagnostics["subcells_per_cell"], 16)
        self.assertLess(diagnostics["worst_subcell_dimension_over_radius"], 0.1)

    def test_refinement_changes_the_matrix_by_a_finite_amount(self):
        coarse, _ = build_finite_cross_section_matrix(
            self.cells, radial_subdivisions=2, axial_subdivisions=2
        )
        fine, _ = build_finite_cross_section_matrix(
            self.cells, radial_subdivisions=4, axial_subdivisions=4
        )
        relative_change = abs(fine[0][0] - coarse[0][0]) / fine[0][0]
        self.assertLess(relative_change, 0.02)

    def test_coarse_self_cell_is_rejected_until_refined(self):
        wide = [AnnularCell(0.010, 0.020, 0.030, 0.040)]
        with self.assertRaisesRegex(ValueError, "too wide"):
            build_finite_cross_section_matrix(
                wide, radial_subdivisions=1, axial_subdivisions=1
            )

    def test_overlapping_cells_are_rejected(self):
        overlap = [
            AnnularCell(0.020, 0.023, 0.040, 0.042),
            AnnularCell(0.022, 0.024, 0.041, 0.043),
        ]
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            build_finite_cross_section_matrix(overlap)

    def test_invalid_cell_bounds_are_rejected(self):
        with self.assertRaises(ValueError):
            AnnularCell(0.0, 0.01, 0.0, 0.01).validate()


if __name__ == "__main__":
    unittest.main()
