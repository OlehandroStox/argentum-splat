"""Bounded metadata detection; unknown scans retain the existing viewer profile."""
import json
from pathlib import Path
_CACHE = {}


def profile(filename):
    path = Path(filename)
    if path.suffix.lower() != '.ply' or not path.is_file():
        return 0
    sidecar = path.parent/'generation.json'
    def stamp(p):
        try:
            s=p.stat(); return (s.st_mtime_ns,s.st_size)
        except OSError: return None
    key=(str(path.resolve()),stamp(path),stamp(sidecar))
    if key in _CACHE: return _CACHE[key]
    result=0
    try:
        with path.open('rb') as f:
            header=f.read(65536).split(b'end_header',1)[0]
        if b'comment argentum_profile brush_classic_v1' in header:
            result=1
        elif sidecar.is_file() and sidecar.stat().st_size < 1024*1024:
            m=json.loads(sidecar.read_text(encoding='utf8'))
            result=int(isinstance(m, dict) and m.get('kind')=='photos' and m.get('brush_version')=='0.3.0' and
                       Path(str(m.get('ply_path',''))).name==path.name)
    except (OSError,ValueError,TypeError): pass
    if len(_CACHE)>64: _CACHE.clear()
    _CACHE[key]=result
    return result
