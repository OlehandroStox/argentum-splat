"""Return to a photographed view without inventing unobserved geometry."""
import json
from pathlib import Path
from . import assets, ids as I, quality


def activate(op):
    first = quality.source_camera_data(op, require_match=True)
    source = Path(assets.resolve_path(op, op[I.FILE]))
    path = source.parent/'capture-cameras.json'
    cameras = [first]
    if first.get('origin') == 'photos_colmap' and path.is_file():
        if path.stat().st_size > 2*1024*1024:
            raise ValueError('Capture camera metadata is too large.')
        cameras = json.loads(path.read_text(encoding='utf8')).get('cameras', [])
    if not isinstance(cameras, list) or not 1 <= len(cameras) <= 500:
        raise ValueError('No valid captured cameras are available.')
    index = int(op[I.CAPTURE_INDEX] or 0)
    if not 0 <= index < len(cameras):
        raise ValueError('This scan has %d saved views. Choose 0–%d.' % (len(cameras), len(cameras)-1))
    camera = quality.create_source_camera(op, cameras[index], activate=True)
    camera.SetName('Splat Captured View %03d - %s' % (index, cameras[index].get('image_name', 'Source')))
    return camera
