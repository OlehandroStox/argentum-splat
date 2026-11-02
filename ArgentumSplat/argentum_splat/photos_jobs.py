"""Cinema adapter for the isolated Photos worker."""
import json
from pathlib import Path
import subprocess
import time
import uuid
from . import ids as I, photos


def start(owner):
    from . import plugin
    plugin.require_idle()
    if not str(owner.op[I.PHOTOS_FOLDER] or '').strip():
        raise ValueError('Choose a Photos Folder first.')
    folder = Path(plugin.document_path(owner.op, owner.op[I.PHOTOS_FOLDER]))
    signature = photos.signature(folder)
    runtime = plugin.RUNTIME.parent/'photos-runtime'
    marker = runtime/'photos-runtime.json'
    if not marker.is_file():
        raise RuntimeError('Photos is not installed. Click Set Up Photos in the Photos tab.')
    config = json.loads(marker.read_text(encoding='utf8'))
    python = Path(config['python_exe'])
    if not python.is_file() or not Path(config['brush_exe']).is_file():
        raise RuntimeError('Photos runtime is incomplete. Run Set Up Photos again.')
    base = Path(plugin.document_path(owner.op, owner.op[I.PHOTOS_OUTPUT]) or plugin.RUNTIME.parent/'reconstructed')
    jobdir = base/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    values = photos.settings(dict(steps=int(owner.op[I.PHOTOS_STEPS]),
        max_splats=int(owner.op[I.PHOTOS_MAX_SPLATS]), resolution=int(owner.op[I.PHOTOS_RESOLUTION]),
        seed=1,training_color='srgb' if owner.op[I.PHOTOS_COLOR]==1 else 'linear'))
    jobdir.mkdir(parents=True, exist_ok=False)
    request = dict(photos_folder=str(folder.resolve()), output_dir=str(jobdir), runtime_dir=str(runtime), **values)
    request_path, result_path = jobdir/'request.json', jobdir/'result.json'
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf8')
    log = (jobdir/'generation.log').open('wb')
    try:
        process = subprocess.Popen([str(python), str(plugin.ROOT/'backend/photos_worker.py'),
            '--request', str(request_path), '--result', str(result_path)], stdout=log,
            stderr=subprocess.STDOUT, cwd=str(plugin.ROOT), shell=False,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except Exception:
        log.close()
        raise
    owner.job = dict(process=process, log=log, dir=jobdir, result=result_path,
                     kind='photos', input_signature=signature)
    plugin.JOBS.add(owner)
    owner.log_offset, owner.log_pending = 0, b''
    owner.set_progress('Preparing %d photos for reconstruction' % len(signature), 0.)
    owner.show_progress()


def current_signature(owner):
    from . import plugin
    try:
        return photos.signature(plugin.document_path(owner.op, owner.op[I.PHOTOS_FOLDER]))
    except (ValueError, OSError):
        return None
