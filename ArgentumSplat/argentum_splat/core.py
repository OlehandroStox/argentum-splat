"""Dependency-free, bounded readers for ordinary 3D Gaussian PLY and SPLAT.

All file coordinates and standard deviations remain in the source's units.
``color`` is linear sRGB; ``raw_color`` and ``sh`` retain the source transfer
function so that view-dependent SH can be evaluated before color conversion.

PLY itself does not define a transfer function. In auto mode, explicit
color_space metadata wins; otherwise sRGB is an assumption recorded in metadata.
SHARP writes a supplemental scalar color_space element: 0 = sRGB, 1 = linearRGB.
See apple/ml-sharp src/sharp/utils/{gaussians,color_space}.py. The SPLAT wire
layout follows antimatter15/splat/convert.py, without copying its implementation.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
import math
from pathlib import Path
import random
import re
import struct
from typing import BinaryIO, Iterator

SH_C0 = 0.28209479177387814
MAX_ELEMENTS = 128
MAX_PROPERTIES = 1024
MAX_RECORDS = 100_000_000
MAX_LIST_LENGTH = 1_000_000
MAX_HEADER_BYTES = 1_048_576
MAX_LINE_BYTES = 1_048_576
MAX_RETAINED = 3_000_000

# struct code, integral lower bound, integral upper bound.
_TYPES = {
    "char": ("b", -128, 127), "int8": ("b", -128, 127),
    "uchar": ("B", 0, 255), "uint8": ("B", 0, 255),
    "short": ("h", -32768, 32767), "int16": ("h", -32768, 32767),
    "ushort": ("H", 0, 65535), "uint16": ("H", 0, 65535),
    "int": ("i", -2147483648, 2147483647),
    "int32": ("i", -2147483648, 2147483647),
    "uint": ("I", 0, 4294967295), "uint32": ("I", 0, 4294967295),
    "float": ("f", None, None), "float32": ("f", None, None),
    "double": ("d", None, None), "float64": ("d", None, None),
}


class SplatFormatError(ValueError):
    """Malformed, unsupported, or unreasonably large source data."""


@dataclass(frozen=True)
class Splat:
    position: tuple[float, float, float]
    color: tuple[float, float, float]
    opacity: float
    scales: tuple[float, float, float]
    rotation: tuple[float, float, float, float]  # unit quaternion, wxyz
    sh: tuple[float, ...] = ()  # channel-major f_rest coefficients
    raw_color: tuple[float, ...] = ()
    input_color_space: str = "linear"


@dataclass
class SplatCloud:
    splats: Sequence[Splat]
    total_count: int
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True, eq=False)
class _PackedSplats(Sequence):
    """An immutable in-memory snapshot, expanding only the requested record.

    Each access returns the same ordinary frozen Splat value as the list-based
    reader. Bytes preserve source precision without retaining millions of Python
    float/tuple graphs. Slices share immutable record bytes; iteration is local
    to its caller and does not cache decoded objects or depend on an open file.
    """
    _records: tuple[bytes, ...] = field(repr=False)
    _decode: object = field(repr=False)
    _space: str

    def __len__(self):
        return len(self._records)

    def _value(self, record):
        splat = self._decode(record)
        return replace(splat, color=source_to_linear(splat.raw_color, self._space),
                       input_color_space=self._space)

    def __getitem__(self, index):
        record = self._records[index]
        if isinstance(index, slice):
            return _PackedSplats(record, self._decode, self._space)
        return self._value(record)

    def __iter__(self):
        for record in self._records:
            yield self._value(record)

    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, Sequence):
            return NotImplemented
        return len(self) == len(other) and all(a == b for a, b in zip(self, other))


@dataclass
class _Property:
    name: str
    value_type: str
    count_type: str | None = None


@dataclass
class _Element:
    name: str
    count: int
    properties: list[_Property] = field(default_factory=list)


def _finite(values, context):
    if not all(math.isfinite(v) for v in values):
        raise SplatFormatError(f"{context}: NaN or infinity is not allowed.")


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number.")


def _space(value):
    normalized = str(value).strip().lower().replace("_", "").replace("-", "")
    if normalized in ("srgb", "0"):
        return "srgb"
    if normalized in ("linear", "linearrgb", "linearsrgb", "1"):
        return "linear"
    if normalized == "auto":
        return "auto"
    raise SplatFormatError(f"Unsupported color space {value!r}; use sRGB or linearRGB.")


def source_to_linear(rgb, color_space="srgb"):
    """Decode source RGB to linear sRGB; clips display RGB to [0, 1]."""
    color_space = _space(color_space)
    if color_space == "auto":
        raise ValueError("source_to_linear requires an explicit color space.")
    _finite(rgb, "Color")
    values = tuple(max(0.0, min(1.0, float(c))) for c in rgb)
    if color_space == "linear":
        return values
    return tuple(c / 12.92 if c <= 0.04045 else ((c + .055) / 1.055) ** 2.4
                 for c in values)


def _quaternion(values, context):
    _finite(values, context)
    # Scale first, so finite very large/small components cannot overflow/underflow.
    magnitude = max(abs(v) for v in values)
    if magnitude == 0:
        raise SplatFormatError(f"{context}: zero quaternion.")
    normalized = tuple(v / magnitude for v in values)
    norm = math.sqrt(sum(v * v for v in normalized))
    return tuple(v / norm for v in normalized)


def _sigmoid(value):
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    e = math.exp(value)
    return e / (1.0 + e)


def _scales(logs, context):
    try:
        result = tuple(math.exp(v) for v in logs)
    except OverflowError as exc:
        raise SplatFormatError(f"{context}: scale exponent overflow.") from exc
    if any(not math.isfinite(v) or v <= 0 for v in result):
        raise SplatFormatError(f"{context}: scales must exponentiate to positive finite values.")
    return result


class _Sampler:
    """Deterministic Algorithm R reservoir over all opacity-eligible records."""
    def __init__(self, limit, min_opacity, progress=None, *, compact=False):
        self.limit = limit
        self.min_opacity = min_opacity
        self.items = []
        self.eligible = 0
        self.rng = random.Random(0x415247454E54554D)
        self.minimum = [math.inf] * 3
        self.maximum = [-math.inf] * 3
        self.progress = progress
        self.compact = compact

    def choose(self, index, position, opacity):
        """Reserve a reservoir slot before allocating attributes for a record."""
        for axis, value in enumerate(position):
            if value < self.minimum[axis]:
                self.minimum[axis] = value
            if value > self.maximum[axis]:
                self.maximum[axis] = value
        if opacity < self.min_opacity:
            return None
        self.eligible += 1
        if len(self.items) < self.limit:
            self.items.append(None)
            return len(self.items) - 1
        selected = self.rng.randrange(self.eligible)
        return selected if selected < self.limit else None

    def add(self, index, splat):
        selected = self.choose(index, splat.position, splat.opacity)
        if selected is not None:
            self.items[selected] = (index, splat)

    def report(self, stage, done, total):
        if self.progress is not None:
            self.progress(stage, done, total)

    def finish(self, total, metadata, space, decode=None, *, compact=False):
        if compact and decode is None:
            raise ValueError("Compact Gaussian storage requires a record decoder.")
        metadata.update({
            "eligible_count": self.eligible,
            "filtered_count": total - self.eligible,
            "retained_count": len(self.items),
            "sampling": "deterministic reservoir, all eligible source records",
            "color_space": "linear",
            "input_color_space": space,
            "bounds": (tuple(self.minimum), tuple(self.maximum)) if total else None,
        })
        # Transfer ownership and consume the reservoir while decoding. Keeping
        # the original reservoir alive doubles its references and, for generic
        # readers, retains the old colour/Splat objects until the pass ends.
        items, self.items = self.items, []
        items.sort(key=lambda pair: pair[0])
        splats = []
        records = [] if compact else None
        effective_degree = 0
        declared_degree = metadata.get('sh_degree', 0)
        for i, (_, splat) in enumerate(items):
            if i % 2048 == 0:
                self.report('Decode colour', i, len(items))
            items[i] = None
            if compact:
                records.append(splat)
            if decode is not None:
                splat = decode(splat)
            if effective_degree < declared_degree and splat.sh:
                size = len(splat.sh) // 3
                for band in range(declared_degree, effective_degree, -1):
                    start, end = ((0, 3), (3, 8), (8, 15))[band - 1]
                    if any(splat.sh[channel * size + j] != 0.
                           for channel in range(3) for j in range(start, end)):
                        effective_degree = band
                        break
            # Validate transfer conversion now, even when the record will only
            # be expanded on demand later. A compact load is not lazy validation.
            color = source_to_linear(splat.raw_color, space)
            if not compact:
                splats.append(replace(splat, color=color, input_color_space=space))
        self.report('Decode colour', len(items), len(items))
        metadata['effective_sh_degree'] = effective_degree
        if compact:
            splats = _PackedSplats(tuple(records), decode, space)
        return SplatCloud(splats, total, metadata)


def _header(stream: BinaryIO):
    first = stream.readline(MAX_LINE_BYTES + 1)
    if first not in (b"ply\n", b"ply\r\n"):
        raise SplatFormatError("Not a PLY file (missing 'ply' signature).")
    consumed = len(first)
    elements = []
    comments = []
    fmt = None
    names = set()
    total_records = 0
    while True:
        line = stream.readline(MAX_LINE_BYTES + 1)
        consumed += len(line)
        if not line or len(line) > MAX_LINE_BYTES or consumed > MAX_HEADER_BYTES:
            raise SplatFormatError("Truncated or oversized PLY header.")
        try:
            text = line.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise SplatFormatError("PLY header must be ASCII.") from exc
        words = text.split()
        if not words:
            continue
        keyword = words[0]
        if keyword == "end_header":
            if len(words) != 1 or fmt is None:
                raise SplatFormatError("Invalid PLY end_header or missing format.")
            break
        if keyword in ("comment", "obj_info"):
            comments.append(text[len(keyword):].strip())
        elif keyword == "format":
            if fmt is not None or len(words) != 3 or words[2] != "1.0":
                raise SplatFormatError("Expected one PLY format declaration, version 1.0.")
            fmt = words[1]
            if fmt not in ("ascii", "binary_little_endian", "binary_big_endian"):
                raise SplatFormatError(f"Unsupported PLY encoding: {fmt}.")
        elif keyword == "element":
            if len(words) != 3 or words[1] in names:
                raise SplatFormatError("Invalid or duplicate PLY element.")
            try:
                count = int(words[2], 10)
            except ValueError as exc:
                raise SplatFormatError("Invalid PLY element count.") from exc
            total_records += count
            if count < 0 or count > MAX_RECORDS or total_records > MAX_RECORDS:
                raise SplatFormatError(f"PLY counts exceed the {MAX_RECORDS:,} record limit.")
            if len(elements) >= MAX_ELEMENTS:
                raise SplatFormatError("Too many PLY elements.")
            names.add(words[1])
            elements.append(_Element(words[1], count))
        elif keyword == "property":
            if not elements:
                raise SplatFormatError("PLY property has no preceding element.")
            if len(words) == 3 and words[1] in _TYPES:
                prop = _Property(words[2], words[1])
            elif (len(words) == 5 and words[1] == "list"
                  and words[2] in _TYPES and words[3] in _TYPES):
                if _TYPES[words[2]][1] is None:
                    raise SplatFormatError("PLY list count type must be integral.")
                prop = _Property(words[4], words[3], words[2])
            else:
                raise SplatFormatError(f"Unsupported or malformed PLY property: {text}.")
            properties = elements[-1].properties
            if len(properties) >= MAX_PROPERTIES or any(p.name == prop.name for p in properties):
                raise SplatFormatError("Too many or duplicate PLY properties.")
            properties.append(prop)
        else:
            raise SplatFormatError(f"Unknown PLY header directive: {keyword}.")
    if any(e.count and not e.properties for e in elements):
        raise SplatFormatError("Nonempty PLY elements must declare properties.")
    return fmt, elements, comments


def _parse_scalar(token, value_type, context):
    code, lo, hi = _TYPES[value_type]
    try:
        value = float(token) if lo is None else int(token, 10)
    except ValueError as exc:
        raise SplatFormatError(f"{context}: invalid {value_type} value.") from exc
    if lo is not None and not lo <= value <= hi:
        raise SplatFormatError(f"{context}: {value_type} value is out of range.")
    if lo is None:
        if not math.isfinite(value):
            raise SplatFormatError(f"{context}: NaN or infinity is not allowed.")
        if code == "f" and abs(value) > 3.4028234663852886e38:
            raise SplatFormatError(f"{context}: float32 value is out of range.")
    return value


def _ascii_records(stream, element):
    for index in range(element.count):
        context = f"PLY {element.name} record {index}"
        line = stream.readline(MAX_LINE_BYTES + 1)
        if not line or len(line) > MAX_LINE_BYTES:
            raise SplatFormatError(f"{context}: truncated or oversized record.")
        try:
            tokens = line.decode("ascii").split()
        except UnicodeDecodeError as exc:
            raise SplatFormatError(f"{context}: non-ASCII data.") from exc
        cursor = 0
        values = {}
        for prop in element.properties:
            if cursor >= len(tokens):
                raise SplatFormatError(f"{context}: missing property {prop.name}.")
            if prop.count_type:
                count = _parse_scalar(tokens[cursor], prop.count_type, context)
                cursor += 1
                if count < 0 or count > MAX_LIST_LENGTH:
                    raise SplatFormatError(f"{context}: invalid or oversized list.")
                if cursor + count > len(tokens):
                    raise SplatFormatError(f"{context}: truncated list {prop.name}.")
                # Validate ignored list values too, without allocating their contents.
                for token in tokens[cursor:cursor + count]:
                    _parse_scalar(token, prop.value_type, context)
                cursor += count
            else:
                values[prop.name] = _parse_scalar(tokens[cursor], prop.value_type, context)
                cursor += 1
        if cursor != len(tokens):
            raise SplatFormatError(f"{context}: unexpected extra values.")
        yield values


def _read_exact(stream, count, context):
    data = stream.read(count)
    if len(data) != count:
        raise SplatFormatError(f"{context}: truncated binary data.")
    return data


def _binary_records(stream, element, endian):
    props = element.properties
    if all(p.count_type is None for p in props):
        codec = struct.Struct(endian + "".join(_TYPES[p.value_type][0] for p in props))
        names = [p.name for p in props]
        # Process at most 1 MiB at a time, independent of file size.
        block_records = max(1, 1_048_576 // max(1, codec.size))
        for start in range(0, element.count, block_records):
            count = min(block_records, element.count - start)
            block = _read_exact(stream, count * codec.size, f"PLY {element.name}")
            for offset, values in enumerate(codec.iter_unpack(block)):
                _finite(values, f"PLY {element.name} record {start + offset}")
                yield dict(zip(names, values))
        return
    codecs = {name: struct.Struct(endian + spec[0]) for name, spec in _TYPES.items()}
    for index in range(element.count):
        context = f"PLY {element.name} record {index}"
        values = {}
        for prop in props:
            codec = codecs[prop.value_type]
            if prop.count_type:
                count_codec = codecs[prop.count_type]
                count = count_codec.unpack(_read_exact(stream, count_codec.size, context))[0]
                if count < 0 or count > MAX_LIST_LENGTH:
                    raise SplatFormatError(f"{context}: invalid or oversized list.")
                for start in range(0, count, 4096):
                    size = min(4096, count - start)
                    block = _read_exact(stream, size * codec.size, context)
                    for item in codec.iter_unpack(block):
                        _finite(item, context)
            else:
                value = codec.unpack(_read_exact(stream, codec.size, context))[0]
                _finite((value,), context)
                values[prop.name] = value
        yield values


def _vertex_schema(vertex, point_radius):
    props = {p.name: p for p in vertex.properties}
    if any(p.count_type for p in vertex.properties):
        raise SplatFormatError("List properties on PLY vertices are not supported.")
    if not {"x", "y", "z"} <= props.keys():
        raise SplatFormatError("PLY vertices require scalar x, y, z.")
    required = ({f"f_dc_{i}" for i in range(3)} | {"opacity"}
                | {f"scale_{i}" for i in range(3)} | {f"rot_{i}" for i in range(4)})
    gaussian_markers = {name for name in props if name.startswith(("f_dc_", "scale_", "rot_", "f_rest_"))}
    gaussian = bool(gaussian_markers)
    if gaussian and not required <= props.keys():
        raise SplatFormatError("Incomplete Gaussian PLY. Missing: " +
                               ", ".join(sorted(required - props.keys())) + ".")
    rest = [name for name in props if name.startswith("f_rest_")]
    if len(rest) not in (0, 9, 24, 45) or set(rest) != {f"f_rest_{i}" for i in range(len(rest))}:
        raise SplatFormatError("SH coefficients must be contiguous f_rest_0..N for degree 1, 2, or 3.")
    if not gaussian:
        if not {"red", "green", "blue"} <= props.keys():
            raise SplatFormatError("PLY must contain complete Gaussian fields or red, green, blue.")
        _positive(point_radius, "point_radius")
        for name in ("red", "green", "blue", "alpha"):
            if name in props:
                kind = _TYPES[props[name].value_type][0]
                if kind not in ("B", "f", "d"):
                    raise SplatFormatError("Point-cloud RGB/alpha must be uchar 0..255 or float 0..1.")
    return gaussian, props, len(rest)


def _make_vertex(values, index, gaussian, props, rest_count, point_radius):
    context = f"PLY vertex {index}"
    position = tuple(float(values[k]) for k in ("x", "y", "z"))
    if gaussian:
        raw = tuple(.5 + SH_C0 * values[f"f_dc_{i}"] for i in range(3))
        _finite(raw, context)
        scales = _scales((values[f"scale_{i}"] for i in range(3)), context)
        rotation = _quaternion(tuple(values[f"rot_{i}"] for i in range(4)), context)
        opacity = _sigmoid(values["opacity"])
        sh = tuple(float(values[f"f_rest_{i}"]) for i in range(rest_count))
    else:
        def channel(name):
            divisor = 255.0 if _TYPES[props[name].value_type][0] == "B" else 1.0
            result = values[name] / divisor
            if not 0 <= result <= 1:
                raise SplatFormatError(f"{context}: RGB/alpha outside the declared [0, 1] range.")
            return result
        raw = tuple(channel(k) for k in ("red", "green", "blue"))
        opacity = channel("alpha") if "alpha" in props else 1.0
        scales = (float(point_radius),) * 3
        rotation = (1.0, 0.0, 0.0, 0.0)
        sh = ()
    return Splat(position, raw, opacity, scales, rotation, sh, raw, "linear")


def _load_binary_gaussians(stream, vertex, endian, sampler, rest_count):
    """Validate every scalar, retaining compact records until sampling finishes.

    The same reservoir and validation rules apply to the generic reader. Large
    SH scans avoid materialising coefficient tuples for reservoir entries which
    will later be replaced. Store the original bytes, including double precision
    and arbitrary property order, then decode each final selected record once.
    """
    names = [p.name for p in vertex.properties]
    codec = struct.Struct(endian + ''.join(_TYPES[p.value_type][0] for p in vertex.properties))
    xyz = tuple(names.index(k) for k in ('x', 'y', 'z'))
    dc = tuple(names.index('f_dc_%d' % i) for i in range(3))
    scales_ix = tuple(names.index('scale_%d' % i) for i in range(3))
    rotation_ix = tuple(names.index('rot_%d' % i) for i in range(4))
    rest_ix = tuple(names.index('f_rest_%d' % i) for i in range(rest_count))
    opacity_ix = names.index('opacity')
    block_records = max(1, 1048576 // codec.size)
    for start in range(0, vertex.count, block_records):
        sampler.report('Read PLY', start, vertex.count)
        count = min(block_records, vertex.count - start)
        block = _read_exact(stream, count * codec.size, 'PLY vertex')
        for offset, values in enumerate(codec.iter_unpack(block)):
            index = start + offset
            context = 'PLY vertex %d' % index
            _finite(values, context)
            position = tuple(values[k] for k in xyz)
            _scales((values[k] for k in scales_ix), context)
            rotation = tuple(values[k] for k in rotation_ix)
            if not any(rotation):
                raise SplatFormatError(context + ': zero quaternion.')
            opacity = _sigmoid(values[opacity_ix])
            slot = sampler.choose(index, position, opacity)
            if slot is None:
                continue
            raw = tuple(.5 + SH_C0 * values[k] for k in dc)
            _finite(raw, context)
            byte_offset = offset * codec.size
            sampler.items[slot] = (index, block[byte_offset:byte_offset + codec.size])
    sampler.report('Read PLY', vertex.count, vertex.count)

    def decode(record):
        values = codec.unpack(record)
        raw = tuple(.5 + SH_C0 * values[k] for k in dc)
        return Splat(tuple(values[k] for k in xyz), raw,
                     _sigmoid(values[opacity_ix]),
                     _scales((values[k] for k in scales_ix), 'PLY vertex'),
                     _quaternion(tuple(values[k] for k in rotation_ix), 'PLY vertex'),
                     tuple(values[k] for k in rest_ix), raw, 'linear')

    return decode


def _load_ply(stream, sampler, requested_space, point_radius):
    fmt, elements, comments = _header(stream)
    # PlayCanvas compressed PLY uses chunk bounds plus packed vertex properties.
    if (any(e.name == "chunk" for e in elements)
            or any(p.name.startswith("packed_") for e in elements for p in e.properties)):
        raise SplatFormatError("PlayCanvas compressed PLY is not supported. Export an uncompressed Gaussian PLY.")
    vertex = next((e for e in elements if e.name == "vertex"), None)
    if vertex is None:
        raise SplatFormatError("PLY has no vertex element.")
    gaussian, props, rest_count = _vertex_schema(vertex, point_radius)
    declared_spaces = []
    for comment in comments:
        match = re.fullmatch(r"color[_ ]?space(?:\s*[:=]\s*|\s+)([A-Za-z0-9_-]+)", comment, re.I)
        if match:
            declared_spaces.append(_space(match.group(1)))
    supplements = {}
    decode = None
    for element in elements:
        if element.name == 'vertex' and gaussian and fmt != 'ascii':
            decode = _load_binary_gaussians(stream, element,
                '<' if fmt == 'binary_little_endian' else '>', sampler, rest_count)
            continue
        records = (_ascii_records(stream, element) if fmt == "ascii" else
                   _binary_records(stream, element, "<" if fmt == "binary_little_endian" else ">"))
        for index, values in enumerate(records):
            if index % 2048 == 0:
                sampler.report('Read PLY ' + element.name, index, element.count)
            if element.name == "vertex":
                sampler.add(index, _make_vertex(values, index, gaussian, props, rest_count, point_radius))
            else:
                for key in ("color_space", "intrinsic", "extrinsic", "image_size", "frame", "version"):
                    if key in values:
                        items = supplements.setdefault(key, [])
                        if len(items) >= 256:
                            raise SplatFormatError(f"Oversized PLY {key} metadata.")
                        items.append(values[key])
    remainder = stream.read(1)
    if remainder:
        if fmt != "ascii":
            raise SplatFormatError("Unexpected trailing binary PLY data.")
        while remainder:
            if remainder.strip():
                raise SplatFormatError("Unexpected trailing ASCII PLY data.")
            remainder = stream.read(65536)
    if "color_space" in supplements:
        values = supplements["color_space"]
        if len(values) != 1 or values[0] not in (0, 1):
            raise SplatFormatError("PLY color_space metadata must contain exactly one value, 0 or 1.")
        declared_spaces.append("srgb" if values[0] == 0 else "linear")
    if len(set(declared_spaces)) > 1:
        raise SplatFormatError("Conflicting PLY color_space declarations.")
    explicit = declared_spaces[0] if declared_spaces else None
    if explicit == "auto":
        raise SplatFormatError("File color_space must explicitly identify sRGB or linearRGB.")
    space = requested_space if requested_space != "auto" else (explicit or "srgb")
    degree = {0: 0, 9: 1, 24: 2, 45: 3}[rest_count]
    metadata = {
        "format": "ply", "encoding": fmt, "comments": comments,
        "kind": "gaussian" if gaussian else "point_cloud",
        "has_sh": bool(rest_count), "sh_degree": degree,
        "source_color_space": explicit,
        "color_space_assumed": requested_space == "auto" and explicit is None,
        "supplements": supplements,
    }
    if not gaussian:
        metadata["point_radius"] = point_radius
    return sampler.finish(vertex.count, metadata, space, decode=decode,
                          compact=sampler.compact and decode is not None)


def _load_splat(stream, sampler, requested_space):
    stream.seek(0, 2)
    length = stream.tell()
    stream.seek(0)
    if length % 32:
        raise SplatFormatError("SPLAT is truncated: file length must be a multiple of 32 bytes.")
    count = length // 32
    if count > MAX_RECORDS:
        raise SplatFormatError(f"SPLAT exceeds the {MAX_RECORDS:,} record limit.")
    codec = struct.Struct("<6f8B")
    index = 0
    while index < count:
        sampler.report('Read SPLAT', index, count)
        block_count = min(32768, count - index)
        block = _read_exact(stream, block_count * 32, "SPLAT")
        for values in codec.iter_unpack(block):
            _finite(values[:6], f"SPLAT record {index}")
            scales = tuple(values[3:6])
            if any(v <= 0 for v in scales):
                raise SplatFormatError(f"SPLAT record {index}: scales must be positive.")
            rotation_bytes = values[10:14]
            if all(v == 128 for v in rotation_bytes):
                raise SplatFormatError(f"SPLAT record {index}: zero quaternion.")
            position, opacity = tuple(values[:3]), values[9] / 255.0
            slot = sampler.choose(index, position, opacity)
            if slot is not None:
                # Keep validated scalar data; decode attributes only for the
                # final reservoir, not each record later replaced in it.
                sampler.items[slot] = (index, values)
            index += 1
            if index % 2048 == 0:
                sampler.report('Read SPLAT', index, count)
    space = "srgb" if requested_space == "auto" else requested_space
    def decode(values):
        raw = tuple(c / 255.0 for c in values[6:9])
        rotation = _quaternion(tuple((v - 128) / 128.0 for v in values[10:14]), 'SPLAT')
        return Splat(tuple(values[:3]), raw, values[9] / 255.0,
                     tuple(values[3:6]), rotation, (), raw, 'linear')
    return sampler.finish(count, {
        "format": "splat", "encoding": "binary_little_endian", "kind": "gaussian",
        "has_sh": False, "sh_degree": 0, "source_color_space": None,
        "color_space_assumed": requested_space == "auto",
    }, space, decode)


def load(path, max_splats=60000, min_opacity=0.02, *, point_radius=0.01,
         color_space="auto", unconverted_coordinates=False, progress=None,
         compact=False):
    """Read and validate every source record, retaining a bounded random sample.

    Sampling is deterministic and covers the entire file after opacity filtering.
    Errors in unselected records are still reported. ``total_count`` is the
    original vertex count; metadata includes eligible/filtered/retained counts.
    Point-cloud RGB uses uchar [0,255] or float [0,1], with explicit native-unit
    standard deviation ``point_radius``. Unlabelled files assume sRGB; callers
    may select ``color_space='linear'`` to override that assumption.
    ``unconverted_coordinates`` applies only to SPZ and preserves its raw frame.
    ``compact=True`` keeps binary Gaussian PLY records in an immutable packed
    sequence with len/index/slice/iteration support. Values and validation are
    unchanged; each access creates a transient Splat instead of caching it.
    The default and other formats retain the existing list representation.
    """
    if isinstance(max_splats, bool) or not isinstance(max_splats, int) or not 1 <= max_splats <= MAX_RETAINED:
        raise ValueError(f"max_splats must be an integer from 1 to {MAX_RETAINED:,}.")
    if (isinstance(min_opacity, bool) or not isinstance(min_opacity, (int, float))
            or not math.isfinite(min_opacity) or not 0 <= min_opacity <= 1):
        raise ValueError("min_opacity must be finite and between 0 and 1.")
    if not isinstance(compact, bool):
        raise ValueError("compact must be a boolean.")
    requested_space = _space(color_space)
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".spz":
        from .spz import load_spz
        return load_spz(path, max_splats=max_splats, min_opacity=min_opacity,
                        unconverted_coordinates=unconverted_coordinates,
                        color_space=requested_space, progress=progress)
    sampler = _Sampler(max_splats, min_opacity, progress, compact=compact)
    with path.open("rb") as stream:
        if suffix == ".ply":
            cloud = _load_ply(stream, sampler, requested_space, point_radius)
        elif suffix == ".splat":
            cloud = _load_splat(stream, sampler, requested_space)
        else:
            raise SplatFormatError("Supported input extensions are .ply, .splat, and .spz.")
    cloud.metadata["source"] = str(path.resolve())
    return cloud


def transform_position(position, global_scale=100.0, flip_y=True):
    """Convert OpenCV positions to C4D Y-up coordinates, preserving origin."""
    _positive(global_scale, "global_scale")
    if len(position) != 3:
        raise ValueError("position must contain three coordinates.")
    _finite(position, "Position")
    result = tuple(float(value) * global_scale * (-1 if flip_y and i == 1 else 1)
                   for i, value in enumerate(position))
    _finite(result, "Transformed position")
    return result


def gaussian_axes(splat, global_scale=100.0, splat_scale=1.0, flip_y=True):
    """Return three scaled principal basis vectors suitable for C4D Matrix.

    A Y reflection is applied to both mean (via transform_position) and axes.
    The final axis is then sign-reversed to keep a positive determinant. Axis
    sign does not change a Gaussian covariance: A A^T is unchanged.
    """
    _positive(global_scale, "global_scale")
    _positive(splat_scale, "splat_scale")
    if len(splat.rotation) != 4 or len(splat.scales) != 3:
        raise ValueError("Expected quaternion wxyz and three standard deviations.")
    w, x, y, z = _quaternion(splat.rotation, "Gaussian orientation")
    for value in splat.scales:
        _positive(value, "Gaussian scale")
    columns = ((1 - 2*(y*y + z*z), 2*(x*y + w*z), 2*(x*z - w*y)),
               (2*(x*y - w*z), 1 - 2*(x*x + z*z), 2*(y*z + w*x)),
               (2*(x*z + w*y), 2*(y*z - w*x), 1 - 2*(x*x + y*y)))
    result = []
    for axis, column in enumerate(columns):
        scale = splat.scales[axis] * global_scale * splat_scale
        # Negating column 2 after reflection preserves handedness and covariance.
        sign = -1 if flip_y and axis == 2 else 1
        vector = tuple(v * scale * sign * (-1 if flip_y and i == 1 else 1)
                       for i, v in enumerate(column))
        _finite(vector, "Transformed Gaussian axes")
        result.append(vector)
    return tuple(result)


def evaluate_sh(splat, direction, degree=3, strength=1.0):
    """Evaluate SH0..3 in source RGB, before clipping or transfer conversion.

    ``direction`` points from the camera to the Gaussian in SOURCE coordinates.
    If the object is transformed, transform the direction into the object's
    source frame first. The requested degree is capped at the stored degree.
    ``strength=0`` returns the source DC color; ``strength=1`` is normal SH.
    """
    if isinstance(degree, bool) or not isinstance(degree, int) or not 0 <= degree <= 3:
        raise ValueError("SH degree must be an integer from 0 to 3.")
    if not isinstance(strength, (int, float)) or not math.isfinite(strength):
        raise ValueError("SH strength must be finite.")
    raw = splat.raw_color or splat.color
    if len(raw) != 3 or len(splat.sh) not in (0, 9, 24, 45):
        raise ValueError("Invalid SH coefficient layout.")
    _finite(raw, "DC color")
    _finite(splat.sh, "SH coefficients")
    available = {0: 0, 9: 1, 24: 2, 45: 3}[len(splat.sh)]
    degree = min(degree, available)
    if degree == 0 or strength == 0:
        return tuple(raw)
    if len(direction) != 3:
        raise ValueError("SH direction must have three components.")
    _finite(direction, "SH direction")
    largest = max(abs(v) for v in direction)
    if largest == 0:
        raise ValueError("SH direction cannot be zero.")
    scaled = tuple(v / largest for v in direction)
    length = math.hypot(*scaled)
    x, y, z = (v / length for v in scaled)
    basis = [-0.4886025119029199*y, 0.4886025119029199*z, -0.4886025119029199*x]
    if degree >= 2:
        xx, yy, zz = x*x, y*y, z*z
        basis.extend((1.0925484305920792*x*y, -1.0925484305920792*y*z,
                      0.31539156525252005*(2*zz-xx-yy), -1.0925484305920792*x*z,
                      0.5462742152960396*(xx-yy)))
    if degree >= 3:
        basis.extend((-0.5900435899266435*y*(3*xx-yy), 2.890611442640554*x*y*z,
                      -0.4570457994644658*y*(4*zz-xx-yy),
                      0.3731763325901154*z*(2*zz-3*xx-3*yy),
                      -0.4570457994644658*x*(4*zz-xx-yy),
                      1.445305721320277*z*(xx-yy), -0.5900435899266435*x*(xx-3*yy)))
    channel_size = len(splat.sh) // 3
    result = tuple(raw[channel] + strength * sum(
        basis[i] * splat.sh[channel * channel_size + i] for i in range(len(basis)))
                   for channel in range(3))
    _finite(result, "Evaluated SH color")
    return result
