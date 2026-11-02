"""Bounded bulk writes into owned Cinema 4D 2027 mesh buffers.

Only detached new meshes/clones may be passed here. Memoryviews are acquired
and released inside each write; no native buffer survives a generator yield.
Every tag's layout is checked before writing. Unsupported hosts use the scalar
implementation. Source arrays are never modified.
"""
try:
    import c4d
except ImportError:
    c4d = None
from . import geometry, numeric_runtime
if c4d is not None:
    from . import materials
else:
    materials = None

BATCH = 2048


def available(prepared):
    return (c4d is not None and getattr(c4d, 'GetC4DVersion', lambda: 0)() >= 2027000 and
            all(isinstance(value, geometry.Vec3Buffer) for value in prepared) and
            numeric_runtime.numpy() is not None)


def vectors(values, np):
    return np.frombuffer(values._values, dtype=np.float64).reshape(-1, 3)


def write(tag, start, values, item_size):
    if tag.GetDataSize() != item_size:
        raise RuntimeError('Unsupported native Gaussian tag layout.')
    data = memoryview(values).cast('B')
    buffer = tag.GetLowlevelDataAddressW()
    try:
        offset = start * item_size
        if offset < 0 or offset + data.nbytes > buffer.nbytes:
            raise ValueError('Gaussian buffer write exceeds the owned tag.')
        buffer.cast('B')[offset:offset+data.nbytes] = data
    finally:
        buffer.release()
        data.release()


def alpha_values(cloud, np):
    """Reuse completed packed alpha; never calculate a full source here."""
    from .fast_geometry import cached_opacity
    return cached_opacity(cloud)


def selection(indices, count, np):
    if isinstance(indices, range) and indices == range(count):
        return None
    return np.asarray(indices, dtype=np.int64)


def build_steps(cloud, prepared, material, opacity, weights, indices):
    from . import import_budget
    count = len(indices)
    yield 'Allocate Gaussian cards', 0, count
    import_budget.check_card_memory(count)
    mesh = c4d.PolygonObject(count*4, count)
    mesh.SetName('Gaussian Cards')
    for tag in (c4d.UVWTag(count), c4d.NormalTag(count)):
        mesh.InsertTag(tag)
    color = c4d.VertexColorTag(count*4)
    color.SetName('SplatColor')
    color.SetPerPointMode(True)
    mesh.InsertTag(color)
    for name in ('SplatOpacity', 'SplatEmission', 'SplatDiffuse', 'SplatSubsurface', 'SplatProfile'):
        tag = c4d.VariableTag(c4d.Tvertexmap, count*4)
        tag.SetName(name)
        mesh.InsertTag(tag)
    mesh.MakeTag(c4d.Tphong)
    steps = update_steps(mesh, cloud, prepared, opacity, weights, indices,
        update_geometry=True, update_colors=True, update_opacity=True,
        update_weights=True, material=material, update_material=True, topology=True)
    return (yield from steps)


def update_steps(mesh, cloud, prepared, opacity, weights, indices,
                 update_geometry=False, update_colors=False, update_opacity=False,
                 update_weights=False, material=None, update_material=False, topology=False):
    count = len(indices)
    if mesh.GetPointCount() != count*4 or mesh.GetPolygonCount() != count:
        raise ValueError('Cached Gaussian mesh does not match its source mapping.')
    update_points = update_geometry or update_opacity
    update_rgba = update_colors or update_points
    weight_tags = tuple((name, setting) for name, setting in (
        ('SplatEmission', 'emission_weight'), ('SplatDiffuse', 'diffuse_weight'),
        ('SplatSubsurface', 'subsurface_weight'))
        if update_weights is True or (update_weights and setting in update_weights))
    update_cards = update_rgba or topology or bool(weight_tags)
    # Material links and constant surface weights do not consume source data.
    # In particular, avoid decoding millions of alpha values or copying a
    # compact visibility mapping merely to update one of those properties.
    if update_cards:
        np = numeric_runtime.numpy()
        by_name = {tag.GetName(): tag for tag in mesh.GetTags()}
    if update_rgba:
        colors = vectors(prepared[4], np)
        source_alpha = alpha_values(cloud, np)
        source_count = len(source_alpha) if source_alpha is not None else len(cloud.splats)
        if source_alpha is None:
            from . import core
        factors = getattr(prepared, 'opacity_factors', None)
        if factors is not None:
            factors = np.asarray(factors)
            if factors.shape != (source_count,):
                raise ValueError('Gaussian filter compensation has the wrong length.')
        chosen = selection(indices, source_count, np)
    if update_points:
        centers, us, vs, normals = [vectors(value, np) for value in prepared[:4]]
        point_tag = mesh.GetTag(c4d.Tpoint)
        normal_tag, uv_tag = mesh.GetTag(c4d.Tnormal), mesh.GetTag(c4d.Tuvw)
        uv_cache = {}
        if 'SplatProfile' not in by_name:
            tag = c4d.VariableTag(c4d.Tvertexmap, count*4);tag.SetName('SplatProfile');mesh.InsertTag(tag)
            by_name['SplatProfile'] = tag
    if topology:
        poly_tag = mesh.GetTag(c4d.Tpolygon)
    stage = ('Build Gaussian cards' if topology else
             'Update Gaussian view' if update_points else
             'Update Gaussian colours' if update_rgba else 'Update surface weights')
    for start in range(0, count if update_cards else 0, BATCH):
        stop = min(count, start+BATCH)
        yield stage, start, count
        if update_rgba:
            ix = slice(start, stop) if chosen is None else chosen[start:stop]
            if source_alpha is None:
                # A missing packed-PLY alpha cache must not trigger a full
                # source pass on the main thread. Generic formats can also
                # decode a complete Splat per lookup. Read only this batch's
                # selected records, after yielding to the host.
                batch_indices = range(start, stop) if chosen is None else ix
                alpha = np.fromiter(core.iter_attributes(cloud, 'opacity', batch_indices),
                                    dtype=np.float64, count=stop-start)
            else:
                alpha = source_alpha[ix]
            alpha = np.clip(alpha * opacity, 0., 1.)
            if factors is not None:
                alpha = alpha * factors[ix]
        if update_points:
            classic = bool(weights.get("gaussian_profile", 0))
            floor = 0. if classic else np.exp(-4.)
            safe = np.maximum(alpha, 1./255.)
            support = np.minimum(2. if classic else 1., np.sqrt(np.maximum(0., -np.log(
                floor+(1.-floor)/(255.*safe))/4.5)) + 1e-6)
            support[alpha <= 1./255.] = 0.
            u, v = us[ix]*support[:,None], vs[ix]*support[:,None]
            center = centers[ix]
            points = np.stack((center-u-v, center+u-v, center+u+v, center-u+v), axis=1)
            write(point_tag, start*4, points, 24)
            # In Cinema 4D 2027 the UVW low-level buffer is not authoritative:
            # a raw write can read back correctly while GetSlow/rendering sees
            # unrelated UVs. Use the public UV setter for each bounded batch.
            for index, radius in enumerate(support.tolist(), start):
                corners = uv_cache.get(radius)
                if corners is None:
                    low, high = .5*(1.-radius), .5*(1.+radius)
                    corners = dict(a=c4d.Vector(low,low,0), b=c4d.Vector(high,low,0),
                                   c=c4d.Vector(high,high,0), d=c4d.Vector(low,high,0))
                    if len(uv_cache) >= 512:
                        uv_cache.clear()
                    uv_cache[radius] = corners
                uv_tag.SetSlow(index, **corners)
            normal = np.clip(normals[ix], -1., 1.)
            packed = np.repeat((normal*32000.).astype(np.int16)[:,None,:], 4, axis=1)
            write(normal_tag, start, packed, 24)
        if topology:
            polygons = np.arange(start*4, stop*4, dtype=np.int32).reshape(-1,4)
            write(poly_tag, start, polygons, 16)
        if update_rgba:
            rgba = np.column_stack((colors[ix], alpha)).astype(np.float32)
            write(by_name['SplatColor'], start*4, np.repeat(rgba,4,axis=0), 16)
        if update_points:
            write(by_name['SplatProfile'], start*4, np.full((stop-start)*4,weights.get('gaussian_profile',0),dtype=np.float32),4)
            write(by_name['SplatOpacity'], start*4, np.repeat(alpha.astype(np.float32),4), 4)
        for name, setting in weight_tags:
            value = weights.get(setting, materials.DEFAULTS[setting])
            write(by_name[name], start*4, np.full((stop-start)*4,value,dtype=np.float32),4)
    if update_material:
        yield 'Update material', 0, 1
        texture = mesh.GetTag(c4d.Ttexture)
        if material is None:
            if texture is not None: texture.Remove()
        else:
            if texture is None:
                texture = c4d.TextureTag()
                mesh.InsertTag(texture)
            texture[c4d.TEXTURETAG_MATERIAL] = material
            texture[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
    for tag in mesh.GetTags():
        tag.SetDirty(c4d.DIRTYFLAGS_DATA)
    mesh.SetDirty(c4d.DIRTYFLAGS_DATA)
    mesh.Message(c4d.MSG_UPDATE)
    return mesh
