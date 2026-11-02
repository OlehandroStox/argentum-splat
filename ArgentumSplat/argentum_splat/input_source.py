"""Input routing shared by Cinema 4D and its isolated media worker."""
from pathlib import Path

IMAGE_EXTENSIONS = frozenset('.png .jpg .jpeg .webp .tif .tiff .bmp .tga .gif'.split())
SPLAT_EXTENSIONS = frozenset('.ply .splat .spz .sog .ksplat'.split())


def coordinate_flip(path, flip_y=False, raw_spz=False, auto_sog=False):
    """Map SOG's conventional Y-down frame to C4D's Y-up, left-handed frame.

    The manual flip remains an additional override. Missing auto_sog on saved
    pre-0.7.2 objects means False, retaining their existing geometry/cameras.
    PLY and generated image assets keep their explicit orientation workflow.
    """
    suffix = Path(path).suffix.lower()
    normalise = (suffix == '.spz' and not raw_spz) or (suffix == '.sog' and auto_sog)
    return bool(flip_y) ^ bool(normalise)


def classify(path, mode=0):
    if mode != 0:
        raise ValueError('Image accepts one still picture. Choose Photos for multiple views.')
    suffix = Path(path).suffix.lower()
    if suffix in SPLAT_EXTENSIONS:
        return 'splat'
    if suffix in IMAGE_EXTENSIONS:
        return 'image'
    raise ValueError('Unsupported input. Choose a still PNG/JPG/WebP/TIFF/BMP/TGA/GIF image.')


def classify_media(path, mode=0):
    if Path(path).suffix.lower() in SPLAT_EXTENSIONS:
        raise ValueError('This is a 3D scan. Select it in SCAN > Splat File, then use Initialise / Reload.')
    return classify(path, mode)


def validate_frame(index):
    # Reject obsolete requests; no frame/sequence decoding remains.
    if isinstance(index, bool) or not isinstance(index, int) or index != 0:
        raise ValueError('Image accepts one still picture; frame selection is no longer supported.')
    return 0
