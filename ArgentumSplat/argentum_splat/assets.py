"""Cinema 4D asset collection and portable converted-file references.

No files are moved here: Save Project owns the copy operation. The source image,
splat source, and generated PLY cache are reported through the documented
MSG_GETALLASSETS contract. MSG_MULTI_CLEARSUGGESTEDFOLDER makes their references
relative after collection. Same-name file collision renaming is not exposed by
the Python MSG_RENAMETEXTURES API; use distinct source basenames when collecting.
"""
import hashlib
import json
import os
from pathlib import Path

import c4d
from . import ids as I

_HASH_CACHE = {}
_ASSET_PARAMETERS = (I.FILE, I.IMAGE, I.CACHE_FILE)


def resolve_path(op, value):
    """Resolve a project asset, including Save Project's conventional tex folder."""
    text = str(value or "")
    if not text:
        return ""
    path = Path(text)
    document = op.GetDocument()
    root = Path(document.GetDocumentPath()) if document and document.GetDocumentPath() else None
    if path.is_absolute() and path.exists():
        return str(path)
    candidates = []
    if root is not None:
        if not path.is_absolute():
            candidates.extend((root / path, root / "tex" / path))
        candidates.extend((root / path.name, root / "tex" / path.name))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    if not path.is_absolute() and root is not None:
        return str(root / path)
    return text


def _digest(path):
    path = Path(path).resolve()
    stat = path.stat()
    key = (os.path.normcase(str(path)), stat.st_mtime_ns, stat.st_size)
    if key not in _HASH_CACHE:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        if len(_HASH_CACHE) >= 16:
            _HASH_CACHE.pop(next(iter(_HASH_CACHE)))
        _HASH_CACHE[key] = digest.hexdigest()
    return _HASH_CACHE[key]


def cache_source_matches(source, stored_signature):
    """Accept the original stat signature, or a content signature after packing."""
    try:
        signature = json.loads(str(stored_signature or ""))
        path = Path(source).resolve()
        stat = path.stat()
        if isinstance(signature, list) and len(signature) == 3:
            original, mtime_ns, size = signature
            return (os.path.normcase(str(path)) == os.path.normcase(str(original))
                    and stat.st_mtime_ns == mtime_ns and stat.st_size == size)
        if isinstance(signature, dict) and signature.get("format") == "argentum-source-sha256-v1":
            return (stat.st_size == signature.get("size")
                    and _digest(path) == signature.get("sha256"))
    except (OSError, ValueError, TypeError):
        pass
    return False


def _clear_suggested_folders(op):
    source = resolve_path(op, op[I.FILE])
    cached = resolve_path(op, op[I.CACHE_FILE])
    # Only preserve a cache that was valid before the move. Content identity
    # survives changed absolute directories and copy tools changing timestamps.
    if (source and cached and Path(cached).is_file()
            and cache_source_matches(source, op[I.CACHE_SOURCE])):
        op[I.CACHE_SOURCE] = json.dumps({
            "format": "argentum-source-sha256-v1",
            "size": Path(source).stat().st_size,
            "sha256": _digest(source),
        }, sort_keys=True)
    for parameter in _ASSET_PARAMETERS:
        value = str(op[parameter] or "")
        if value:
            op[parameter] = Path(value).name


def handle_message(op, message, data):
    """Return True when an asset message was handled, False for unrelated input."""
    if message == c4d.MSG_GETALLASSETS:
        if not isinstance(data, dict):
            return True
        output = data.setdefault("assets", [])
        if not isinstance(output, list):
            return True
        texture_only = bool(data.get("flags", 0) & c4d.ASSETDATA_FLAG_TEXTURESONLY)
        seen = set()
        for parameter in _ASSET_PARAMETERS:
            if texture_only and parameter != I.IMAGE:
                continue
            filename = resolve_path(op, op[parameter])
            if not filename:
                continue
            key = os.path.normcase(os.path.abspath(filename))
            if key in seen:
                continue
            seen.add(key)
            output.append({"filename": filename, "bl": op, "netRequestOnDemand": False})
        return True
    if message == c4d.MSG_MULTI_CLEARSUGGESTEDFOLDER:
        _clear_suggested_folders(op)
        return True
    return False
