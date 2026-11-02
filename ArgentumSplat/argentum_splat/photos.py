"""Shared, host-independent contract for multi-photo reconstruction."""
from pathlib import Path
import hashlib
import math

EXTENSIONS = frozenset('.jpg .jpeg .png .webp .tif .tiff .bmp'.split())
BRUSH_VERSION = '0.3.0'
BRUSH_URL = 'https://github.com/ArthurBrussee/brush/releases/download/v0.3.0/brush-app-x86_64-pc-windows-msvc.zip'
BRUSH_SHA256 = 'b68e3e9cf052d51bf3ee30776fa5a364de7f2ba13b58443128ff797bb7bcfcd6'
PYCOLMAP_VERSION = '4.2.1'


def image_files(folder):
    if not str(folder).strip():
        raise ValueError('Choose a Photos Folder first.')
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise ValueError('Choose a Photos Folder containing pictures of the same object or place.')
    files = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS),
                   key=lambda p: p.name.casefold())
    if not 3 <= len(files) <= 500:
        raise ValueError('Photos needs 3–500 still images in one folder; 10 or more overlapping views are recommended.')
    return files


def signature(folder):
    return tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in image_files(folder))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def settings(request):
    color=request.get('training_color', 'linear')
    if color not in ('linear','srgb'):raise ValueError('Training colour must be linear or srgb.')
    result = {'training_color':color}
    for key, default, low, high in (('steps', 30000, 100, 60000),
            ('max_splats', 1000000, 10000, 4000000),
            ('resolution', 1600, 512, 2400), ('seed', 1, 0, 2147483647)):
        value = request.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError('%s must be an integer from %d to %d.' % (key, low, high))
        result[key] = value
    return result


def registration_check(total, names):
    count = len(names)
    if count < max(3, math.ceil(total * .6)):
        raise ValueError('Only %d of %d photos could be aligned. Use sharp, overlapping views of a stationary subject with visible texture.' % (count, total))
    return count


def brush_command(executable, dataset, output, values):
    return [str(executable), str(dataset), '--total-steps', str(values['steps']),
            '--max-splats', str(values['max_splats']), '--max-resolution', str(values['resolution']),
            '--seed', str(values['seed']), '--growth-stop-iter', str(min(15000, values['steps']//2)),
            '--export-every', str(values['steps']),
            '--export-path', str(output), '--export-name', 'reconstruction.ply']
