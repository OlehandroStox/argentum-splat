"""Read one still picture locally. No sequence or moving-image decoding."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from argentum_splat.input_source import classify_media, validate_frame


def load_source(path, mode=0, frame_index=0, progress=None):
    from PIL import Image, ImageOps
    path = Path(path).resolve()
    classify_media(path, mode)
    validate_frame(frame_index)
    if not path.is_file():
        raise ValueError('Input image does not exist.')
    with Image.open(path) as raw:
        if getattr(raw, 'n_frames', 1) != 1:
            raise ValueError('Choose a single still image, not an animated or multipage file.')
        if raw.width * raw.height > 80_000_000:
            raise ValueError('Input image exceeds the supported 80 megapixel limit.')
        raw.load()
        result = ImageOps.exif_transpose(raw).convert('RGBA')
    return result, dict(path=str(path), selected_path=str(path), kind='image',
                        reconstruction='single_image', resolution=dict(width=result.width,height=result.height))
