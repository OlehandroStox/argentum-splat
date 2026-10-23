"""Import framing across scale, aspect, source formats and floating background."""
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ArgentumSplat'))
from argentum_splat import core, geometry as g, loading, import_analysis as a


def cloud(positions):
    return core.SplatCloud([core.Splat(tuple(p),(.5,.2,.1),.8,(.01,)*3,(1.,0.,0.,0.))
                           for p in positions],len(positions))


class ImportAnalysisTests(unittest.TestCase):
    def test_scale_and_aspect_fit_is_relative_to_source(self):
        for size in (1e-6,.1,100.,1e6):
            for aspect in (.25,1.,4.):
                with self.subTest(size=size,aspect=aspect):
                    bounds=((-size,-size*.3,-size*.7),(size,size*.3,size*.7))
                    points=a.corners(bounds)
                    fit=a.fit_camera(points,(1,0,0),(0,1,0),(.4,-.2,1),math.radians(50),aspect)
                    tx=math.tan(math.radians(25))
                    for p in points:
                        delta=g.sub(p,fit['eye'])
                        x,y,z=(g.dot(delta,fit[k]) for k in ('right','up','forward'))
                        self.assertGreater(z,fit['near'])
                        self.assertLessEqual(abs(x/z),tx/1.14)
                        self.assertLessEqual(abs(y/z),tx/aspect/1.14)

    def test_off_origin_bounds_preserve_position_and_fit(self):
        points=a.corners(((1e8,2e8,-1e8),(1e8+200,2e8+20,-1e8+50)))
        fit=a.fit_camera(points,(1,0,0),(0,1,0),(0,0,1),1.,1.)
        self.assertEqual(fit['target'],(1e8+100,2e8+10,-1e8+25))
        self.assertLess(fit['distance'],1000)

    def test_floaters_do_not_dominate_initial_frame_or_delete_records(self):
        source=cloud([(math.sin(i),math.cos(i),i%5*.1) for i in range(1000)]+[(1e9,1e9,1e9)])
        original=list(source.splats)
        report=a.analyse(source)
        self.assertLess(max(report['bounds'][1]),10)
        self.assertEqual(report['retained'],1001)
        self.assertEqual(source.splats,original)

    def test_thin_flat_and_single_splat_have_nonzero_framing_volume(self):
        for points in ([(0,0,0)],[(0,0,0),(2,0,0)],[(0,0,0),(1,1,0)]):
            report=a.analyse(cloud(points))
            self.assertTrue(all(hi>lo for lo,hi in zip(*report['bounds'])))

    def test_environment_tail_does_not_put_camera_outside_capture(self):
        # Smoothly distributed detail with a long environment tail, not one
        # removable outlier. q90/q50 < 8 while q95/q50 > 8.
        points=[]
        for i in range(1000):
            t=(i+.5)/1000
            radius=.2+t/(1-t)**1.2
            angle=i*2.399963229728653
            points.append((radius*math.cos(angle),.2*radius*math.sin(angle),radius*math.sin(angle)))
        source=cloud(points)
        before=list(source.splats)
        report=a.analyse(source)
        self.assertIn('dense central region',report['frame_focus'])
        self.assertLess(max(report['bounds'][1]),2.)
        self.assertEqual(before,source.splats)

    def test_compact_subject_keeps_whole_overview(self):
        source=cloud([(math.sin(i),math.cos(i),math.sin(i*.3)) for i in range(1000)])
        report=a.analyse(source)
        self.assertEqual(report['frame_focus'],'overview')
        self.assertGreater(report['bounds'][1][0],.99)

    def test_capture_view_requires_detail_across_frame_and_rejects_blobs(self):
        splats=[core.Splat((x*.25,y*.25,10.),(.5,.5,.5),.8,
            (.02,.02,.001),(1.,0.,0.,0.)) for x in range(-40,41) for y in range(-23,24)]
        score=a.capture_view_score(splats,1_000_000)
        self.assertTrue(score['available'])
        self.assertGreater(score['detail_coverage'],.9)
        blob=core.Splat((0.,0.,1.),(.5,.5,.5),1.,(5.,5.,5.),(1.,0.,0.,0.))
        self.assertFalse(a.capture_view_score(splats+[blob]*50,1_000_000)['available'])

    def test_capture_view_rejects_narrow_subject_and_empty_forward_view(self):
        source=cloud([(0.,i*.01,10.) for i in range(-100,100)])
        self.assertFalse(a.capture_view_score(source.splats,1_000_000)['available'])
        self.assertFalse(a.capture_view_score(cloud([(0,0,-1)]).splats,1)['available'])

    def test_environment_direction_prefers_detail_over_close_blurred_surface(self):
        # Two dense, isotropic walls. The forward wall has additional coarse
        # foreground splats; the equally detailed right wall is a better view.
        front=[core.Splat((x*.25,y*.25,10.),(.5,)*3,.8,(.02,)*3,(1.,0.,0.,0.))
            for x in range(-40,41) for y in range(-23,24)]
        right=[core.Splat((10.,s.position[1],-s.position[0]),s.color,s.opacity,
                         s.scales,s.rotation) for s in front]
        blob=core.Splat((0.,0.,5.),(.5,)*3,.1,(.1,)*3,(1.,0.,0.,0.))
        result=a.choose_capture_view(front+right+[blob]*30,2_000_000)
        self.assertTrue(result['available'])
        self.assertEqual(result['forward'],(1.,0.,0.))
        original=a.capture_view_score(front,1_000_000)
        rotated=a.capture_view_score(right,1_000_000,(1.,0.,0.))
        for key in ('detail_coverage','coarse_fraction','near'):
            self.assertAlmostEqual(original[key],rotated[key])

    def test_sampling_and_missing_gaussian_data_are_visible(self):
        source=cloud([(0,0,0)])
        source.total_count=1000
        source.metadata=dict(eligible_count=800,kind='point_cloud',input_color_space='linear',effective_sh_degree=0)
        message=a.summary(a.analyse(source),100.)
        self.assertIn('limit reached',message)
        self.assertIn('200 records',message)
        self.assertIn('original Gaussian shapes',message)
        self.assertIn('linear source colour',message)

    def test_analysis_is_bounded_deterministic_and_cancellable(self):
        source=cloud([(i,0,0) for i in range(10000)])
        self.assertEqual(a.analyse(source,limit=1024),a.analyse(source,limit=1024))
        self.assertEqual(a.analyse(source,limit=1024)['sample_count'],1024)
        def cancel(*args): raise loading.Cancelled()
        with self.assertRaises(loading.Cancelled): a.analyse(source,cancel)

    def test_empty_and_invalid_camera_are_rejected(self):
        with self.assertRaises(ValueError): a.analyse(cloud([]))
        with self.assertRaises(ValueError): a.fit_camera([(0,0,0)],(1,0,0),(0,0,1),(0,0,1),1.,1.)
        with self.assertRaises(ValueError): a.fit_camera([(0,0,0)],(1,0,0),(0,1,0),(0,0,1),1.,0.)

    def test_analysis_stage_reuses_cloud_without_preparing_obsolete_view(self):
        source=cloud([(0,0,2),(1,1,3)])
        values=dict(scale=100.,camera_facing=False,sh_degree=0)
        request=dict(path='unused',max_splats=10,min_opacity=0.,raw_spz=False,
                     values=values,camera=(0,0,-500),analyse_only=True)
        with patch.object(loading.geometry,'prepare_geometry',side_effect=AssertionError('too early')):
            worker=loading.Preparation(request,cloud=source).start()
            self.assertTrue(worker.done.wait(5))
            self.assertIsNone(worker.error)
            self.assertIs(worker.result['cloud'],source)
        with patch.object(core,'load',side_effect=AssertionError('must not read twice')):
            followup=loading.Preparation(dict(request,analyse_only=False,analysis=worker.result['analysis']),
                                         cloud=worker.result['cloud']).start()
            self.assertTrue(followup.done.wait(5))
            self.assertIsNone(followup.error)
            self.assertIs(followup.result['analysis'],worker.result['analysis'])


if __name__=='__main__': unittest.main()
