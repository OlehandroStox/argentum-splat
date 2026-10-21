"""Optional format conversion through pinned, official PlayCanvas tooling.

No source geometry, SH bands, opacity, or quaternion fields are intentionally
filtered. The output is ordinary binary PLY in the source's PLY-equivalent
coordinate frame, without centering, scaling, or additional rotation.
SPZ is decoded RAW by PlayCanvas; apply any SPZ coordinate correction after
loading this PLY. SOG/KSPLAT quantization already present cannot be reversed.

The direct ``conversion_command`` API is safe to run asynchronously with
subprocess.Popen(argv, shell=False). It never starts a shell and rejects script,
URL, and directory inputs. The CLI wrapper additionally validates all decoded
records and publishes a JSON result after successful conversion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import uuid

PACKAGE_VERSION = "3.10.1"
SUPPORTED_SUFFIXES = {".sog", ".ksplat", ".spz", ".ply", ".splat"}
PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class ConversionError(RuntimeError):
    """An unavailable runtime or failed/invalid format conversion."""


def default_manifest_path():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise ConversionError("LOCALAPPDATA is unavailable; supply an explicit runtime manifest.")
    return Path(base) / "ArgentumSplat" / "formats" / "formats.json"


def needs_conversion(path):
    """Inspect only a small local header; never installs or executes anything.

    Regular Gaussian PLY, SPLAT and gzip SPZ2/3 use the native Python readers.
    Bundled SOG, KSPLAT, plaintext SPZ4 and packed PlayCanvas PLY use the
    optional converter. A malformed or unknown source remains a reader error.
    """
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in (".sog", ".ksplat"):
        return True
    if suffix == ".spz":
        with source.open("rb") as stream:
            header = stream.read(8)
        return len(header) == 8 and header[:4] == b"NGSP" and struct.unpack("<I", header[4:])[0] == 4
    if suffix != ".ply":
        return False
    with source.open("rb") as stream:
        if stream.readline(16).strip() != b"ply":
            return False
        consumed = 0
        while consumed < 1_048_576:
            line = stream.readline(65_537)
            consumed += len(line)
            if not line or len(line) > 65_536:
                return False
            words = line.split()
            if words and words[0] == b"end_header":
                return False
            if len(words) >= 2 and words[:2] == [b"element", b"chunk"]:
                return True
            if words and words[0] == b"property" and words[-1].startswith(b"packed_"):
                return True
    return False


def read_runtime(manifest_path=None):
    """Resolve installed runtime executables without PATH lookups or downloads."""
    manifest = Path(manifest_path) if manifest_path else default_manifest_path()
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ConversionError("Format runtime is not ready. Run setup_formats.ps1 first.") from error
    if not isinstance(data, dict) or data.get("version") != PACKAGE_VERSION:
        raise ConversionError(f"Expected format runtime {PACKAGE_VERSION}; run setup_formats.ps1.")
    for field in ("node_exe", "cli_js", "package_root"):
        value = data.get(field)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ConversionError(f"Invalid format runtime {field}.")
    node, cli = Path(data["node_exe"]), Path(data["cli_js"])
    package_root = Path(data["package_root"]).resolve()
    expected_cli = package_root / "node_modules" / "@playcanvas" / "splat-transform" / "bin" / "cli.mjs"
    if cli.resolve() != expected_cli or not node.is_file() or not cli.is_file():
        raise ConversionError("Format runtime files are missing or inconsistent; rerun setup_formats.ps1.")
    try:
        package = json.loads((cli.parent.parent / "package.json").read_text(encoding="utf8"))
        digest = hashlib.sha256((package_root / "package-lock.json").read_bytes()).hexdigest()
    except (OSError, ValueError) as error:
        raise ConversionError("Format runtime package or lockfile cannot be read.") from error
    if package.get("version") != PACKAGE_VERSION or digest != data.get("package_lock_sha256"):
        raise ConversionError("Format runtime version/lockfile mismatch; rerun setup_formats.ps1.")
    return data


def conversion_command(input_path, output_path, manifest_path=None):
    """Return a fixed Node argv converting a supported local file to new PLY.

    The caller owns process lifetime, cancellation, progress and output cleanup.
    ``output_path`` must end in .ply but not .compressed.ply and must not exist.
    """
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    if source.suffix.lower() not in SUPPORTED_SUFFIXES or not source.is_file():
        raise ConversionError("Choose a local .sog, .ksplat, .spz, .ply or .splat file.")
    if target.suffix.lower() != ".ply" or target.name.lower().endswith(".compressed.ply"):
        raise ConversionError("Conversion output must be an ordinary .ply file.")
    if target == source or target.exists():
        raise ConversionError("Conversion output must be a new file; existing files are preserved.")
    if not target.parent.is_dir():
        raise ConversionError("Conversion output directory does not exist.")
    runtime = read_runtime(manifest_path)
    return [runtime["node_exe"], "--max-old-space-size=8192", runtime["cli_js"],
            "--gpu", "cpu", "--no-tty", str(source), str(target)]


def validate_converted(path):
    """Validate all output records through the plugin's strict bounded reader."""
    root = str(PLUGIN_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from argentum_splat import core
    cloud = core.load(path, max_splats=1, min_opacity=0.)
    if cloud.total_count == 0:
        raise ConversionError("The converter produced an empty PLY; no model was imported.")
    return {
        "total_count": cloud.total_count,
        "sh_degree": cloud.metadata["sh_degree"],
        "bounds": cloud.metadata["bounds"],
        "coordinates": "source PLY-equivalent frame; no extra transform",
    }


def convert(input_path, output_path, manifest_path=None):
    """Run synchronously for CLI use; C4D should use conversion_command instead."""
    target = Path(output_path).resolve()
    command = conversion_command(input_path, target, manifest_path)
    # A unique staged PLY prevents partially converted data from appearing final.
    staged = target.with_name(target.stem + ".partial-" + uuid.uuid4().hex + ".ply")
    command[-1] = str(staged)
    try:
        completed = subprocess.run(command, shell=False, check=False,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if completed.returncode:
            raise ConversionError(f"splat-transform failed with exit code {completed.returncode}.")
        summary = validate_converted(staged)
        if target.exists():
            raise ConversionError("Output appeared while converting; the existing file was preserved.")
        staged.rename(target)
        return dict(ok=True, ply_path=str(target), source_path=str(Path(input_path).resolve()),
                    converter_version=PACKAGE_VERSION, **summary)
    finally:
        if staged.exists():
            staged.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--result", help="Optional JSON result path for a parent application.")
    args = parser.parse_args(argv)
    try:
        result = convert(args.input, args.output, args.manifest)
        exit_code = 0
    except Exception as error:
        result = {"ok": False, "error": str(error)}
        exit_code = 1
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.result:
        Path(args.result).write_text(serialized, encoding="utf8")
    print(serialized, flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
