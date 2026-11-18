import unittest

from mono_spiral_geometry import MonoSpiral
from run_disk_convergence import matrix_condition_inf
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
            self.assertEqual(first[1], second[0])

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

    def test_coaxial_mutual_rejects_invalid_simpson_resolution(self):
        with self.assertRaises(ValueError):
            _coaxial_loop_mutual(0.010,0.020,0.030,511)

    def test_invalid_disk_is_rejected(self):
        bad=ConductiveDisk(radius_m=0.0,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.04)
        with self.assertRaises(ValueError):
            build_disk_model(self.coil,bad)


if __name__=="__main__":
    unittest.main()
