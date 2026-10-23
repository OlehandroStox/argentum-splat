import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from test_core import ROW, ply_header
from test_spz import fixture
from argentum_splat import core, import_budget as b, loading


class ImportBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_max_preserves_all_eligible_and_source_order(self):
        path = self.folder / 'scan.ply'
        rows = [list(ROW) for _ in range(17)]
        for i, row in enumerate(rows):
            row[0] = i
        rows[6][6] = -1000  # opacity, not retention, excludes exactly this row
        path.write_bytes(ply_header(len(rows), 'binary_little_endian') +
                         b''.join(struct.pack('<14f', *row) for row in rows))
        full = core.load(path, max_splats=0, compact=True)
        self.assertEqual([s.position[0] for s in full.splats], [i for i in range(17) if i != 6])
        self.assertEqual(full.metadata['eligible_count'], len(full.splats))
        self.assertEqual(full.metadata['sampling'], 'full eligible source')
        sample = core.load(path, max_splats=4, compact=True)
        self.assertEqual(len(sample.splats), 4)
        self.assertEqual(sample.total_count, full.total_count)
        self.assertEqual(sample.metadata['filtered_count'], 1)

    def test_full_source_is_not_capped_by_old_four_million_limit(self):
        self.assertEqual(b.retained_upper_bound(9_975_598, 0), 9_975_598)
        path = self.folder / 'one.ply'
        path.write_bytes(ply_header(1, 'binary_little_endian') + struct.pack('<14f', *ROW))
        self.assertEqual(len(core.load(path, max_splats=9_975_598).splats), 1)

    def test_header_count_before_conversion_for_real_formats(self):
        paths = [self.folder / ('scan' + ext) for ext in ('.sog', '.ply', '.splat', '.spz')]
        with zipfile.ZipFile(paths[0], 'w') as archive:
            archive.writestr('meta.json', json.dumps({'count': 9_975_598}))
        paths[1].write_bytes(ply_header(7, 'binary_little_endian'))
        paths[2].write_bytes(bytes(32 * 11))
        paths[3].write_bytes(fixture(positions=((1,2,3),(4,5,6))))
        self.assertEqual([b.source_count(p) for p in paths], [9_975_598,7,11,2])
        self.assertIn('9,975,598 / 9,975,598', b.plan(paths[0], 0))
        self.assertIn('250,000 / 9,975,598', b.plan(paths[0], b.PRESETS[1]))
        paths[2].write_bytes(bytes(32 * 12))
        self.assertEqual(b.source_count(paths[2]), 12)

    def test_unsafe_full_import_fails_without_silent_sampling(self):
        with self.assertRaisesRegex(MemoryError, 'never silently sampled'):
            b.check_memory(10_000_000, 0, available=4 * 2**30)
        b.check_memory(10_000_000, 250_000, available=4 * 2**30)
        self.assertEqual(b.preset_for(0), 4)
        self.assertEqual(b.preset_for(12345), 0)

    def test_compact_spz_is_exact_and_preserves_full_source_after_file_removed(self):
        path = self.folder / 'scan.spz'
        path.write_bytes(fixture(positions=((1,2,3),(4,5,6)), degree=3, sh=range(45)))
        ordinary = core.load(path, max_splats=0)
        packed = core.load(path, max_splats=0, compact=True)
        path.unlink()
        self.assertEqual(packed.splats, ordinary.splats)
        self.assertIsInstance(packed.splats, core._PackedSplats)

    def test_full_import_remains_cancellable(self):
        path = self.folder / 'scan.ply'
        path.write_bytes(ply_header(5000, 'binary_little_endian') + struct.pack('<14f', *ROW) * 5000)
        def cancel(stage, done, total):
            if stage == 'Decode colour' and done >= 2048:
                raise loading.Cancelled()
        with self.assertRaises(loading.Cancelled):
            core.load(path, max_splats=0, compact=True, progress=cancel)

    def test_bad_or_oversized_sog_header_fails_before_loading(self):
        for count in (-1, 100_000_001, True, '9000000'):
            path = self.folder / ('bad' + str(count) + '.sog')
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('meta.json', json.dumps({'count':count}))
            with self.assertRaises(ValueError):
                b.source_count(path)
