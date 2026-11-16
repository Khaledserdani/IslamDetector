import unittest

from mono_spiral_disk import Coil, ConductiveDisk, Pulse, build_disk_model, receive_peak, simulate


class ConductiveDiskModelTests(unittest.TestCase):
    def setUp(self):
        self.coil=Coil()
        self.pulse=Pulse(time_step_s=1.0e-6)
        self.disk=ConductiveDisk(radius_m=0.012,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.04,rings=4)

    def test_matrix_is_symmetric_and_positive_diagonal(self):
        L,R,radii=build_disk_model(self.coil,self.disk,ring_segments=48)
        self.assertEqual(len(L),5)
        for i in range(len(L)):
            self.assertGreater(L[i][i],0)
            for j in range(len(L)):
                self.assertAlmostEqual(L[i][j],L[j][i],places=15)
        self.assertTrue(all(v>0 for v in R))

    def test_model_produces_finite_receive_signal(self):
        rows=simulate(self.coil,self.disk,self.pulse,ring_segments=48)
        peak=receive_peak(rows)
        self.assertGreater(peak,0.0)
        self.assertLess(peak,float("inf"))

    def test_greater_depth_reduces_coupling_response(self):
        near=ConductiveDisk(radius_m=0.012,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.04,rings=4)
        far=ConductiveDisk(radius_m=0.012,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.08,rings=4)
        p_near=receive_peak(simulate(self.coil,near,self.pulse,ring_segments=48))
        p_far=receive_peak(simulate(self.coil,far,self.pulse,ring_segments=48))
        self.assertGreater(p_near,p_far)

    def test_invalid_disk_is_rejected(self):
        bad=ConductiveDisk(radius_m=0.0,thickness_m=0.001,
            conductivity_s_m=35e6,depth_m=0.04)
        with self.assertRaises(ValueError):
            build_disk_model(self.coil,bad)


if __name__=="__main__":
    unittest.main()
