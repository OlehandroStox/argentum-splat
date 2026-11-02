"""Offline readiness check and driver-only preflight before multi-GB downloads."""
import argparse
import ctypes
import importlib.metadata
import json
from pathlib import Path
import struct
import sys

from bootstrap import MODEL_REVISION, SOURCE_REVISION, WEIGHTS


def gpu_preflight():
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise RuntimeError('Local AI requires Windows x64.')
    try:
        driver = ctypes.WinDLL('nvcuda.dll')
    except OSError as exc:
        raise RuntimeError('NVIDIA CUDA driver not found. Scan import still works; local AI needs an NVIDIA Ampere-or-newer GPU and driver.') from exc
    if driver.cuInit(0) != 0:
        raise RuntimeError('The NVIDIA driver could not initialize CUDA. Restart Windows or update the NVIDIA driver; scan import remains available.')
    device = ctypes.c_int()
    if driver.cuDeviceGet(ctypes.byref(device), 0) != 0:
        raise RuntimeError('No CUDA device 0 is available for local AI.')
    major, minor = ctypes.c_int(), ctypes.c_int()
    if driver.cuDeviceComputeCapability(ctypes.byref(major), ctypes.byref(minor), device) != 0 or major.value < 8:
        raise RuntimeError('Local AI needs an NVIDIA Ampere-or-newer GPU with BF16 support. Scan import remains available.')
    return {'compute_capability': [major.value, minor.value]}


def check_model_files(config, runtime):
    if config.get('model_revision') != MODEL_REVISION or config.get('source_revision') != SOURCE_REVISION:
        raise ValueError('Model/runtime revision changed; setup is required.')
    model_root = runtime / 'models'
    if Path(config['checkpoint_dir']).resolve() != model_root:
        raise ValueError('Model directory was moved; rerun setup.')
    sizes = config.get('model_sizes', {})
    for name in WEIGHTS:
        target = model_root / name
        if name not in config.get('model_sha256', {}) or not target.is_file():
            raise ValueError('Missing model checkpoint: ' + name)
        size = target.stat().st_size
        if size < 1024 or (name in sizes and size != sizes[name]):
            raise ValueError('Incomplete checkpoint: ' + name)
        # Quick structure check; bootstrap.py / -Repair verifies full hashes.
        with target.open('rb') as stream:
            length = struct.unpack('<Q', stream.read(8))[0]
            if length < 2 or length > min(size - 8, 100_000_000):
                raise ValueError('Invalid checkpoint header: ' + name)
            header = json.loads(stream.read(length))
            ends = [item['data_offsets'][1] for key, item in header.items() if key != '__metadata__']
            if not ends or max(ends) + 8 + length != size:
                raise ValueError('Truncated checkpoint data: ' + name)


def check_runtime(runtime):
    runtime = Path(runtime).resolve()
    config = json.loads((runtime / 'runtime.json').read_text(encoding='utf-8-sig'))
    if Path(config['python_exe']).resolve() != Path(sys.executable).resolve():
        raise ValueError('Runtime Python moved; rerun setup.')
    if not (3, 10) <= sys.version_info[:2] <= (3, 12) or struct.calcsize('P') != 8:
        raise ValueError('Python 3.10-3.12 x64 is required.')
    requirements = Path(__file__).with_name('requirements.txt').read_text().splitlines()
    for item in requirements:
        if '==' in item:
            name, version = item.strip().split('==')
            if importlib.metadata.version(name) != version:
                raise ValueError('Package needs setup: ' + name)
    import torch
    import torchvision
    from PIL import Image
    if torch.__version__ != '2.9.1+cu128' or torchvision.__version__.split('+')[0] != '0.24.1':
        raise ValueError('The pinned CUDA packages need setup.')
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError('CUDA / BF16 unavailable. Check the NVIDIA GPU driver.')
    check_model_files(config, runtime)
    return {'gpu': torch.cuda.get_device_name(0), 'python': sys.version.split()[0]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-dir')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    try:
        result = gpu_preflight() if args.preflight else check_runtime(args.runtime_dir)
        print(json.dumps({'ok': True, **result}), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'message': str(exc)}), flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
