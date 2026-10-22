"""Sparse render-card indexing and selective decoding retain source semantics."""
import math
import unittest
import test_large_scan_storage as storage
from argentum_splat import core, geometry as g, import_analysis as a, loading
from test_scan_scheduling import VALUES


class ViewOptimizationTests(unittest.TestCase):
    def test_selective_attributes_match_full_snapshot_all_layouts(self):
        for endian in ('<','>'):
            for sh in (0,9,24,45):
                normal, packed = storage.LargeScanStorageTests().load_pair(endian=endian,rest_count=sh)
                for expected, spatial, color, alpha in zip(normal.splats,
                        core.iter_attributes(packed,'geometry'),core.iter_attributes(packed,'appearance'),
                        core.iter_attributes(packed,'opacity')):
                    self.assertEqual((spatial.position,spatial.scales,spatial.rotation),
                                     (expected.position,expected.scales,expected.rotation))
                    self.assertEqual((color.position,color.raw_color,color.sh,color.input_color_space),
                                     (expected.position,expected.raw_color,expected.sh,expected.input_color_space))
                    self.assertEqual(alpha,expected.opacity)
                indices=[0,5,2,len(normal.splats)-1]
                self.assertEqual(list(core.iter_attributes(packed,'opacity',indices)),
                                 [normal.splats[i].opacity for i in indices])

    def test_compaction_removes_only_zero_area_and_preserves_order(self):
        spatial=([(i,0,0) for i in range(5)],[(0,0,0),(1,0,0),(0,0,0),(0,1e-30,0),(0,0,2)])
        self.assertEqual(list(g.card_indices(spatial,True)),[1,3,4])
        self.assertEqual(list(g.card_indices(spatial,False)),list(range(5)))
        self.assertEqual(len(spatial[0]),5)

    def test_entering_hierarchy_invalidates_geometry_but_not_colors(self):
        baseline=loading.preparation_keys(('a',),dict(VALUES,compact_cards=True),(0,0,-5),3,(0,))
        hierarchy=loading.preparation_keys(('a',),dict(VALUES,compact_cards=False),(0,0,-5),3,(0,))
        self.assertNotEqual(baseline[0],hierarchy[0])
        self.assertEqual(baseline[1],hierarchy[1])

    def test_large_environment_shell_does_not_swallow_body_frame(self):
        points=[(math.cos(i),math.sin(i),i%11*.1) for i in range(800)]
        points += [(1000*math.cos(i),1000*math.sin(i),i%11*10.) for i in range(200)]
        for scale in (1e-6,1.,1e6):
            splats=[core.Splat(tuple(v*scale for v in p),(.5,)*3,.8,(scale*.01,)*3,(1,0,0,0)) for p in points]
            source=core.SplatCloud(splats,len(splats))
            report=a.analyse(source)
            self.assertIn('central region',report['frame_focus'])
            self.assertLess(max(report['bounds'][1]),5*scale)
            self.assertEqual(report['retained'],1000)
            self.assertGreater(max(report['overview_bounds'][1]),900*scale)

    def test_uniform_scene_is_not_cropped_to_a_dense_center(self):
        splats=[core.Splat((i,j,0),(.5,)*3,.8,(.01,)*3,(1,0,0,0)) for i in range(30) for j in range(30)]
        report=a.analyse(core.SplatCloud(splats,len(splats)))
        self.assertEqual(report['frame_focus'],'overview')
        self.assertLess(report['bounds'][0][0],0)
        self.assertGreater(report['bounds'][1][0],29)


if __name__=='__main__': unittest.main()
