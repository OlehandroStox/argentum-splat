"""Optional, offline numeric runtime shipped for Cinema 4D 2027 on Windows.

Never download or install into Cinema's Python environment. An existing NumPy
is reused; otherwise the exact bundled wheel is unpacked into our local cache.
The ordinary Python implementation remains available on other platforms.
"""
import hashlib
import importlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
import threading
import zipfile

WHEEL = 'numpy-2.2.6-cp311-cp311-win_amd64.whl'
SHA256 = 'e8213002e427c69c45a52bbd94163084025f533a55a59d6f9c5b820774ef3303'
_lock = threading.RLock()
_module = None
_attempted = False
_error = ''


def _unpack(wheel, parent):
    """Validate the distribution before extracting; publish only a full tree."""
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('Bundled numeric runtime checksum does not match.')
    target = parent / ('numpy-2.2.6-cp311-' + SHA256[:12])
    marker = target / 'ARGENTUM-COMPLETE.txt'
    if marker.is_file() and marker.read_text(encoding='ascii').strip() == SHA256:
        return target
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='numeric-stage-', dir=parent))
    try:
        with zipfile.ZipFile(wheel) as archive:
            if sum(i.file_size for i in archive.infolist()) > 150 * 1024**2:
                raise RuntimeError('Numeric runtime exceeds the extraction limit.')
            for item in archive.infolist():
                name = PurePosixPath(item.filename)
                if (name.is_absolute() or '..' in name.parts or '\\' in item.filename
                        or ':' in item.filename or stat.S_ISLNK(item.external_attr >> 16)):
                    raise RuntimeError('Invalid path in the numeric runtime.')
            archive.extractall(temporary)
        (temporary / marker.name).write_text(SHA256+'\n', encoding='ascii')
        try:
            temporary.rename(target)
        except FileExistsError:
            if not marker.is_file() or marker.read_text(encoding='ascii').strip() != SHA256:
                raise RuntimeError('An incomplete numeric runtime cache already exists.')
        return target
    finally:
        if temporary.exists():
            # mkdtemp created this exact owned directory under the fixed cache.
            if temporary.resolve().parent != parent.resolve():
                raise RuntimeError('Numeric staging path escaped its cache.')
            shutil.rmtree(temporary)


def numpy():
    global _module, _attempted, _error
    with _lock:
        if _attempted:
            return _module
        try:
            _module = importlib.import_module('numpy')
        except (OSError, RuntimeError) as error:
            # A broken third-party native runtime must not disable scalar
            # import. Do not replace another plugin's partially loaded module.
            _error = str(error)
        except ImportError:
            if sys.platform == 'win32' and sys.version_info[:2] == (3, 11):
                wheel = Path(__file__).resolve().parents[1] / 'vendor' / WHEEL
                local = os.environ.get('LOCALAPPDATA')
                if wheel.is_file() and local:
                    try:
                        folder = _unpack(wheel, Path(local) / 'ArgentumSplat' / 'numeric')
                        sys.path.insert(0, str(folder))
                        try:
                            _module = importlib.import_module('numpy')
                        finally:
                            sys.path.remove(str(folder))
                    except Exception as error:
                        _error = str(error)
        _attempted = True
        return _module


def status():
    return {'available': _module is not None,
            'version': getattr(_module, '__version__', None), 'error': _error}
