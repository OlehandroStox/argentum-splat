"""A release contains plugin sources and docs, never a developer's runtime."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('argentum_release_builder', ROOT/'tools/build_release.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ReleasePackagingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.shipped = {
            'ArgentumSplat/argentum_splat/__init__.py':
                '__version__ = "1.2.3-rc.1"\nraise RuntimeError("packaging must not execute this")\n',
            'ArgentumSplat/ArgentumSplat.pyp': '# plugin entry point\n',
            'ArgentumSplat/Install.cmd': '@echo installer\n',
            'ArgentumSplat/setup_python.ps1': '# private runtime installer\n',
            'ArgentumSplat/backend/worker.py': '# background worker\n',
            'ArgentumSplat/backend/vendor/model.py': '# model architecture is source code\n',
            'ArgentumSplat/backend/vendor/LICENSE': 'Upstream notice\n',
            'ArgentumSplat/backend/requirements.txt': 'Pillow\n',
            'ArgentumSplat/backend/formats/package-lock.json': '{}\n',
            'ArgentumSplat/backend/licenses/sources.json': '{}\n',
            'ArgentumSplat/res/argentum_splat.png': 'image fixture',
            'ArgentumSplat/res/description/oargentumsplat.h': '# resource identifiers\n',
            'ArgentumSplat/res/description/oargentumsplat.res': 'resource fixture\n',
            'ArgentumSplat/res/strings_us/description/oargentumsplat.str': 'strings fixture\n',
            'docs/media/reference.gif': 'animation fixture',
            'docs/installation.md': '# Installation\n',
            **{name:'# Public release document\n' for name in builder.ROOT_FILES},
        }
        for relative, data in self.shipped.items():
            self.write(relative, data)

    def write(self, relative, data='private fixture'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding='utf8')

    def build(self):
        with redirect_stdout(io.StringIO()):
            return builder.build_release(self.root)

    def test_archive_excludes_runtime_secrets_caches_and_downloaded_binaries(self):
        excluded = (
            'ArgentumSplat/.env', 'ArgentumSplat/.env.local',
            'ArgentumSplat/.git/config', 'ArgentumSplat/.venv/Lib/site-packages/private.py',
            'ArgentumSplat/venv/Lib/site-packages/private.py',
            'ArgentumSplat/backend/node_modules/dependency/package.json',
            'ArgentumSplat/backend/runtime/config.json', 'ArgentumSplat/backend/Runtime/private.py',
            'ArgentumSplat/backend/models/model.py', 'ArgentumSplat/backend/weights/config.json',
            'ArgentumSplat/backend/checkpoints/config.json', 'ArgentumSplat/backend/wheel-cache/metadata.json',
            'ArgentumSplat/backend/runtime.json', 'ArgentumSplat/backend/setup-result.json',
            'ArgentumSplat/backend/credentials.json', 'ArgentumSplat/backend/secrets.txt',
            'ArgentumSplat/backend/config.local.json', 'ArgentumSplat/backend/token.txt',
            'ArgentumSplat/backend/private.pem', 'ArgentumSplat/backend/private.key',
            'ArgentumSplat/backend/python.exe', 'ArgentumSplat/backend/dependency.dll',
            'ArgentumSplat/backend/model.safetensors', 'ArgentumSplat/backend/model.pth',
            'ArgentumSplat/backend/model.bin', 'ArgentumSplat/backend/model.onnx',
            'ArgentumSplat/argentum_splat/__pycache__/core.pyc',
            'ArgentumSplat/argentum_splat/core.pyo', 'ArgentumSplat/backend/setup.log',
            'ArgentumSplat/backend/TRACE.LOG', 'docs/cache/report.md', 'docs/caches/report.md',
            'docs/generated/scan.png', 'docs/converted/scan.ply', 'docs/backups/source.py',
            'docs/temp/report.json', 'docs/.private/notes.md', 'docs/.DS_Store',
            'work/private.md', 'tests/private.py', 'runtime/private.py',
        )
        for relative in excluded:
            self.write(relative)
        archive = self.build()
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(set(package.namelist()), set(self.shipped))
            for relative in self.shipped:
                self.assertEqual(package.read(relative), (self.root/relative).read_bytes())

    def test_archive_version_and_checksum_match_packaged_literal_metadata(self):
        archive = self.build()
        self.assertEqual(archive.name,'ArgentumSplat-1.2.3-rc.1-C4D2027-Windows.zip')
        with zipfile.ZipFile(archive) as package:
            source = package.read('ArgentumSplat/argentum_splat/__init__.py').decode('utf8')
            self.assertIn('__version__ = "1.2.3-rc.1"',source)
        expected = hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n'
        self.assertEqual((archive.parent/'SHA256SUMS.txt').read_text(encoding='ascii'),expected)

    def test_only_declared_checksum_verified_wheel_is_packaged(self):
        data = b'pinned wheel fixture'
        name = 'numpy-test.whl'
        self.write('ArgentumSplat/argentum_splat/numeric_runtime.py',
                   'WHEEL = '+repr(name)+'\nSHA256 = '+repr(hashlib.sha256(data).hexdigest())+'\n')
        wheel = self.root/'ArgentumSplat/vendor'/name
        wheel.parent.mkdir(parents=True, exist_ok=True)
        wheel.write_bytes(data)
        self.write('ArgentumSplat/vendor/unrelated.whl')
        with zipfile.ZipFile(self.build()) as archive:
            self.assertEqual(archive.read('ArgentumSplat/vendor/'+name), data)
            self.assertNotIn('ArgentumSplat/vendor/unrelated.whl', archive.namelist())
        wheel.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'Missing or corrupt'):
            self.build()
        wheel.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing or corrupt'):
            self.build()

    def test_missing_public_documents_and_invalid_versions_fail_before_packaging(self):
        version_file = 'ArgentumSplat/argentum_splat/__init__.py'
        for value in ('../outside', '0.8.2/elsewhere', '0.8.2\\elsewhere', 'latest'):
            self.write(version_file, '__version__ = '+repr(value)+'\n')
            with self.subTest(version=value), self.assertRaisesRegex(ValueError,'semantic'):
                self.build()
            self.assertFalse((self.root/'dist').exists())
        self.write(version_file, '__version__ = "0.8.2"\n')
        (self.root/'LICENSE').unlink()
        with self.assertRaisesRegex(ValueError,'release document'):
            self.build()
        self.assertFalse((self.root/'dist').exists())


if __name__ == '__main__': unittest.main()
