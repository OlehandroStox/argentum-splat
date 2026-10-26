"""Transparent-tail clipping preserves the existing visible Gaussian field."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ArgentumSplat'))
from argentum_splat.geometry import gaussian_support

class GaussianSupportTests(unittest.TestCase):
    def test_every_removed_sample_was_already_zero_in_shader(self):
        for alpha in (0.,1/255,.005,.01,.03,.1,.5,1.,2.):
            support=gaussian_support(alpha)
            self.assertGreaterEqual(support,0.)
            self.assertLessEqual(support,1.)
            for i in range(-80,81):
                x=i/80
                for j in range(-80,81):
                    y=j/80
                    floor=math.exp(-4.)
                    old=min(1.,max(0.,alpha))*max(0.,(math.exp(-4.5*(x*x+y*y))-floor)/(1.-floor))
                    if abs(x)>support or abs(y)>support:
                        self.assertLess(old,1/255)
                    elif support:
                        # Geometry shrinks by support and UVs shrink about .5.
                        local=x/support
                        uv=.5*(1-support)+(local+1)*.5*support
                        self.assertAlmostEqual((uv-.5)*2,x)

    def test_faint_support_changes_with_opacity_without_affecting_covariance(self):
        self.assertEqual(gaussian_support(0),0)
        self.assertLess(gaussian_support(1),1)
        self.assertLess(gaussian_support(.01),gaussian_support(.02))
        floor=math.exp(-4.)
        self.assertAlmostEqual(gaussian_support(.01),math.sqrt(-math.log(floor+(1.-floor)/2.55)/4.5)+1e-6)

if __name__=='__main__':unittest.main()
