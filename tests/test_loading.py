"""Regression tests for scan cancellation, exact sampling and invalidation."""
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ArgentumSplat'))
from argentum_splat import core, geometry, loading
from test_core import FIELDS, ROW, ply_header


VALUES = dict(scale=100., splat_scale=1., flip_y=False, camera_facing=False,
    smoothing=2, sh_degree=1, sh_strength=1., gamma=1., contrast=.5,
    hue=0., saturation=1., level=1., highlight=3., color_mode=0)


class LoadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def binary(self, rows, fields=FIELDS):
        path = self.folder/'scan.ply'
        # float32 input, exactly representable values used in the parity test.
        path.write_bytes(ply_header(len(rows), 'binary_little_endian', fields=fields)+
                         b''.join(struct.pack('<%df' % len(row), *row) for row in rows))
        return path

    def test_binary_fast_path_same_sample_and_sh_as_ascii(self):
        fields = FIELDS+['f_rest_%d'%i for i in range(45)]
        rows = []
        for i in range(400):
            row = [float(i), 0., 1., .25, .5, .125, 0., 0., 0., 0., 1., 0., 0., 0.]
            row += [float(i%7)/8.]*45
            rows.append(row)
        binary = self.binary(rows, fields)
        ascii_path = self.folder/'ascii.ply'
        ascii_path.write_bytes(ply_header(len(rows), fields=fields)+
            ''.join(' '.join(map(str,row))+'\n' for row in rows).encode())
        a, b = [core.load(path, max_splats=29) for path in (binary,ascii_path)]
        self.assertEqual(a.splats,b.splats)
        self.assertEqual(a.metadata['bounds'],b.metadata['bounds'])

    def test_binary_validates_filtered_and_unretained_records(self):
        for index, value in ((0,math.nan),(7,1000.),(8,-1000.),(10,0.)):
            rows = [ROW.copy() for _ in range(20)]
            rows[-1][6] = -1000.
            rows[-1][index] = value
            with self.subTest(index=index), self.assertRaises(core.SplatFormatError):
                core.load(self.binary(rows),max_splats=1)

    def test_splat_validates_filtered_bad_quaternion(self):
        path = self.folder/'scan.splat'
        path.write_bytes(struct.pack('<6f8B',1,2,3,1,1,1,0,0,0,0,128,128,128,128))
        with self.assertRaisesRegex(core.SplatFormatError,'zero quaternion'):
            core.load(path)

    def test_read_cancellation_from_progress(self):
        path = self.binary([ROW]*6000)
        seen = []
        def cancel(stage, done, total):
            seen.append((stage,done,total))
            if done > 0:
                raise loading.Cancelled()
        with self.assertRaises(loading.Cancelled):
            core.load(path, max_splats=100,progress=cancel)
        self.assertTrue(seen)

    def test_sh_camera_change_does_not_invalidate_surface_geometry(self):
        a = loading.preparation_keys(('scan',),VALUES,(0,0,-5),True,(0,))
        b = loading.preparation_keys(('scan',),VALUES,(3,0,-5),True,(0,))
        self.assertEqual(a[0],b[0])
        self.assertNotEqual(a[1],b[1])

    def test_no_sh_scan_does_not_depend_on_camera(self):
        a = loading.preparation_keys(('scan',),VALUES,(0,0,-5),False,(0,))
        b = loading.preparation_keys(('scan',),VALUES,(3,0,-5),False,(0,))
        self.assertEqual(a,b)

    def test_facing_cards_still_depend_on_camera(self):
        values = dict(VALUES,camera_facing=True)
        a = loading.preparation_keys(('scan',),values,(0,0,-5),False,(0,))
        b = loading.preparation_keys(('scan',),values,(3,0,-5),False,(0,))
        self.assertNotEqual(a[0],b[0])

    def test_worker_result_and_cancellation_are_atomic(self):
        path = self.binary([ROW]*40)
        request = dict(path=path,max_splats=20,min_opacity=0.,raw_spz=False,
                       values=VALUES,camera=(0,0,-500))
        cancelled = loading.Preparation(request)
        cancelled.cancelled.set()
        cancelled.start()
        self.assertTrue(cancelled.done.wait(5))
        self.assertIsInstance(cancelled.error,loading.Cancelled)
        self.assertIsNone(cancelled.result)
        worker = loading.Preparation(request).start()
        self.assertTrue(worker.done.wait(5))
        self.assertIsNone(worker.error)
        self.assertEqual(len(worker.result['cloud'].splats),20)
        self.assertEqual(len(worker.result['spatial'][0]),20)
        self.assertEqual(len(worker.result['colors']),20)
        reused = loading.Preparation(request, worker.result['cloud'],
            worker.result['spatial'],worker.result['colors'],worker.result['bounds']).start()
        self.assertTrue(reused.done.wait(5))
        self.assertIsNone(reused.error)
        self.assertIs(reused.result['spatial'],worker.result['spatial'])
        self.assertIs(reused.result['colors'],worker.result['colors'])

    def test_geometry_cancellation_in_smoothing(self):
        cloud = core.load(self.binary([ROW]*50))
        def cancel(stage, done, total):
            if stage == 'Smooth normals':
                raise loading.Cancelled()
        with self.assertRaises(loading.Cancelled):
            geometry.prepare_geometry(cloud,VALUES,progress=cancel)

    def test_worker_reports_bad_input_without_partial_result(self):
        request = dict(path=self.folder/'missing.splat',max_splats=20,min_opacity=0.,
                       raw_spz=False,values=VALUES,camera=(0,0,-500))
        worker = loading.Preparation(request).start()
        self.assertTrue(worker.done.wait(5))
        self.assertIsInstance(worker.error,FileNotFoundError)
        self.assertIsNone(worker.result)


if __name__ == '__main__':
    unittest.main()
