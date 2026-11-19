import math
import unittest

from rectangular_cross_section_gmd import rectangular_cross_section_gmd
from mono_spiral_geometry import MonoSpiral
from run_disk_convergence import matrix_condition_inf
from run_disk_radial_basis_diagnostics import annulus_section_aspect_ratios
from mono_spiral_disk import (Coil, ConductiveDisk, Pulse, MU0,
    _coaxial_loop_mutual, _segments_coil_path, build_disk_model, receive_peak, simulate)


class ConductiveDiskModelTests(unittest.TestCase):
    def setUp(self):
        self.coil=Coil()
        self.pulse=Pulse(time_step_s=1.0e-6)
        self.disk=ConductiveDisk(radius_m=0.012,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.04,rings=4)

    def test_matrix_condition_inf_for_identity_is_one(self):
        self.assertAlmostEqual(matrix_condition_inf([[1.0, 0.0], [0.0, 1.0]]), 1.0)

    def test_matrix_condition_inf_for_diagonal_matrix(self):
        self.assertAlmostEqual(matrix_condition_inf([[2.0, 0.0], [0.0, 4.0]]), 2.0)

    def test_matrix_is_symmetric_and_positive_diagonal(self):
        L,R,radii=build_disk_model(self.coil,self.disk,ring_segments=48)
        self.assertEqual(len(L),5)
        for i in range(len(L)):
            self.assertGreater(L[i][i],0)
            for j in range(len(L)):
                self.assertAlmostEqual(L[i][j],L[j][i],places=15)
        self.assertTrue(all(v>0 for v in R))

    def test_disk_coupling_uses_one_continuous_spiral_path(self):
        segments = _segments_coil_path(self.coil, subdivisions=3)
        geometry = MonoSpiral(
            outer_side_m=self.coil.outer_side_m,
            turns=self.coil.turns,
            pitch_m=self.coil.pitch_m,
        )
        expected = []
        for start, end in geometry.continuous_spiral_segments():
            for q in range(3):
                f0, f1 = q / 3, (q + 1) / 3
                p0 = tuple(start[i] + (end[i] - start[i]) * f0 for i in range(3))
                p1 = tuple(start[i] + (end[i] - start[i]) * f1 for i in range(3))
                expected.append((p0, p1))
        self.assertEqual(segments, expected)
        for first, second in zip(segments, segments[1:]):
            for axis in range(3):
                self.assertAlmostEqual(first[1][axis], second[0][axis], delta=1e-12)

    def test_model_produces_finite_receive_signal(self):
        rows=simulate(self.coil,self.disk,self.pulse,ring_segments=48)
        peak=receive_peak(rows)
        self.assertGreater(peak,0.0)
        self.assertLess(peak,float("inf"))

    def test_receive_peak_window_is_relative_to_rx_phase_start(self):
        rows = [
            {"time_s": 200e-6, "phase": 1.0, "rx_voltage_v": 0.0},
            {"time_s": 300e-6, "phase": 2.0, "rx_voltage_v": 1.0e-3},
            {"time_s": 700e-6, "phase": 2.0, "rx_voltage_v": 4.0e-3},
            {"time_s": 850e-6, "phase": 2.0, "rx_voltage_v": 9.0e-3},
        ]
        # 700 us absolute is 400 us after RX begins; 850 us is outside
        # the 500 us receive window and must not be selected.
        self.assertAlmostEqual(receive_peak(rows), 4.0e-3)

    def test_greater_depth_reduces_coupling_response(self):
        near=ConductiveDisk(radius_m=0.012,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.04,rings=4)
        far=ConductiveDisk(radius_m=0.012,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.08,rings=4)
        p_near=receive_peak(simulate(self.coil,near,self.pulse,ring_segments=48))
        p_far=receive_peak(simulate(self.coil,far,self.pulse,ring_segments=48))
        self.assertGreater(p_near,p_far)

    def test_ring_count_above_temporary_model_limit_is_rejected(self):
        disk=ConductiveDisk(radius_m=0.012,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.04,rings=9)
        with self.assertRaises(ValueError):
            build_disk_model(self.coil,disk,ring_segments=96)

    def test_coaxial_mutual_inductance_obeys_reciprocity(self):
        mab=_coaxial_loop_mutual(0.010,0.020,0.030,512)
        mba=_coaxial_loop_mutual(0.020,0.010,0.030,512)
        self.assertAlmostEqual(mab,mba,places=15)
        self.assertGreater(mab,0.0)

    def test_coaxial_mutual_inductance_matches_far_field_dipole_limit(self):
        a,b,z=0.010,0.015,1.5
        actual=_coaxial_loop_mutual(a,b,z,2048)
        expected=MU0*3.141592653589793*a*a*b*b/(2*z**3)
        self.assertLess(abs(actual-expected)/expected,0.002)

    def test_agm_mutual_matches_independent_simpson_quadrature(self):
        cases = (
            (0.010, 0.012, 0.001),
            (0.010, 0.020, 0.030),
            (0.010, 0.015, 1.500),
        )
        for radius_a, radius_b, gap in cases:
            with self.subTest(radius_a=radius_a, radius_b=radius_b, gap=gap):
                fast = _coaxial_loop_mutual(radius_a, radius_b, gap)
                reference = _coaxial_loop_mutual(
                    radius_a, radius_b, gap, integration_steps=4096
                )
                self.assertLess(abs(fast - reference) / reference, 2.0e-10)

    def test_coaxial_mutual_rejects_invalid_simpson_resolution(self):
        with self.assertRaises(ValueError):
            _coaxial_loop_mutual(0.010,0.020,0.030,511)

    def test_equal_area_inner_annulus_is_not_thin_ring_geometry(self):
        ratios = annulus_section_aspect_ratios(
            radius_m=0.012, thickness_m=0.001, ring_count=6
        )
        # For equal-area annuli, the innermost radial width / mean radius
        # is sqrt(2), independent of ring count; thin-filament loop formulas
        # are therefore not asymptotically justified for this inner basis.
        self.assertAlmostEqual(ratios[0], math.sqrt(2.0), places=14)
        self.assertGreater(ratios[0], 1.0)

    def test_ring_self_term_uses_rectangular_section_gmd(self):
        disk = ConductiveDisk(
            radius_m=0.012,
            thickness_m=0.001,
            conductivity_s_m=35e6,
            depth_m=0.04,
            rings=4,
        )
        matrix, _, radii = build_disk_model(self.coil, disk, ring_segments=48)
        edges = [disk.radius_m * math.sqrt(i / disk.rings)
                 for i in range(disk.rings + 1)]
        width = edges[1] - edges[0]
        section_gmd = rectangular_cross_section_gmd(width, disk.thickness_m, order=96)
        expected = MU0 * radii[0] * (math.log(8 * radii[0] / section_gmd) - 2.0)
        self.assertAlmostEqual(matrix[1][1], expected, places=18)

    def test_eight_ring_basis_is_rejected_for_known_small_target_fixture(self):
        # Regression fixture from the radial-basis sweep: seven annuli remain
        # positive definite, while the eighth introduces a negative Schur
        # complement at pivot 8. Keep the solver fail-closed until the annular
        # basis/self-inductance formulation is upgraded.
        seven = ConductiveDisk(
            radius_m=0.006, thickness_m=0.001,
            conductivity_s_m=35e6, depth_m=0.04, rings=7,
        )
        eight = ConductiveDisk(
            radius_m=0.006, thickness_m=0.001,
            conductivity_s_m=35e6, depth_m=0.04, rings=8,
        )
        matrix, _, _ = build_disk_model(self.coil, seven, ring_segments=96)
        self.assertEqual(len(matrix), 8)
        with self.assertRaisesRegex(
            ValueError, r"not positive definite at pivot 8"
        ):
            build_disk_model(self.coil, eight, ring_segments=96)

    def test_non_positive_inductance_matrix_reports_failing_pivot(self):
        unstable_fixture = ConductiveDisk(
            radius_m=0.006,
            thickness_m=0.002,
            conductivity_s_m=35e6,
            depth_m=0.04,
            rings=6,
        )
        with self.assertRaisesRegex(ValueError, r"not positive definite at pivot \d+"):
            build_disk_model(self.coil, unstable_fixture, ring_segments=96)

    def test_invalid_disk_is_rejected(self):
        bad=ConductiveDisk(radius_m=0.0,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.04)
        with self.assertRaises(ValueError):
            build_disk_model(self.coil,bad)


if __name__=="__main__":
    unittest.main()
