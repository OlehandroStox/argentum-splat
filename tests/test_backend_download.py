import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ArgentumSplat' / 'backend'))
import download_torch as download


class Response(io.BytesIO):
    def __init__(self, data=b'', headers=None, status=200):
        super().__init__(data)
        self.headers = headers or {}
        self.status = status


class DownloadRecoveryTests(unittest.TestCase):
    def test_corrupt_resumable_part_does_not_poison_retry(self):
        payload = bytes(range(64))
        expected = hashlib.sha256(payload).hexdigest()
        tag = 'cp%d%d' % sys.version_info[:2]
        filename = f'torch-{download.TORCH_VERSION}+cu128-{tag}-{tag}-win_amd64.whl'
        index = f'<a href="https://download.pytorch.org/{filename}#sha256={expected}">wheel</a>'.encode()

        def fake_open(request, timeout=60):
            if isinstance(request, str):
                return Response(index)
            if request.get_method() == 'HEAD':
                return Response(headers={'Content-Length': str(len(payload))})
            start, end = map(int, request.get_header('Range').removeprefix('bytes=').split('-'))
            return Response(payload[start:end + 1], {'Content-Range': f'bytes {start}-{end}/{len(payload)}'}, 206)

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            parts = cache / (filename + '.parts')
            parts.mkdir()
            (parts / '00000.bin').write_bytes(b'x' * 16)
            with patch.object(download, 'CHUNK', 16), patch.object(download.urllib.request, 'urlopen', fake_open), patch('builtins.print'):
                with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
                    download.download(cache)
                self.assertEqual(list(parts.glob('*.bin')), [])
                target = download.download(cache)
            self.assertEqual(target.read_bytes(), payload)
            self.assertFalse(parts.exists())
