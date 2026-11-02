"""Install the pinned optional Photos trainer into its private runtime."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from argentum_splat import photos


def install(runtime):
    import pycolmap
    from PIL import Image
    if pycolmap.__version__ != photos.PYCOLMAP_VERSION:
        raise RuntimeError('Photos requires the pinned PyCOLMAP version.')
    runtime = Path(runtime).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    archive = runtime / ('brush-' + photos.BRUSH_VERSION + '.zip')
    if not archive.is_file() or photos.digest(archive) != photos.BRUSH_SHA256:
        partial = archive.with_suffix('.download')
        with urllib.request.urlopen(photos.BRUSH_URL, timeout=90) as source, partial.open('wb') as target:
            while block := source.read(1024*1024):
                target.write(block)
        if photos.digest(partial) != photos.BRUSH_SHA256:
            raise RuntimeError('Brush download checksum failed; installation was not activated.')
        partial.replace(archive)
    destination = runtime / ('brush-' + photos.BRUSH_VERSION)
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        # The pinned release contains four flat files. Never extract arbitrary paths.
        expected = {'brush_app.exe', 'LICENSE', 'README.md', 'CHANGELOG.md'}
        if set(package.namelist()) != expected:
            raise RuntimeError('Unexpected files in pinned Brush release.')
        for name in sorted(expected):
            target = destination / name
            temporary = target.with_suffix(target.suffix + '.tmp')
            temporary.write_bytes(package.read(name))
            temporary.replace(target)
    executable = destination / 'brush_app.exe'
    checked = subprocess.run([str(executable), '--version'], capture_output=True, text=True,
        timeout=30, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if photos.BRUSH_VERSION not in checked.stdout:
        raise RuntimeError('Unexpected Brush version.')
    data = dict(schema=1, python_exe=sys.executable, brush_exe=str(executable),
        brush_sha256=photos.digest(executable), brush_archive_sha256=photos.BRUSH_SHA256,
        brush_version=photos.BRUSH_VERSION, pycolmap_version=pycolmap.__version__)
    marker = runtime / 'photos-runtime.json'
    tmp = marker.with_suffix('.tmp'); tmp.write_text(json.dumps(data, indent=2), encoding='utf8'); tmp.replace(marker)
    print(json.dumps(dict(ok=True, runtime=str(marker))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-dir', required=True)
    install(parser.parse_args().runtime_dir)
