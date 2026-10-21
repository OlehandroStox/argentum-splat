"""Bounded incremental JSON-line parsing without losing partial writes."""
import json
import math


def read_updates(path, offset=0, pending=b''):
    with open(path, 'rb') as handle:
        handle.seek(offset)
        chunk = handle.read(262144)
        offset = handle.tell()
    parts = (pending + chunk).split(b'\n')
    pending = parts.pop()
    if len(pending) > 262144:
        pending = b''
    updates = []
    for line in parts:
        try:
            item = json.loads(line.decode('utf8', errors='replace'))
            if isinstance(item, dict) and isinstance(item.get('message'), str):
                amount = item.get('progress')
                if isinstance(amount, (float, int)) and math.isfinite(amount):
                    item['progress'] = min(1., max(0., float(amount)))
                else:
                    item['progress'] = None
                updates.append(item)
        except (ValueError, TypeError):
            pass
    return updates, offset, pending
