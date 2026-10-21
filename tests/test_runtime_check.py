import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

BACKEND = Path(__file__).resolve().parents[1] / 'ArgentumSplat' / 'backend'
sys.path.insert(0, str(BACKEND))
import runtime_check as check


class RuntimeCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.config = dict(model_revision=check.MODEL_REVISION,
                           source_revision=check.SOURCE_REVISION,
                           checkpoint_dir=str(self.root / 'models'), model_sha256={})
        for name in check.WEIGHTS:
            target = self.root / 'models' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            header = json.dumps({'tensor': {'dtype': 'U8', 'shape': [2048], 'data_offsets': [0, 2048]}}).encode()
            target.write_bytes(struct.pack('<Q', len(header)) + header + bytes(2048))
            self.config['model_sha256'][name] = '0' * 64

    def tearDown(self):
        self.temp.cleanup()

    def test_legacy_manifest_with_valid_models(self):
        check.check_model_files(self.config, self.root)

    def test_legacy_manifest_detects_truncated_payload(self):
        target = self.root / 'models' / check.WEIGHTS[0]
        target.write_bytes(target.read_bytes()[:-10])
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            check.check_model_files(self.config, self.root)

    def test_wrong_pinned_revision(self):
        self.config['model_revision'] = 'another'
        with self.assertRaisesRegex(ValueError, 'revision'):
            check.check_model_files(self.config, self.root)

    def test_recorded_size_mismatch(self):
        self.config['model_sizes'] = {check.WEIGHTS[0]: 9999}
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            check.check_model_files(self.config, self.root)

    def test_missing_model(self):
        (self.root / 'models' / check.WEIGHTS[0]).unlink()
        with self.assertRaisesRegex(ValueError, 'Missing'):
            check.check_model_files(self.config, self.root)

    def test_relocated_models(self):
        self.config['checkpoint_dir'] = str(self.root / 'elsewhere')
        with self.assertRaisesRegex(ValueError, 'moved'):
            check.check_model_files(self.config, self.root)
