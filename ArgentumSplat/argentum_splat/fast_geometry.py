"""Optional vectorized preparation for validated packed Gaussian PLY records.

prepare_geometry / prepare_colors return None when the optional runtime or
input path is unsupported; callers then use the scalar implementation. Real
validation errors and progress/cancellation exceptions propagate unchanged.
Only complete immutable source buffers enter a weak-owner LRU cache, bounded
to two clouds and 1 GiB total. Large sources stream bounded batches instead.
No Cinema 4D API or native object is used here.
"""
from collections import OrderedDict
from array import array
import math
import struct
import threading
import weakref

from . import core, geometry

BATCH_SIZE = 262144
CACHE_MAX_BYTES = 1024**3
CACHE_MAX_CLOUDS = 2
_CACHE = OrderedDict()
_CACHE_LOCK = threading.RLock()


def get_numpy():
    try:
        from .numeric_runtime import numpy
        return numpy()
    except ImportError:
        # Standalone source tests can use an already installed NumPy. Host
        # deployment provides numeric_runtime and never requires global pip.
        try:
            import numpy
            return numpy
        except ImportError:
            return None


def clear_cache():
    with _CACHE_LOCK:
        _CACHE.clear()


def cache_info():
    with _CACHE_LOCK:
        return {'clouds': len(_CACHE), 'bytes': sum(item['nbytes'] for item in _CACHE.values())}


def _drop(key, reference):
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if item is not None and item['owner'] is reference:
            del _CACHE[key]


def _store(cloud, item):
    key = id(cloud)
    with _CACHE_LOCK:
        _CACHE.pop(key, None)
        if item['nbytes'] > CACHE_MAX_BYTES:
            return
        _CACHE[key] = item
        while (len(_CACHE) > CACHE_MAX_CLOUDS or
               sum(entry['nbytes'] for entry in _CACHE.values()) > CACHE_MAX_BYTES):
            _CACHE.popitem(last=False)


def _layout(cloud, np):
    splats = cloud.splats
    decoder = getattr(splats, '_decode', None)
    descriptor = getattr(decoder, 'numpy_layout', None)
    if not isinstance(splats, core._PackedSplats) or not getattr(decoder, 'validated_records', False):
        return None
    if descriptor is None or len(descriptor) != 7:
        return None
    fmt = descriptor[0]
    if not isinstance(fmt, str) or not fmt or fmt[0] not in '<>!=':
        return None
    types = dict(b='i1', B='u1', h='i2', H='u2', i='i4', I='u4', f='f4', d='f8')
    if any(code not in types for code in fmt[1:]):
        return None
    endian = '>' if fmt[0] in '>!' else '<' if fmt[0] == '<' else '='
    dtype = np.dtype([('f'+str(i), endian+types[code]) for i, code in enumerate(fmt[1:])])
    if dtype.itemsize != struct.calcsize(fmt):
        return None
    return descriptor, dtype


def _report(progress, stage, start, count):
    if progress:
        progress(stage, start, count)


def _source(cloud, layout, np, progress):
    key = id(cloud)
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if (item is not None and item['owner']() is cloud and
                item['source_id'] == id(cloud.splats)):
            _CACHE.move_to_end(key)
            return item
        _CACHE.pop(key, None)
    descriptor, dtype = layout
    count = len(cloud.splats)
    size = count*dtype.itemsize
    reference = weakref.ref(cloud, lambda ref: _drop(key, ref))
    item = dict(owner=reference, source_id=id(cloud.splats), records=None,
                geometry=None, nbytes=0, descriptor=descriptor, dtype=dtype)
    if size > CACHE_MAX_BYTES:
        return item
    records = np.empty(count, dtype=dtype)
    for start in range(0, count, BATCH_SIZE):
        _report(progress, 'Prepare source arrays', start, count)
        stop = min(count, start+BATCH_SIZE)
        records[start:stop] = np.frombuffer(b''.join(cloud.splats._records[start:stop]), dtype=dtype)
    _report(progress, 'Prepare source arrays', count, count)
    records.setflags(write=False)
    item.update(records=records, nbytes=records.nbytes)
    _store(cloud, item)
    return item


def _records(cloud, item, start, stop, np):
    if item['records'] is not None:
        return item['records'][start:stop]
    return np.frombuffer(b''.join(cloud.splats._records[start:stop]), dtype=item['dtype'])


def _fields(records, indices, np):
    return np.column_stack([records['f'+str(index)] for index in indices]).astype(np.float64, copy=False)


def _quaternions(values, np):
    largest = np.max(np.abs(values), axis=1)
    normalized = values/largest[:, None]
    length = np.sqrt(((normalized[:, 0]**2+normalized[:, 1]**2)+
                      normalized[:, 2]**2)+normalized[:, 3]**2)
    return normalized/length[:, None]


def _components(records, descriptor, np):
    position = _fields(records, descriptor[1], np)
    scales = np.exp(_fields(records, descriptor[3], np))
    # The scalar decoder normalizes once, then gaussian_axes normalizes again.
    q = _quaternions(_quaternions(_fields(records, descriptor[4], np), np), np)
    w, x, y, z = (q[:, i] for i in range(4))
    columns = np.empty((len(records), 3, 3), dtype=np.float64)
    columns[:, 0, :] = np.column_stack((1-2*(y*y+z*z), 2*(x*y+w*z), 2*(x*z-w*y)))
    columns[:, 1, :] = np.column_stack((2*(x*y-w*z), 1-2*(x*x+z*z), 2*(y*z+w*x)))
    columns[:, 2, :] = np.column_stack((2*(x*z+w*y), 2*(y*z-w*x), 1-2*(x*x+y*y)))
    return position, scales, columns


def _source_geometry(cloud, item, np, progress):
    if item['geometry'] is not None:
        return item['geometry']
    count = len(cloud.splats)
    # Keep source orientation and scales independent of object/import scale.
    # Larger scans compute these cheap vectorized stages one batch at a time.
    size = count*15*8
    if item['records'] is None or item['nbytes']+size > CACHE_MAX_BYTES:
        return None
    position = np.empty((count, 3), dtype=np.float64)
    scales = np.empty((count, 3), dtype=np.float64)
    columns = np.empty((count, 3, 3), dtype=np.float64)
    for start in range(0, count, BATCH_SIZE):
        _report(progress, 'Prepare source covariance', start, count)
        stop = min(count, start+BATCH_SIZE)
        values = _components(_records(cloud, item, start, stop, np), item['descriptor'], np)
        position[start:stop], scales[start:stop], columns[start:stop] = values
    _report(progress, 'Prepare source covariance', count, count)
    for value in (position, scales, columns):
        value.setflags(write=False)
    item = dict(item, geometry=(position, scales, columns), nbytes=item['nbytes']+size)
    _store(cloud, item)
    return item['geometry']


def _append(buffer, values, np):
    buffer._values.frombytes(np.ascontiguousarray(values, dtype=np.float64).tobytes())


def _dot(values, row):
    return (values[..., 0]*row[0]+values[..., 1]*row[1])+values[..., 2]*row[2]


def _normal(values, np):
    largest = np.max(np.abs(values), axis=1)
    nonzero = largest != 0.
    scaled = values/np.where(nonzero, largest, 1.)[:, None]
    length = np.hypot(np.hypot(scaled[:, 0], scaled[:, 1]), scaled[:, 2])
    result = scaled/np.where(nonzero, length, 1.)[:, None]
    result[~nonzero] = (0., 0., 1.)
    return result


def _projected(axes, centers, camera, projection, np):
    (right, up, inverse, orthographic, scale_x, scale_y, variance,
     width, height, offset_x, offset_y, hidden) = projection
    relative = centers-np.asarray(camera, dtype=np.float64)
    x, y, z = (_dot(relative, row) for row in inverse)
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(z) & (z > 1e-8)
    sigma_limit = min(1024., width, height)/math.sqrt(8.)
    support_limit = 3.*math.sqrt(2.)*sigma_limit
    world_x, world_y = (scale_x, scale_y) if orthographic else (z/scale_x, z/scale_y)
    if not orthographic:
        valid &= ((np.abs(x+offset_x*world_x) <= (width*.5+support_limit)*world_x) &
                  (np.abs(y+offset_y*world_y) <= (height*.5+support_limit)*world_y))
    projected_x, projected_y = _dot(axes, inverse[0]), _dot(axes, inverse[1])
    if orthographic:
        projected_x, projected_y = projected_x/scale_x, projected_y/scale_y
    else:
        projected_z = _dot(axes, inverse[2])
        projected_x = (projected_x-(x/z)[:, None]*projected_z)/world_x[:, None]
        projected_y = (projected_y-(y/z)[:, None]*projected_z)/world_y[:, None]
    valid &= np.all(np.isfinite(projected_x) & np.isfinite(projected_y), axis=1)
    largest = np.maximum(math.sqrt(variance), np.maximum(np.max(np.abs(projected_x), axis=1),
                                                       np.max(np.abs(projected_y), axis=1)))
    valid &= largest > 0.
    divisor = np.where(valid, largest, 1.)
    px, py = projected_x/divisor[:, None], projected_y/divisor[:, None]
    ridge = (math.sqrt(variance)/divisor)**2
    xx = (px[:, 0]**2+px[:, 1]**2)+px[:, 2]**2
    yy = (py[:, 0]**2+py[:, 1]**2)+py[:, 2]**2
    xy = (px[:, 0]*py[:, 0]+px[:, 1]*py[:, 1])+px[:, 2]*py[:, 2]
    determinant = ((px[:, 0]*py[:, 1]-px[:, 1]*py[:, 0])**2+
                   (px[:, 0]*py[:, 2]-px[:, 2]*py[:, 0])**2)+\
                  (px[:, 1]*py[:, 2]-px[:, 2]*py[:, 1])**2
    original_determinant = determinant.copy() if variance > 0. else None
    determinant += ridge*(xx+yy)+ridge*ridge
    major_squared = (xx+yy+2.*ridge+np.hypot(xx-yy, 2.*xy))/2.
    valid &= (major_squared > 0.) & (determinant > 0.)
    major = np.minimum(sigma_limit, largest*np.sqrt(major_squared))
    minor = np.minimum(sigma_limit, largest*np.sqrt(determinant/major_squared))
    angle = .5*np.arctan2(2.*xy, xx-yy)
    cosine, sine = np.cos(angle), np.sin(angle)
    half_x = 3.34*(major*np.abs(cosine)+minor*np.abs(sine))
    half_y = 3.34*(major*np.abs(sine)+minor*np.abs(cosine))
    valid &= ((np.abs(x/world_x+offset_x)-half_x <= width*.5) &
              (np.abs(y/world_y+offset_y)-half_y <= height*.5))
    right, up = np.asarray(right), np.asarray(up)
    u = 3.*major[:, None]*(right*(cosine*world_x)[:, None]+up*(sine*world_y)[:, None])
    v = 3.*minor[:, None]*(right*(-sine*world_x)[:, None]+up*(cosine*world_y)[:, None])
    valid &= np.all(np.isfinite(u) & np.isfinite(v), axis=1)
    # Do not normalize NaNs from deliberately hidden projections.
    u[~valid], v[~valid] = (1., 0., 0.), (0., 1., 0.)
    normal = _normal(np.cross(_normal(u, np), _normal(v, np)), np)
    reverse = np.sum(normal*relative, axis=1) > 0.
    v[reverse] *= -1.
    normal[reverse] *= -1.
    u[~valid], v[~valid], normal[~valid] = hidden
    factors = None
    if variance > 0.:
        ratio = np.divide(original_determinant, determinant, out=np.zeros_like(determinant),
                          where=valid & (determinant > 0.))
        factors = np.clip(np.sqrt(ratio), 0., 1.)
        factors[~valid] = 0.
    return u, v, normal, factors


def prepare_geometry(cloud, settings, camera=(0., 0., -500.), progress=None):
    if not settings.get('compact_buffers') or not settings.get('camera_facing') or not settings.get('projection'):
        return None
    np = get_numpy()
    if np is None:
        return None
    layout = _layout(cloud, np)
    if layout is None:
        return None
    scale, splat_scale = settings.get('scale', 100.), settings.get('splat_scale', 1.)
    core._positive(scale, 'global_scale')
    core._positive(splat_scale, 'splat_scale')
    projection = geometry._compile_projection(settings['projection'], settings.get('pixel_variance', 0.))
    if len(camera) != 3:
        raise ValueError('Camera must contain three coordinates.')
    flip = bool(settings.get('flip_y', False))
    source = _source(cloud, layout, np, progress)
    components = _source_geometry(cloud, source, np, progress)
    buffers = tuple(geometry.Vec3Buffer() for _ in range(4))
    opacity_factors = array('d') if projection[6] > 0. else None
    count = len(cloud.splats)
    with np.errstate(over='ignore', under='ignore', divide='ignore', invalid='ignore'):
        for start in range(0, count, BATCH_SIZE):
            _report(progress, 'Prepare geometry', start, count)
            stop = min(count, start+BATCH_SIZE)
            position, scales, columns = (tuple(value[start:stop] for value in components) if components is not None else
                _components(_records(cloud, source, start, stop, np), source['descriptor'], np))
            centers = position*scale
            axes = columns*((scales*scale)*splat_scale)[:, :, None]
            if flip:
                centers[:, 1] *= -1.
                axes[:, :, 1] *= -1.
                axes[:, 2, :] *= -1.
            if not np.all(np.isfinite(centers)) or not np.all(np.isfinite(axes)):
                raise ValueError('Transformed Gaussian positions or axes must be finite.')
            projected = _projected(axes, centers, camera, projection, np)
            spatial = (centers,)+projected[:3]
            for buffer, value in zip(buffers, spatial):
                _append(buffer, value, np)
            if opacity_factors is not None:
                opacity_factors.frombytes(np.ascontiguousarray(projected[3], dtype=np.float64).tobytes())
    _report(progress, 'Prepare geometry', count, count)
    return geometry.SpatialData(buffers, opacity_factors)


def _hsv(rgb, hue, saturation, np):
    r, g, b = (rgb[:, i] for i in range(3))
    maximum, minimum = np.max(rgb, axis=1), np.min(rgb, axis=1)
    difference = maximum-minimum
    divisor = np.where(difference != 0., difference, 1.)
    rc, gc, bc = (maximum-r)/divisor, (maximum-g)/divisor, (maximum-b)/divisor
    h = np.where(r == maximum, bc-gc, np.where(g == maximum, 2.+rc-bc, 4.+gc-rc))
    h = np.where(difference == 0., 0., (h/6.) % 1.)
    s = np.where(maximum != 0., difference/np.where(maximum != 0., maximum, 1.), 0.)
    h, s = (h+hue/360.) % 1., np.minimum(1., s*saturation)
    scaled = h*6.
    integer = scaled.astype(np.int64)
    fraction = scaled-integer
    p, q, t = maximum*(1.-s), maximum*(1.-s*fraction), maximum*(1.-s*(1.-fraction))
    options = ((maximum, t, p), (q, maximum, p), (p, maximum, t),
               (p, q, maximum), (t, p, maximum), (maximum, p, q))
    result = np.empty_like(rgb)
    for index, values in enumerate(options):
        mask = integer % 6 == index
        for channel in range(3):
            result[mask, channel] = values[channel][mask]
    return result


def _correct(rgb, correction, source_space, np):
    rgb = np.maximum(0., rgb)
    if correction['gamma'] != 1.:
        rgb = rgb**(1./correction['gamma'])
        if not np.all(np.isfinite(rgb)):
            raise ValueError('Gamma correction overflow.')
    if correction['contrast'] != .5:
        rgb = np.maximum(0., (rgb-.5)*(2.*correction['contrast'])+.5)
    if correction['hue'] != 0. or correction['saturation'] != 1.:
        rgb = _hsv(rgb, correction['hue'], correction['saturation'], np)
    rgb = np.minimum(correction['highlight'], np.maximum(0., rgb*correction['level']))
    if correction['color_mode'] == 0 and source_space == 'srgb':
        rgb = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
    if not np.all(np.isfinite(rgb)):
        raise ValueError('Color correction overflow.')
    return rgb


def _sh_basis(direction, degree, np):
    normalized = _normal(direction, np)
    x, y, z = (normalized[:, i] for i in range(3))
    basis = [-0.4886025119029199*y, 0.4886025119029199*z, -0.4886025119029199*x]
    if degree >= 2:
        xx, yy, zz = x*x, y*y, z*z
        basis.extend((1.0925484305920792*x*y, -1.0925484305920792*y*z,
            0.31539156525252005*(2*zz-xx-yy), -1.0925484305920792*x*z,
            0.5462742152960396*(xx-yy)))
    if degree >= 3:
        basis.extend((-0.5900435899266435*y*(3*xx-yy), 2.890611442640554*x*y*z,
            -0.4570457994644658*y*(4*zz-xx-yy), 0.3731763325901154*z*(2*zz-3*xx-3*yy),
            -0.4570457994644658*x*(4*zz-xx-yy), 1.445305721320277*z*(xx-yy),
            -0.5900435899266435*x*(xx-3*yy)))
    return basis


def prepare_colors(cloud, settings, camera=(0., 0., -500.), centers=None, progress=None):
    if not settings.get('compact_buffers'):
        return None
    np = get_numpy()
    if np is None:
        return None
    layout = _layout(cloud, np)
    if layout is None:
        return None
    count = len(cloud.splats)
    if centers is not None and len(centers) != count:
        raise ValueError('Color preparation needs one center per splat.')
    if not count:
        return geometry.Vec3Buffer()
    degree, strength = settings.get('sh_degree', 0), settings.get('sh_strength', 1.)
    core.evaluate_sh(core.Splat((0., 0., 0.), (0., 0., 0.), 1., (1., 1., 1.), (1., 0., 0., 0.)),
                     (0., 0., 1.), degree, strength)
    correction = {key: settings.get(key, value) for key, value in dict(gamma=1., contrast=.5,
        hue=0., saturation=1., level=1., highlight=3., color_mode=0).items()}
    geometry._batch_color_corrector(correction)
    source_space = core._space(cloud.splats._space)
    if source_space == 'auto' and correction['color_mode'] == 0:
        raise ValueError('Color correction needs an explicit source color space.')
    requested_degree = degree
    degree = min(degree, {0: 0, 9: 1, 24: 2, 45: 3}[len(layout[0][5])])
    direction_override = settings.get('sh_direction')
    projection = settings.get('projection')
    if direction_override is None and projection and projection.get('orthographic'):
        direction_override = projection['forward']
    flip, scale = bool(settings.get('flip_y', False)), settings.get('scale', 100.)
    if requested_degree and strength and direction_override is not None:
        direction_override = tuple(float(v) for v in direction_override)
        if (len(direction_override) != 3 or not all(math.isfinite(v) for v in direction_override)
                or not any(direction_override)):
            raise ValueError('Orthographic SH direction must be a finite nonzero three-component vector.')
        direction_override = np.asarray(direction_override).copy()
        if flip:
            direction_override[1] *= -1.
    source = _source(cloud, layout, np, progress)
    result = geometry.Vec3Buffer()
    with np.errstate(over='ignore', under='ignore', divide='ignore', invalid='ignore'):
        for start in range(0, count, BATCH_SIZE):
            _report(progress, 'Prepare colour', start, count)
            stop = min(count, start+BATCH_SIZE)
            records = _records(cloud, source, start, stop, np)
            rgb = .5+core.SH_C0*_fields(records, source['descriptor'][2], np)
            if degree and strength:
                if direction_override is not None:
                    direction = np.broadcast_to(direction_override, (stop-start, 3))
                else:
                    if centers is not None:
                        position = (np.frombuffer(centers._values, dtype=np.float64).reshape(-1, 3)[start:stop]
                                    if isinstance(centers, geometry.Vec3Buffer) else np.asarray(centers[start:stop]))
                    else:
                        core._positive(scale, 'global_scale')
                        position = _fields(records, source['descriptor'][1], np)*scale
                        if flip:
                            position[:, 1] *= -1.
                    direction = position-np.asarray(camera, dtype=np.float64)
                    if flip:
                        direction[:, 1] *= -1.
                if not np.all(np.isfinite(direction)):
                    raise ValueError('SH direction must be finite.')
                basis = _sh_basis(direction, degree, np)
                indices = source['descriptor'][5]
                channel_size = len(indices)//3
                for channel in range(3):
                    contribution = np.zeros(stop-start, dtype=np.float64)
                    for index, value in enumerate(basis):
                        contribution += value*records['f'+str(indices[channel*channel_size+index])]
                    rgb[:, channel] += strength*contribution
            if not np.all(np.isfinite(rgb)):
                raise ValueError('Evaluated SH color must be finite.')
            _append(result, _correct(rgb, correction, source_space, np), np)
    _report(progress, 'Prepare colour', count, count)
    return result


def cached_opacity(cloud):
    """Return completed cached alpha without decoding records or growing cache.

    Native mesh assembly calls this on the main thread. A cache miss must use
    its selected batch rather than start a full-source opacity calculation.
    """
    key=id(cloud)
    with _CACHE_LOCK:
        item=_CACHE.get(key)
        if (item is not None and item['owner']() is cloud and
                item['source_id'] == id(cloud.splats)):
            return item.get('opacity')
    return None


def opacity_array(cloud, progress=None):
    """Readonly float64 alpha for native bulk mesh writes, or None to fall back."""
    np = get_numpy()
    if np is None:
        return None
    layout = _layout(cloud, np)
    if layout is None:
        return None
    source = _source(cloud, layout, np, progress)
    if source.get('opacity') is not None:
        return source['opacity']
    count = len(cloud.splats)
    result = np.empty(count, dtype=np.float64)
    field = 'f'+str(source['descriptor'][6])
    for start in range(0, count, BATCH_SIZE):
        _report(progress, 'Prepare opacity', start, count)
        stop = min(count, start+BATCH_SIZE)
        values = _records(cloud, source, start, stop, np)[field].astype(np.float64, copy=False)
        positive = values >= 0.
        target = result[start:stop]
        target[positive] = 1./(1.+np.exp(-values[positive]))
        exponent = np.exp(values[~positive])
        target[~positive] = exponent/(1.+exponent)
    _report(progress, 'Prepare opacity', count, count)
    result.setflags(write=False)
    if source['nbytes']+result.nbytes <= CACHE_MAX_BYTES:
        _store(cloud, dict(source, opacity=result, nbytes=source['nbytes']+result.nbytes))
    return result


def spatial_bounds(spatial, progress=None):
    """Exact min/max bounds for contiguous spatial vectors, or None to fall back."""
    if not all(isinstance(value, geometry.Vec3Buffer) for value in spatial[:3]):
        return None
    np = get_numpy()
    if np is None or not len(spatial[0]):
        return None
    positions, us, vs = (np.frombuffer(value._values, dtype=np.float64).reshape(-1, 3)
                         for value in spatial[:3])
    if len(positions) != len(us) or len(positions) != len(vs):
        return None
    low, high = np.full(3, np.inf), np.full(3, -np.inf)
    count = len(positions)
    for start in range(0, count, BATCH_SIZE):
        _report(progress, 'Prepare bounds', start, count)
        stop = min(count, start+BATCH_SIZE)
        extent = np.abs(us[start:stop])+np.abs(vs[start:stop])
        low = np.minimum(low, np.min(positions[start:stop]-extent, axis=0))
        high = np.maximum(high, np.max(positions[start:stop]+extent, axis=0))
    _report(progress, 'Prepare bounds', count, count)
    return [((float(lo)+float(hi))*.5, max(.01, (float(hi)-float(lo))*.5)) for lo, hi in zip(low, high)]


def card_indices(spatial, progress=None):
    """Cancellable compact visibility indices for Vec3Buffer, or None."""
    if not isinstance(spatial[1], geometry.Vec3Buffer):
        return None
    np = get_numpy()
    if np is None:
        return None
    values = np.frombuffer(spatial[1]._values, dtype=np.float64).reshape(-1, 3)
    result = array('I')
    count = len(values)
    for start in range(0, count, BATCH_SIZE):
        _report(progress, 'Select visible cards', start, count)
        stop = min(count, start+BATCH_SIZE)
        selected = np.flatnonzero(np.any(values[start:stop] != 0., axis=1))+start
        result.frombytes(selected.astype('u'+str(result.itemsize)).tobytes())
    _report(progress, 'Select visible cards', count, count)
    return result
