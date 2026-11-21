import math
import unittest
from rectangular_segment_general_mutual import rectangular_segment_mutual_inductance

class GeneralRectangularMutualTests(unittest.TestCase):
    def setUp(self):
        self.a=dict(center_a=(0.,0.,0.),axis_a=(0.,0.,1.),
          cross_u_a=(1.,0.,0.),cross_v_a=(0.,1.,0.),
          length_a_m=.001,width_a_m=.0002,height_a_m=.0002)
        self.b=dict(center_b=(.05,.03,.02),axis_b=(.6,0.,.8),
          cross_u_b=(0.,1.,0.),cross_v_b=(-.8,0.,.6),
          length_b_m=.0015,width_b_m=.0002,height_b_m=.0002)

    def test_nonparallel_far_field_limit(self):
        actual=rectangular_segment_mutual_inductance(**self.a,**self.b,order=6)
        distance=math.dist(self.a["center_a"],self.b["center_b"])
        expected=1e-7*.001*.0015*.8/distance
        self.assertGreater(actual,0.)
        self.assertLess(abs(actual-expected)/expected,.01)

    def test_reciprocity_when_segments_are_swapped(self):
        first=rectangular_segment_mutual_inductance(**self.a,**self.b,order=6)
        def rename(d, old, new):
            return {k.replace(old,new):v for k,v in d.items()}
        reverse=rectangular_segment_mutual_inductance(
            **rename(self.b,"_b","_a"),**rename(self.a,"_a","_b"),order=6)
        self.assertAlmostEqual(first,reverse,delta=1e-18)

    def test_reversing_one_current_direction_reverses_mutual_sign(self):
        parallel=dict(center_b=(.04,.02,.01),axis_b=(0.,0.,1.),
          cross_u_b=(1.,0.,0.),cross_v_b=(0.,1.,0.),
          length_b_m=.0015,width_b_m=.0002,height_b_m=.0002)
        positive=rectangular_segment_mutual_inductance(**self.a,**parallel,order=6)
        parallel["axis_b"]=(0.,0.,-1.)
        parallel["cross_v_b"]=(0.,-1.,0.)
        negative=rectangular_segment_mutual_inductance(**self.a,**parallel,order=6)
        self.assertGreater(positive,0.)
        self.assertLess(negative,0.)
        self.assertAlmostEqual(positive,-negative,delta=1e-18)

    def test_perpendicular_current_directions_have_zero_coupling(self):
        b=dict(self.b)
        b["axis_b"]=(0.,1.,0.)
        b["cross_u_b"]=(1.,0.,0.)
        b["cross_v_b"]=(0.,0.,-1.)
        self.assertEqual(rectangular_segment_mutual_inductance(**self.a,**b,order=4),0.)

    def test_nonorthogonal_cross_section_is_rejected(self):
        b=dict(self.b)
        b["cross_u_b"]=(1.,0.,0.)
        with self.assertRaises(ValueError):
            rectangular_segment_mutual_inductance(**self.a,**b,order=4)

if __name__=="__main__":
    unittest.main()
