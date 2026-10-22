"""Float64 preparation buffers: numerical parity, cancellation and CPU/memory benchmark.

Run with --benchmark for 50,000 perspective-filtered splats. Default tests avoid
timing thresholds; the optional benchmark measures preparation time and the
retained output containers, excluding the source cloud and native C4D objects.
"""
import json
import math
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat"))
from argentum_splat import core, geometry as g


def make_cloud(count):
    splats = []
    for index in range(count):
        sh = tuple((j % 7 - 3)*.0125 for j in range(9 if index % 2 else 0))
        raw = ((index % 251)/250., (index % 193)/192., (index % 137)/136.)
        splats.append(core.Splat(
            ((index % 251-125)/100., ((index//251) % 127-63)/100., 5.+(index % 31)/30.),
            raw, .8, (.01, .02, .005), (.7, .2, .3, .6), sh, raw, 'srgb'))
    return core.SplatCloud(splats, count)


def projection():
    return dict(right=(1., 0., 0.), up=(0., 1., 0.), forward=(0., 0., 1.),
                focal_x=960., focal_y=960., width=1920, height=1080)


def bounds(spatial):
    return tuple((min(p[axis]-abs(u[axis])-abs(v[axis]) for p, u, v in zip(*spatial[:3])),
                  max(p[axis]+abs(u[axis])+abs(v[axis]) for p, u, v in zip(*spatial[:3])))
                 for axis in range(3))


def retained_size(value, seen=None):
    """Reachable buffer/list/tuple payload size without counting shared values twice."""
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, g.Vec3Buffer):
        size += sys.getsizeof(value._values)
    elif isinstance(value, (list, tuple)):
        size += sum(retained_size(item, seen) for item in value)
    return size


class Vec3BufferTests(unittest.TestCase):
    def test_append_extend_and_float64_precision(self):
        expected = [(1., 2., 3.), (math.pi, 1e-300, 1e300), (-0., -.25, 1.0000000000000002)]
        actual = g.Vec3Buffer(expected[:1])
        actual.append(expected[1])
        actual.extend(iter(expected[2:]))
        self.assertEqual(list(actual), expected)
        self.assertEqual(len(actual), 3)
        self.assertEqual(actual.nbytes, 3*3*8)
        self.assertEqual(math.copysign(1., actual[-1][0]), -1.)

    def test_sequence_indexing_and_independent_slices_match_lists(self):
        expected = [(float(i), float(i+1), float(i+2)) for i in range(7)]
        actual = g.Vec3Buffer(expected)
        for index in range(-len(expected), len(expected)):
            self.assertEqual(actual[index], expected[index])
        for selection in (slice(None), slice(1, 4), slice(-4, None), slice(None, None, -1),
                          slice(None, None, 2), slice(-1, -6, -2), slice(5, 1), slice(50, 60)):
            with self.subTest(selection=selection):
                selected = actual[selection]
                self.assertIsInstance(selected, g.Vec3Buffer)
                self.assertEqual(list(selected), expected[selection])
                selected.append((8., 9., 10.))
                self.assertEqual(list(actual), expected)
        for index in (-8, 7):
            with self.assertRaises(IndexError):
                _ = actual[index]
        with self.assertRaises(TypeError):
            _ = actual[1.2]
        with self.assertRaises(ValueError):
            _ = actual[::0]

    def test_buffer_copy_and_self_extend_do_not_alias(self):
        original = g.Vec3Buffer([(1., 2., 3.)])
        copy = g.Vec3Buffer(original)
        copy.extend(copy)
        original.append((4., 5., 6.))
        self.assertEqual(list(copy), [(1., 2., 3.), (1., 2., 3.)])
        self.assertEqual(list(original), [(1., 2., 3.), (4., 5., 6.)])

    def test_failed_append_cannot_leave_partial_vector(self):
        original = [(1., 2., 3.)]
        actual = g.Vec3Buffer(original)
        for invalid in ((4., 5.), (4., 5., 6., 7.), (4., 5., 'invalid')):
            with self.assertRaises(ValueError):
                actual.append(invalid)
            self.assertEqual(list(actual), original)
            self.assertEqual(actual.nbytes, 24)

    def test_geometry_colors_shapes_and_bounds_match_default_lists(self):
        cloud = make_cloud(96)
        camera = (0., 0., 0.)
        configurations = (
            dict(scale=1., sh_degree=1, smoothing=0),
            dict(scale=1., sh_degree=3, smoothing=2, flip_y=True),
            dict(scale=1., sh_degree=3, smoothing=0, camera_facing=True),
            dict(scale=1., sh_degree=1, smoothing=0, camera_facing=True,
                 projection=projection(), pixel_variance=.3, gamma=1.3),
            dict(scale=1., sh_degree=1, smoothing=2, camera_facing=True,
                 projection=projection(), pixel_variance=.3, contrast=.6, saturation=.8),
        )
        for settings in configurations:
            with self.subTest(settings=settings):
                expected = g.prepare(cloud, settings, camera)
                compact = g.prepare(cloud, dict(settings, compact_buffers=True), camera)
                self.assertEqual(len(compact), 5)
                for actual_array, expected_array in zip(compact, expected):
                    self.assertIsInstance(expected_array, list)
                    self.assertIsInstance(actual_array, g.Vec3Buffer)
                    self.assertEqual(len(actual_array), len(cloud.splats))
                    self.assertEqual(list(actual_array), expected_array)
                    self.assertEqual(list(actual_array[7:23]), expected_array[7:23])
                self.assertEqual(bounds(compact), bounds(expected))

    def test_empty_output_type_matches_requested_storage(self):
        cloud = make_cloud(0)
        for compact in (False, True):
            prepared = g.prepare(cloud, dict(compact_buffers=compact))
            for values in prepared:
                self.assertIsInstance(values, g.Vec3Buffer if compact else list)
                self.assertEqual(len(values), 0)

    def test_cancellation_remains_responsive_with_compact_buffers(self):
        class Cancelled(Exception):
            pass

        cloud = make_cloud(4100)
        for operation in (g.prepare_geometry, g.prepare_colors):
            calls = []

            def progress(stage, completed, total):
                calls.append((stage, completed, total))
                if completed >= 2048:
                    raise Cancelled()

            with self.subTest(operation=operation.__name__):
                with self.assertRaises(Cancelled):
                    operation(cloud, dict(compact_buffers=True), progress=progress)
                self.assertEqual([done for _, done, _ in calls], [0, 2048])
                self.assertTrue(all(total == 4100 for _, _, total in calls))

    def test_compact_outputs_hold_substantially_less_memory(self):
        cloud = make_cloud(1000)
        settings = dict(scale=1., camera_facing=True, pixel_variance=.3, projection=projection())
        regular = g.prepare(cloud, settings, (0., 0., 0.))
        compact = g.prepare(cloud, dict(settings, compact_buffers=True), (0., 0., 0.))
        self.assertLess(retained_size(compact), retained_size(regular)*.3)


def benchmark():
    cloud = make_cloud(50000)
    settings = dict(scale=1., camera_facing=True, pixel_variance=.3, projection=projection(),
                    smoothing=0, sh_degree=1)
    for compact in (False, True):
        started = time.perf_counter()
        prepared = g.prepare(cloud, dict(settings, compact_buffers=compact), (0., 0., 0.))
        elapsed = time.perf_counter()-started
        size = retained_size(prepared)
        print(json.dumps(dict(count=len(cloud.splats), compact=compact,
                              preparation_seconds=elapsed, retained_output_bytes=size,
                              retained_output_mib=size/(1024*1024))), flush=True)
        del prepared


if __name__ == '__main__':
    if '--benchmark' in sys.argv:
        benchmark()
    else:
        unittest.main()
