"""Dependency-free SPZ v2/v3 reader with explicit RUB/RDF conversion.

The wire layout and decoding mathematics follow the primary implementation:
https://github.com/nianticlabs/spz (src/cc/load-spz.cc, splat-utils.h,
splat-types.h). Quantized rotations and SH parity are adapted under MIT:

Copyright (c) 2025 Niantic Labs
Copyright (c) 2025 Adobe Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Decompression is streamed to an anonymous temporary file, bounded by the
validated header, then mapped read-only. No full decompressed byte copy is
retained. The output sample is bounded and selected across all source records.
Version 4 requires a separate ZSTD/extension implementation and is refused.
"""
from __future__ import annotations

import gzip
import io
import math
import mmap
from pathlib import Path
import struct
import tempfile
import zlib

from .core import (
    MAX_RECORDS, MAX_RETAINED, SH_C0, Splat, SplatFormatError, _Sampler,
    _quaternion, _space,
)


MAGIC = 0x5053474E
HEADER = struct.Struct("<IIIBBBB")
MAX_DECOMPRESSED_BYTES = 512 * 1024 * 1024
_SH_DIMS = (0, 3, 8, 15)
# RUB -> RDF: x=+1, y=-1, z=-1, in the standard real SH basis.
_RUB_RDF_SH_SIGNS = (-1, -1, 1, -1, 1, 1, -1, 1, -1, 1, -1, -1, 1, -1, 1)


def coordinate_metadata(version, unconverted_coordinates=False):
    """Describe the conversion chosen for a supported SPZ version."""
    if version not in (2, 3):
        raise SplatFormatError(f"SPZ version {version} is unsupported; use v2, v3 or PLY.")
    return {
        "spz_version": version,
        "source_coordinates": "RUB",
        "coordinates": "RUB" if unconverted_coordinates else "RDF",
        "unconverted_coordinates": bool(unconverted_coordinates),
        "coordinate_conversion": (
            "none (native SPZ Right/Up/Back)"
            if unconverted_coordinates
            else "RUB to RDF: flip Y and Z; rotate quaternion and SH consistently"
        ),
        "rotation_encoding": "xyz8" if version == 2 else "smallest-three32",
    }


def _options(max_splats, min_opacity, color_space):
    if isinstance(max_splats, bool) or not isinstance(max_splats, int) or not 1 <= max_splats <= MAX_RETAINED:
        raise ValueError(f"max_splats must be an integer from 1 to {MAX_RETAINED:,}.")
    if (isinstance(min_opacity, bool) or not isinstance(min_opacity, (int, float))
            or not math.isfinite(min_opacity) or not 0 <= min_opacity <= 1):
        raise ValueError("min_opacity must be finite and between 0 and 1.")
    return _space(color_space)


def _signed24(data, offset):
    value = data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)
    return value - 0x1000000 if value & 0x800000 else value


def _rotation(data, offset, version, index):
    if version == 2:
        xyz = tuple(data[offset + axis] / 127.5 - 1.0 for axis in range(3))
        squared = sum(value * value for value in xyz)
        # Valid 8-bit quantization can make the squared length slightly > 1.
        if squared > 1.025:
            raise SplatFormatError(f"SPZ record {index}: invalid v2 quaternion.")
        q = (math.sqrt(max(0.0, 1.0 - squared)),) + xyz
    else:
        packed = struct.unpack_from("<I", data, offset)[0]
        largest = packed >> 30
        xyzw = [0.0] * 4
        for axis in range(3, -1, -1):
            if axis == largest:
                continue
            magnitude = packed & 511
            sign = -1 if packed & 512 else 1
            xyzw[axis] = sign * math.sqrt(0.5) * magnitude / 511.0
            packed >>= 10
        squared = sum(value * value for value in xyzw)
        if squared > 1.0:
            raise SplatFormatError(f"SPZ record {index}: invalid v3 quaternion.")
        xyzw[largest] = math.sqrt(1.0 - squared)
        q = (xyzw[3], xyzw[0], xyzw[1], xyzw[2])
    return _quaternion(q, f"SPZ record {index}")


def _header(data):
    if len(data) != HEADER.size:
        raise SplatFormatError("SPZ has a truncated header.")
    magic, version, count, degree, bits, flags, reserved = HEADER.unpack(data)
    if magic != MAGIC:
        raise SplatFormatError("SPZ magic is missing from the decompressed header.")
    if version == 4:
        raise SplatFormatError(
            "SPZ v4 uses ZSTD streams and is not supported by this build. "
            "Convert it to PLY or SPZ v2/v3 with the official SPZ tools."
        )
    if version not in (2, 3):
        raise SplatFormatError(f"Unsupported SPZ version {version}; use v2, v3 or PLY.")
    if not 1 <= count <= MAX_RECORDS:
        raise SplatFormatError(f"SPZ point count must be 1..{MAX_RECORDS:,}.")
    if degree not in range(4):
        raise SplatFormatError("SPZ SH degree must be 0..3 in this build; degree 4 is unsupported.")
    if not 0 <= bits <= 24:
        raise SplatFormatError("SPZ fractional bits must be in the range 0..24.")
    if flags & 2:
        raise SplatFormatError(
            "SPZ vendor extensions are unsupported and may change coordinate interpretation. "
            "Export a standard SPZ v2/v3 or PLY."
        )
    if flags & ~1 or reserved:
        raise SplatFormatError("SPZ contains unsupported header flags or reserved data.")
    rotation_bytes = 3 if version == 2 else 4
    size = count * (9 + 1 + 3 + 3 + rotation_bytes + 3 * _SH_DIMS[degree])
    if size > MAX_DECOMPRESSED_BYTES:
        raise SplatFormatError(
            f"SPZ decompressed attributes exceed the {MAX_DECOMPRESSED_BYTES // (1024*1024)} MiB limit. "
            "Reduce the source cloud or export PLY."
        )
    return version, count, degree, bits, flags, size


def _decode_arrays(data, header, max_splats, min_opacity, requested_space, unconverted, progress=None):
    version, count, degree, fractional_bits, flags, unused_size = header
    rotation_bytes = 3 if version == 2 else 4
    sh_dim = _SH_DIMS[degree]
    alpha_start = 9 * count
    color_start = alpha_start + count
    scale_start = color_start + 3 * count
    rotation_start = scale_start + 3 * count
    sh_start = rotation_start + rotation_bytes * count
    coordinate_scale = 2.0 ** (-fractional_bits)
    sampler = _Sampler(max_splats, min_opacity, progress)
    for index in range(count):
        if index % 2048 == 0:
            sampler.report('Read SPZ', index, count)
        position = tuple(_signed24(data, index * 9 + axis * 3) * coordinate_scale for axis in range(3))
        alpha = data[alpha_start + index] / 255.0
        raw_color = tuple(
            0.5 + SH_C0 * ((data[color_start + index * 3 + axis] / 255.0 - 0.5) / 0.15)
            for axis in range(3)
        )
        scales = tuple(math.exp(data[scale_start + index * 3 + axis] / 16.0 - 10.0) for axis in range(3))
        rotation = _rotation(data, rotation_start + index * rotation_bytes, version, index)
        # Wire is coefficient-major RGB; core uses channel-major PLY f_rest.
        sh = tuple(
            (data[sh_start + index * sh_dim * 3 + coefficient * 3 + channel] - 128.0) / 128.0
            * (1 if unconverted else _RUB_RDF_SH_SIGNS[coefficient])
            for channel in range(3) for coefficient in range(sh_dim)
        )
        if not unconverted:
            position = (position[0], -position[1], -position[2])
            rotation = (rotation[0], rotation[1], -rotation[2], -rotation[3])
        sampler.add(index, Splat(position, raw_color, alpha, scales, rotation, sh, raw_color))
    metadata = {
        "format": "spz", "encoding": "gzip", "kind": "gaussian",
        "has_sh": bool(sh_dim), "sh_degree": degree, "source_color_space": None,
        "color_space_assumed": requested_space == "auto",
        "antialiased": bool(flags & 1), "fractional_bits": fractional_bits,
    }
    metadata.update(coordinate_metadata(version, unconverted))
    return sampler.finish(count, metadata, "srgb" if requested_space == "auto" else requested_space)


def _load_stream(stream, max_splats, min_opacity, unconverted, requested_space, progress=None):
    signature = stream.read(8)
    stream.seek(0)
    if signature[:4] == b"NGSP":
        version = struct.unpack("<I", signature[4:8])[0] if len(signature) == 8 else "unknown"
        raise SplatFormatError(
            f"SPZ v{version} plaintext/ZSTD format is unsupported. "
            "Convert it to PLY or gzip SPZ v2/v3 with the official SPZ tools."
        )
    if signature[:2] != b"\x1f\x8b":
        raise SplatFormatError("SPZ v2/v3 must be a gzip stream.")
    try:
        with gzip.GzipFile(fileobj=stream, mode="rb") as compressed:
            header = _header(compressed.read(HEADER.size))
            remaining = header[-1]
            with tempfile.TemporaryFile(prefix="argentum_spz_") as spool:
                while remaining:
                    if progress:
                        progress('Decompress SPZ', header[-1] - remaining, header[-1])
                    block = compressed.read(min(1024 * 1024, remaining))
                    if not block:
                        raise SplatFormatError("SPZ attribute data is truncated.")
                    spool.write(block)
                    remaining -= len(block)
                # This also forces CRC/length validation by gzip at EOF.
                if compressed.read(1):
                    raise SplatFormatError("SPZ has unexpected trailing attribute data.")
                spool.flush()
                with mmap.mmap(spool.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
                    return _decode_arrays(mapped, header, max_splats, min_opacity, requested_space, unconverted, progress)
    except (gzip.BadGzipFile, EOFError, zlib.error) as error:
        raise SplatFormatError("SPZ gzip stream is corrupt or truncated: " + str(error)) from error


def load_spz(path, max_splats=60000, min_opacity=0.02, unconverted_coordinates=False, color_space="auto", progress=None):
    """Read SPZ v2/v3 to SplatCloud; normally convert native RUB into RDF.

    ``unconverted_coordinates=True`` preserves source means, quaternions and
    SH coefficients. Source color transfer is not recorded in these versions;
    auto assumes sRGB, exactly as the PLY reader, and records that assumption.
    """
    requested_space = _options(max_splats, min_opacity, color_space)
    path = Path(path)
    with path.open("rb") as stream:
        cloud = _load_stream(stream, max_splats, min_opacity, bool(unconverted_coordinates), requested_space, progress)
    cloud.metadata["source"] = str(path.resolve())
    return cloud


def decode_spz(data, max_splats=60000, min_opacity=0.02, unconverted_coordinates=False, color_space="auto"):
    """Decode bytes using the same bounded parser, primarily for import bridges."""
    requested_space = _options(max_splats, min_opacity, color_space)
    return _load_stream(io.BytesIO(data), max_splats, min_opacity, bool(unconverted_coordinates), requested_space)
