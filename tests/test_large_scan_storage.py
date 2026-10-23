"""Bounded SH3 scan storage without changing the public Gaussian values."""
import io
from dataclasses import FrozenInstanceError
import math
from pathlib import Path
import struct
import sys
import tempfile
import tracemalloc
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ArgentumSplat'))
from argentum_splat import core, geometry
from test_core import FIELDS


def scan_bytes(count, rest_count=45, endian='<', mixed=False, invalid=None):
    names = FIELDS + ['f_rest_%d' % index for index in range(rest_count)]
    names += ['unused_extra']
    if mixed:
        names.reverse()
    props = [core._Property(name, 'double' if mixed and index % 2 else 'float')
             for index, name in enumerate(names)]
    codec = struct.Struct(endian + ''.join(core._TYPES[p.value_type][0] for p in props))
    rows = []
    for index in range(count):
        values = dict(x=index + .123456789123, y=-.987654321987, z=.0123456789123,
                      opacity=-1000. if index % 11 == 0 else .123456789123,
                      scale_0=-.234567891234, scale_1=-1., scale_2=-2.,
                      rot_0=1., rot_1=.234567891234, rot_2=-.375, rot_3=.5,
                      f_dc_0=.123456789123, f_dc_1=-.625, f_dc_2=.25,
                      unused_extra=17.)
        values.update(('f_rest_%d' % k, (index % 7 - 3) * .123456789123 / (k + 1))
                      for k in range(rest_count))
        if invalid and index == count - 1:
            values.update(invalid)
        rows.append(codec.pack(*(values[name] for name in names)))
    return core._Element('vertex', count, props), b''.join(rows)


def header(vertex, endian, trailing_space=False):
    encoding = 'binary_little_endian' if endian == '<' else 'binary_big_endian'
    text = 'ply\nformat %s 1.0\nelement vertex %d\n' % (encoding, vertex.count)
    text += ''.join('property %s %s\n' % (p.value_type, p.name)
                    for p in vertex.properties)
    if trailing_space:
        text += 'element color_space 1\nproperty uchar color_space\n'
    return (text + 'end_header\n').encode('ascii')


class LargeScanStorageTests(unittest.TestCase):
    def load_pair(self, count=401, rest_count=45, endian='<', mixed=True, max_splats=29):
        vertex, data = scan_bytes(count, rest_count, endian, mixed=mixed)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scan.ply'
            path.write_bytes(header(vertex, endian, True) + data + b'\x00')
            normal = core.load(path, max_splats=max_splats)
            packed = core.load(path, max_splats=max_splats, compact=True)
        # Both representations must remain valid after the source file closes
        # and disappears; compact mode is a snapshot, not a file-backed handle.
        return normal, packed

    def test_packed_selection_matches_generic_decoding_at_original_precision(self):
        for endian in ('<', '>'):
            for rest_count in (0, 9, 24, 45):
                with self.subTest(endian=endian, rest_count=rest_count):
                    vertex, data = scan_bytes(401, rest_count, endian, mixed=True)
                    expected = core._Sampler(29, .02)
                    gaussian, props, _ = core._vertex_schema(vertex, .01)
                    for index, values in enumerate(core._binary_records(io.BytesIO(data), vertex, endian)):
                        expected.add(index, core._make_vertex(
                            values, index, gaussian, props, rest_count, .01))
                    expected = expected.finish(vertex.count, {'sh_degree': {0: 0, 9: 1, 24: 2, 45: 3}[rest_count]}, 'linear')
                    with tempfile.TemporaryDirectory() as folder:
                        path = Path(folder) / 'scan.ply'
                        # The source transfer function occurs after the packed
                        # records and must still govern the eventual decoding.
                        path.write_bytes(header(vertex, endian, True) + data + b'\x01')
                        actual = core.load(path, max_splats=29, min_opacity=.02)
                    self.assertEqual(actual.splats, expected.splats)
                    for key in ('eligible_count', 'filtered_count', 'bounds', 'effective_sh_degree'):
                        self.assertEqual(actual.metadata[key], expected.metadata[key])
                    self.assertIsInstance(actual.splats[0].sh, tuple)
                    self.assertIsInstance(actual.splats[0].position, tuple)

    def test_malformed_filtered_records_are_still_rejected(self):
        cases = (
            {'x': math.nan}, {'unused_extra': math.inf},
            {'f_rest_44': math.nan}, {'scale_1': 1000.},
            {'scale_2': -1000.},
            {'rot_0': 0., 'rot_1': 0., 'rot_2': 0., 'rot_3': 0.},
        )
        for invalid in cases:
            with self.subTest(invalid=invalid):
                vertex, data = scan_bytes(40, invalid=dict(invalid, opacity=-1000.))
                with self.assertRaises(core.SplatFormatError):
                    core._load_binary_gaussians(
                        io.BytesIO(data), vertex, '<', core._Sampler(1, .02), 45)

    def test_large_sh3_reservoir_has_bounded_peak_storage(self):
        # Source bytes are constructed before tracing: measure reader storage,
        # not a test fixture which the real reader streams from the filesystem.
        vertex, data = scan_bytes(20_000)
        sampler = core._Sampler(12_000, .02)
        tracemalloc.start()
        try:
            decode = core._load_binary_gaussians(io.BytesIO(data), vertex, '<', sampler, 45)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 12 * 1024 * 1024,
                        'Reservoir expanded SH3 floats before final selection: %d bytes' % peak)
        cloud = sampler.finish(vertex.count, {'sh_degree': 3}, 'srgb', decode)
        self.assertEqual(len(cloud.splats), 12_000)
        self.assertEqual(sampler.items, [])
        self.assertEqual(cloud.metadata['effective_sh_degree'], 3)

    def test_compact_matches_default_values_and_metadata(self):
        for endian in ('<', '>'):
            for rest_count in (0, 9, 24, 45):
                with self.subTest(endian=endian, rest_count=rest_count):
                    normal, packed = self.load_pair(rest_count=rest_count, endian=endian)
                    self.assertIsInstance(normal.splats, list)
                    self.assertNotIsInstance(packed.splats, list)
                    self.assertEqual(list(packed.splats), normal.splats)
                    self.assertEqual(packed.splats, normal.splats)
                    self.assertEqual(packed.metadata, normal.metadata)
                    self.assertEqual(packed.total_count, normal.total_count)

    def test_compact_indexes_slices_are_immutable_and_repeatable(self):
        normal, packed = self.load_pair()
        values = packed.splats
        self.assertEqual(len(values), len(normal.splats))
        for index in (0, 1, -1, -len(values)):
            self.assertEqual(values[index], normal.splats[index])
            self.assertIsInstance(values[index], core.Splat)
        for part in (slice(None), slice(None, None, -1), slice(1, 17, 3),
                     slice(-3, None), slice(200, 300)):
            self.assertNotIsInstance(values[part], list)
            self.assertEqual(list(values[part]), normal.splats[part])
        for index in (len(values), -len(values)-1):
            with self.assertRaises(IndexError):
                values[index]
        with self.assertRaises(TypeError):
            values[.5]
        with self.assertRaises(ValueError):
            values[::0]
        with self.assertRaises(TypeError):
            values[0] = normal.splats[0]
        with self.assertRaises(FrozenInstanceError):
            values._records = ()
        first, second = iter(values), iter(values)
        self.assertEqual(next(first), next(second))
        self.assertEqual(list(first), normal.splats[1:])
        self.assertEqual(list(second), normal.splats[1:])
        self.assertEqual(list(values), normal.splats)

    def test_compact_geometry_and_sh_passes_match_default(self):
        normal, packed = self.load_pair(count=80, max_splats=80)
        settings = dict(scale=100., splat_scale=1., flip_y=True,
                        camera_facing=True, smoothing=0, sh_degree=3,
                        sh_strength=.9, gamma=1.1, contrast=.4,
                        hue=10., saturation=.8, level=1.2)
        camera = (1., 2., -500.)
        expected = geometry.prepare(normal, settings, camera)
        self.assertEqual(geometry.prepare(packed, settings, camera), expected)
        self.assertEqual(geometry.prepare(packed, settings, camera), expected)

    def test_compact_validation_can_cancel_before_publishing_cloud(self):
        vertex, data = scan_bytes(6000)
        class Cancelled(Exception):
            pass
        seen = []
        def cancel(stage, done, total):
            seen.append((stage, done, total))
            if stage == 'Decode colour' and done >= 2048:
                raise Cancelled()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scan.ply'
            path.write_bytes(header(vertex, '<') + data)
            with self.assertRaises(Cancelled):
                core.load(path, max_splats=6000, compact=True, progress=cancel)
            # Cancelled work has no global state affecting a subsequent load.
            self.assertGreater(len(core.load(path, compact=True).splats), 0)
        self.assertTrue(any(stage == 'Decode colour' and done == 2048
                            for stage, done, total in seen))

    def test_compact_validates_filtered_records_and_rejects_truncation(self):
        vertex, data = scan_bytes(40, invalid={'opacity': -1000., 'f_rest_44': math.nan})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scan.ply'
            for bad in (data, data[:-1]):
                path.write_bytes(header(vertex, '<') + bad)
                with self.assertRaises(core.SplatFormatError):
                    core.load(path, max_splats=1, compact=True)

    def test_compact_full_load_retains_compact_storage(self):
        vertex, data = scan_bytes(20_000)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scan.ply'
            path.write_bytes(header(vertex, '<') + data)
            tracemalloc.start()
            try:
                cloud = core.load(path, max_splats=12_000, compact=True)
                retained, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
        self.assertEqual(len(cloud.splats), 12_000)
        self.assertLess(retained, 6 * 1024 * 1024)
        self.assertLess(peak, 12 * 1024 * 1024)
        self.assertEqual(cloud.metadata['effective_sh_degree'], 3)

    def test_compact_option_keeps_other_readers_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scan.splat'
            path.write_bytes(struct.pack('<6f8B', 1, 2, 3, 1, 1, 1,
                                         255, 128, 0, 255, 255, 128, 128, 128))
            normal = core.load(path)
            packed = core.load(path, compact=True)
            self.assertIsInstance(packed.splats, core._PackedSplats)
            self.assertEqual(normal.splats, packed.splats)
            with self.assertRaisesRegex(ValueError, 'boolean'):
                core.load(path, compact=1)


if __name__ == '__main__':
    unittest.main()
