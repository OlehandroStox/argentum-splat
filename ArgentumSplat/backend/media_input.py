"""Local frame extraction. No inference, subprocesses, URLs or uploads."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from argentum_splat.input_source import classify, sequence_frame, validate_frame


def load_source(path, mode=0, frame_index=0, progress=None):
    from PIL import Image, ImageOps
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Input file does not exist.')
    validate_frame(frame_index)
    kind = classify(path, mode)
    if kind == 'splat':
        raise ValueError('Splat files must be loaded directly, not sent to image generation.')
    metadata = {'path': str(path), 'kind': kind, 'frame_index': frame_index,
                'mode': mode, 'reconstruction': 'single_selected_frame'}
    if kind in ('image', 'sequence'):
        selected = sequence_frame(path, frame_index) if kind == 'sequence' else path
        with Image.open(selected) as raw:
            index = 0 if kind == 'sequence' else frame_index
            try:
                raw.seek(index)
            except EOFError:
                raise ValueError('Source Frame is outside this image. Use 0 for a still image.') from None
            raw.load()
            result = ImageOps.exif_transpose(raw).convert('RGBA')
        metadata['selected_path'] = str(selected)
    else:
        try:
            import av
        except ImportError:
            raise RuntimeError('Video decoder is missing. Run Set Up AI / Extra Formats once to install PyAV.') from None
        # Decode in presentation order: exact frame selection also for VFR and
        # B-frame video. Timestamp seeking cannot promise an exact frame index.
        with av.open(str(path), mode='r') as container:
            if not container.streams.video:
                raise ValueError('This file contains no video stream.')
            stream = container.streams.video[0]
            if stream.width * stream.height > 80_000_000:
                raise ValueError('Video frames exceed the supported 80 megapixel limit.')
            if stream.frames and frame_index >= stream.frames:
                raise ValueError('Source Frame is outside the video (%d frames).' % stream.frames)
            selected = None
            for index, frame in enumerate(container.decode(video=0)):
                if progress and index % 48 == 0:
                    progress(index, frame_index)
                if index == frame_index:
                    selected = frame
                    break
            if selected is None:
                raise ValueError('Source Frame is outside the decoded video.')
            result = selected.to_image().convert('RGBA')
            rotation = float(getattr(selected, 'rotation', 0) or 0)
            if rotation:
                result = result.rotate(rotation, expand=True)
            metadata.update(timestamp_seconds=float(selected.time) if selected.time is not None else None,
                            rotation_degrees=rotation,
                            fps=float(stream.average_rate) if stream.average_rate else None)
    metadata['resolution'] = {'width': result.width, 'height': result.height}
    return result, metadata
