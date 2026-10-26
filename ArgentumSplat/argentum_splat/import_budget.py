"""Import presets, bounded header inspection and conservative RAM admission.

The estimate covers a new CPU-side source, preparation and native card copies.
It is not a VRAM measurement or a promise that Redshift will fit the scene.
"""
from functools import lru_cache
import gzip
import json
import os
from pathlib import Path
import struct
import zipfile
from . import core

PRESETS = {1: 250_000, 2: 1_000_000, 3: 4_000_000, 4: 0}
LABELS = {0: 'CUSTOM — Advanced limit', 1: 'LOW — 250,000',
          2: 'MEDIUM — 1,000,000', 3: 'HIGH — 4,000,000',
          4: 'MAX — Full Source'}
LARGE_SOURCE = 4_000_000


def preset_for(limit):
    return next((key for key, value in PRESETS.items() if value == limit), 0)


def retained_upper_bound(count, limit):
    return count if limit == 0 else min(count, limit)


@lru_cache(maxsize=32)
def _probe(path, mtime, size):
    suffix = Path(path).suffix.lower()
    count = None
    if suffix == '.sog':
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo('meta.json')
            if info.file_size > core.MAX_HEADER_BYTES:
                raise ValueError('Oversized SOG metadata.')
            meta = json.loads(archive.read(info))
            count = meta.get('count')
    elif suffix == '.ply':
        with open(path, 'rb') as stream:
            _, elements, _ = core._header(stream)
        vertex = next((e for e in elements if e.name == 'vertex'), None)
        count = vertex.count if vertex is not None else None
    elif suffix == '.splat':
        if size % 32:
            raise ValueError('Truncated SPLAT file.')
        count = size // 32
    elif suffix == '.spz':
        with open(path, 'rb') as stream:
            signature = stream.read(4)
        if signature[:2] == b'\x1f\x8b':
            with gzip.open(path, 'rb') as stream:
                header = stream.read(16)
        else:
            with open(path, 'rb') as stream:
                header = stream.read(16)
        if len(header) == 16 and header[:4] == b'NGSP':
            count = struct.unpack_from('<I', header, 8)[0]
    if count is not None and (isinstance(count, bool) or not isinstance(count, int)
                              or not 0 <= count <= core.MAX_RECORDS):
        raise ValueError('Invalid source splat count.')
    return count


def source_count(path):
    path = Path(path).resolve()
    stat = path.stat()
    return _probe(str(path), stat.st_mtime_ns, stat.st_size)


def estimate(count, limit):
    retained = retained_upper_bound(count, limit)
    # Includes transient arrays and native caches. Measured peak also depends on
    # visibility, renderer copies, other objects and the file's attribute layout.
    return retained, retained * 1400, retained * 2600


def plan(path, limit):
    count = source_count(path)
    if count is None:
        return 'Source count available after conversion. MAX keeps all opacity-eligible splats.'
    retained, low, high = estimate(count, limit)
    return ('Up to {:,} / {:,} source splats (before opacity filter).\n'
            'Estimated additional RAM: {:.1f}–{:.1f} GiB; VRAM depends on Redshift.').format(
                retained, count, low / 2**30, high / 2**30)


def available_memory():
    if os.name != 'nt':
        return None
    import ctypes
    class Status(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ('total', 'available', 'page_total', 'page_available', 'virtual_total',
             'virtual_available', 'extended')]
    state = Status()
    state.length = ctypes.sizeof(state)
    return state.available if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)) else None


def check_memory(count, limit, available=None):
    """Refuse an unsafe allocation; never silently reduce MAX to a sample."""
    if count is None:
        return
    available = available_memory() if available is None else available
    if available is None:
        return
    _, needed, _ = estimate(count, limit)
    if needed + 1024**3 > available:
        raise MemoryError(
            'Import needs approximately {:.1f}–{:.1f} GiB additional RAM; {:.1f} GiB is free. '
            'Choose LOW / MEDIUM / HIGH, close other scenes, or free memory, then Reload. '
            'The previous complete model is preserved; MAX is never silently sampled.'.format(
                needed / 2**30, estimate(count, limit)[2] / 2**30, available / 2**30))


def check_card_memory(card_count, available=None):
    """Recheck actual visible native cards after CPU preparation is resident.

    One card stores four float64 points (96 B), a polygon (16 B), UVs (96 B),
    colour (64 B), four scalar maps (64 B), and normals (about 24 B). Reserve
    1024 B per visible card for the mesh, its display clone, temporary alpha
    arrays and native allocator overhead. Already resident source/preparation
    and old complete models are reflected in available RAM, not counted twice.
    Redshift's own render/BVH/VRAM allocation remains outside this CPU guard.
    """
    if isinstance(card_count, bool) or not isinstance(card_count, int) or card_count < 0:
        raise ValueError('Visible Gaussian card count must be a nonnegative integer.')
    if not card_count:
        return
    available = available_memory() if available is None else available
    if available is None:
        return
    needed = card_count * 1024
    if needed + 1024**3 > available:
        raise MemoryError(
            'The current view needs {:,} Gaussian cards (approximately {:.1f} GiB '
            'for native geometry and its display copy); {:.1f} GiB RAM is free '
            'after source preparation. Choose a lower Import Quality, close other '
            'scenes, or free memory, then Reload. The previous complete model is '
            'preserved; source detail is never silently reduced.'.format(
                card_count, needed / 2**30, available / 2**30))
