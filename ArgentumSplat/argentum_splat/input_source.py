"""Input routing shared by Cinema 4D and its isolated media worker."""
from pathlib import Path
import re

IMAGE_EXTENSIONS = frozenset('.png .jpg .jpeg .webp .tif .tiff .bmp .tga .gif'.split())
VIDEO_EXTENSIONS = frozenset('.mp4 .mov .m4v .mkv .avi .webm .mpg .mpeg .mts .m2ts'.split())
SPLAT_EXTENSIONS = frozenset('.ply .splat .spz .sog .ksplat'.split())
MAX_FRAME = 99999


def classify(path, mode=0):
    suffix = Path(path).suffix.lower()
    if mode not in (0, 1):
        raise ValueError('Unknown Input Mode.')
    if mode == 1:
        if suffix not in IMAGE_EXTENSIONS:
            raise ValueError('Numbered Sequence requires an image file such as name_0001.png.')
        return 'sequence'
    if suffix in SPLAT_EXTENSIONS:
        return 'splat'
    if suffix in VIDEO_EXTENSIONS:
        return 'video'
    if suffix in IMAGE_EXTENSIONS:
        return 'image'
    raise ValueError('Unsupported input. Use PNG/JPG/WebP/TIFF/BMP/TGA/GIF, a video, or PLY/SPLAT/SPZ/SOG/KSPLAT.')


def validate_frame(index):
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= MAX_FRAME:
        raise ValueError('Source Frame must be an integer from 0 to 99,999.')
    return index


def sequence_frame(path, offset):
    """Offset from the selected file's final numeric suffix; never skip holes."""
    validate_frame(offset)
    path = Path(path)
    match = re.fullmatch(r'(.*?)(\d+)', path.stem)
    if not match:
        raise ValueError('Select a numbered image, for example shot_0001.png.')
    prefix, digits = match.groups()
    number = int(digits) + offset
    target = path.with_name(prefix + str(number).zfill(len(digits)) + path.suffix)
    if not target.is_file():
        raise ValueError('Sequence frame is missing: ' + target.name)
    return target
