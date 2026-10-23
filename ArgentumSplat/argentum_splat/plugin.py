"""Cinema 4D integration. Heavy AI work runs in an isolated subprocess."""
import json
import math
import os
from pathlib import Path
import subprocess
import time
import uuid
import weakref
from dataclasses import replace
import c4d
from . import core, geometry, materials, assets, input_source, job_progress, loading, ids as I
from .scene_jobs import InteractiveScan

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get("LOCALAPPDATA", str(ROOT))) / "ArgentumSplat" / "runtime"
INSTANCES = weakref.WeakSet()
JOBS = set()  # Strong ownership until every subprocess has exited.
PENDING = []
RESOURCE = None
REGISTERED = False
CLOUD_CACHE = {}
CONVERTER = None


def is_open_document(document):
    current = c4d.documents.GetFirstDocument()
    while current:
        if current == document:
            return True
        current = current.GetNext()
    return False


def shutdown():
    for instance in list(JOBS):
        try:
            instance.cancel(notify=False)
        except Exception as error:
            print("Argentum Splat shutdown:",error)
    for instance in list(INSTANCES):
        from .progress_ui import close
        close(instance)


def require_idle():
    if any(instance.job for instance in JOBS):
        raise RuntimeError("Another Argentum job is running. Finish or cancel it first.")


def settings(op):
    flip = input_source.coordinate_flip(str(op[I.FILE] or ""), op[I.FLIP_Y],
                                       op[I.SPZ_RAW], op[I.AUTO_SOG_ORIENTATION])
    values = {
        "scale": float(op[I.SCALE]), "splat_scale": float(op[I.SPLAT_SCALE]),
        "flip_y": flip, "camera_facing": bool(op[I.CAMERA_FACING]),
        "smoothing": int(op[I.SMOOTHING]), "sh_degree": int(op[I.SH_DEGREE]),
        "sh_strength": float(op[I.SH_STRENGTH]), "gamma": float(op[I.GAMMA]),
        "contrast": float(op[I.CONTRAST]), "hue": float(op[I.HUE]),
        "saturation": float(op[I.SATURATION]), "level": float(op[I.LEVEL]),
        "highlight": float(op[I.HIGHLIGHT]), "color_mode": int(op[I.COLOR_MODE]),
        "emission_weight": float(op[I.EMISSION]),
        "diffuse_weight": float(op[I.DIFFUSE]), "subsurface_weight": float(op[I.SUBSURFACE]),
        "pixel_variance": float(op[I.PIXEL_VARIANCE] or 0.),
        "compact_buffers": True,
        "compact_cards": op.GetUp() is None,
    }
    if values['camera_facing']:
        values['projection'] = screen_projection(op)
    return values


def vector_tuple(v):
    return (v.x, v.y, v.z)


def color_configuration_key(doc):
    """Only input-to-render settings; display/view transforms stay with C4D."""
    if doc is None:
        return (None,)
    mode = int(doc[c4d.DOCUMENT_COLOR_MANAGEMENT])
    if mode != c4d.DOCUMENT_COLOR_MANAGEMENT_OCIO:
        return (mode,)
    return (
        mode, str(doc[c4d.DOCUMENT_OCIO_CONFIG]),
        int(doc[c4d.DOCUMENT_OCIO_PRESET]),
        int(doc[c4d.DOCUMENT_OCIO_RENDER_COLORSPACE]),
        str(doc[c4d.DOCUMENT_OCIO_RENDER_COLORSPACE_NAME]),
        os.environ.get("OCIO", ""),
    )


def working_colors(doc, colors):
    """Convert corrected linear Rec.709 RGB into the document working gamut."""
    if (doc is None or
            doc[c4d.DOCUMENT_COLOR_MANAGEMENT] != c4d.DOCUMENT_COLOR_MANAGEMENT_OCIO):
        return colors
    if not colors:
        return colors
    color_converter = doc.GetColorConverter()
    if not color_converter.IsOcioConverter():
        raise RuntimeError("Cinema 4D could not initialize the document OCIO converter.")
    working = geometry.Vec3Buffer() if isinstance(colors, geometry.Vec3Buffer) else []
    for start in range(0, len(colors), 4096):
        result = color_converter.TransformColors(
            [c4d.Vector(*rgb) for rgb in colors[start:start+4096]],
            c4d.COLORSPACETRANSFORMATION_OCIO_LINEAR_TO_RENDERING,
        )
        working.extend(vector_tuple(rgb) for rgb in result)
    return working


def source_signature(path):
    path = Path(path).resolve()
    stat = path.stat()
    return json.dumps([str(path),stat.st_mtime_ns,stat.st_size])


def document_path(op, value):
    """Resolve project-relative paths consistently for loading and jobs."""
    return assets.resolve_path(op,value)


def converter():
    global CONVERTER
    if CONVERTER is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_argentum_format_converter", ROOT/"backend"/"convert_splat.py")
        CONVERTER = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(CONVERTER)
    return CONVERTER


def convert_spz_cloud_frame(cloud):
    """Bring a converted SPZ4 PLY from native RUB into the native parser's RDF."""
    from .spz import _RUB_RDF_SH_SIGNS
    transformed = []
    for splat in cloud.splats:
        x,y,z = splat.position
        w,qx,qy,qz = splat.rotation
        dimension = len(splat.sh)//3
        sh = tuple(value*_RUB_RDF_SH_SIGNS[index % dimension]
                   for index,value in enumerate(splat.sh)) if dimension else ()
        transformed.append(replace(splat,position=(x,-y,-z),rotation=(w,qx,-qy,-qz),sh=sh))
    return core.SplatCloud(transformed,cloud.total_count,dict(cloud.metadata,coordinates="RDF"))


def projection_camera(op):
    doc = op.GetDocument()
    cam = op[I.CAMERA]
    if cam is None and doc:
        bd = doc.GetRenderBaseDraw()
        if bd:
            cam = bd.GetSceneCamera(doc) or bd.GetEditorCamera()
    position = cam.GetMg().off if cam else c4d.Vector(0, 0, -500)
    return vector_tuple(~op.GetMg() * position)


def screen_projection(op):
    """Camera axes retain inverse object scale so projection supports affine objects."""
    doc = op.GetDocument()
    if doc is None:
        return None
    bd = doc.GetRenderBaseDraw()
    cam = op[I.CAMERA] or (bd.GetSceneCamera(doc) or bd.GetEditorCamera() if bd else None)
    if cam is None or cam[c4d.CAMERA_PROJECTION] != c4d.Pperspective:
        # Other C4D projections keep the existing covariance-card path.
        return None
    rd = doc.GetActiveRenderData()
    width, height = max(1., float(rd[c4d.RDATA_XRES])), max(1., float(rd[c4d.RDATA_YRES]))
    focal = width / (2. * math.tan(float(cam[c4d.CAMERAOBJECT_FOV]) * .5))
    inv, mg = ~op.GetMg(), cam.GetMg()
    return dict(right=vector_tuple(inv.MulV(mg.v1)), up=vector_tuple(inv.MulV(mg.v2)),
                forward=vector_tuple(inv.MulV(mg.v3)), focal_x=focal,
                focal_y=focal * float(rd[c4d.RDATA_PIXELASPECT] or 1.), width=width, height=height)


def complete_steps(steps):
    while True:
        try:
            next(steps)
        except StopIteration as finished:
            return finished.value


def build_mesh(cloud, prepared, material, opacity=1., weights=None):
    return complete_steps(build_mesh_steps(cloud, prepared, material, opacity, weights))


def build_mesh_steps(cloud, prepared, material, opacity=1., weights=None):
    indices = geometry.card_indices(prepared, (weights or {}).get('compact_cards', False))
    count = len(indices)
    mesh = c4d.PolygonObject(count*4, count)
    mesh.SetName("Gaussian Cards")
    centers, us, vs, normals, colors = prepared
    points = []
    uv = c4d.UVWTag(count)
    mesh.InsertTag(uv)
    color_tag = c4d.VertexColorTag(count*4)
    color_tag.SetName("SplatColor")
    mesh.InsertTag(color_tag)
    color_tag.SetPerPointMode(True)
    color_data = color_tag.GetDataAddressW()
    alpha_tag = c4d.VariableTag(c4d.Tvertexmap, count*4)
    alpha_tag.SetName("SplatOpacity")
    mesh.InsertTag(alpha_tag)
    normal_tag = c4d.NormalTag(count)
    mesh.InsertTag(normal_tag)
    mesh.MakeTag(c4d.Tphong)
    normal_data = normal_tag.GetDataAddressW()
    alphas = []
    corners = dict(a=c4d.Vector(0,0,0), b=c4d.Vector(1,0,0),
                   c=c4d.Vector(1,1,0), d=c4d.Vector(0,1,0))
    for n, (source_index, alpha) in enumerate(zip(indices, core.iter_attributes(cloud, 'opacity', indices))):
        if n % 1024 == 0:
            yield ('Build Gaussian cards', n, count)
        center, u, v = c4d.Vector(*centers[source_index]), c4d.Vector(*us[source_index]), c4d.Vector(*vs[source_index])
        points.extend((center-u-v, center+u-v, center+u+v, center-u+v))
        j = n*4
        mesh.SetPolygon(n, c4d.CPolygon(j,j+1,j+2,j+3))
        uv.SetSlow(n, **corners)
        rgba = c4d.Vector4d(*colors[source_index], min(1., alpha*opacity))
        for k in range(4):
            c4d.VertexColorTag.SetPoint(color_data, None, None, j+k, rgba)
        alphas.extend([min(1., max(0., alpha*opacity))]*4)
        normal = c4d.Vector(*normals[source_index])
        c4d.NormalTag.Set(normal_data,n,dict(a=normal,b=normal,c=normal,d=normal))
    mesh.SetAllPoints(points)
    del points
    yield ('Apply opacity', count, count)
    alpha_tag.SetAllHighlevelData(alphas)
    weights = weights or materials.DEFAULTS
    for name, setting in (
        ("SplatEmission", "emission_weight"),
        ("SplatDiffuse", "diffuse_weight"),
        ("SplatSubsurface", "subsurface_weight"),
    ):
        tag = c4d.VariableTag(c4d.Tvertexmap, count*4)
        tag.SetName(name)
        mesh.InsertTag(tag)
        tag.SetAllHighlevelData([float(weights[setting])]*(count*4))
        yield ('Apply ' + name, count, count)
    if material:
        texture = c4d.TextureTag()
        texture[c4d.TEXTURETAG_MATERIAL] = material
        texture[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
        mesh.InsertTag(texture)
    mesh.Message(c4d.MSG_UPDATE)
    return mesh


def cache_mesh(cache):
    """Find our card mesh without taking ownership of Cinema 4D's cache."""
    if cache is None:
        return None
    if cache.CheckType(c4d.Opolygon):
        return cache
    for child in cache.GetChildren():
        result = cache_mesh(child)
        if result is not None:
            return result
    return None


def update_mesh_attributes(mesh, cloud, prepared, opacity, weights,
                           update_colors=False, update_opacity=False,
                           update_weights=False, material=None, update_material=False):
    return complete_steps(update_mesh_steps(mesh, cloud, prepared, opacity, weights,
        update_colors, update_opacity, update_weights, material, update_material))


def update_mesh_steps(mesh, cloud, prepared, opacity, weights,
                      update_colors=False, update_opacity=False,
                      update_weights=False, material=None, update_material=False):
    """Update an owned clone's attributes, leaving points/UV/normals untouched.

    Never pass op.GetCache() directly: it belongs to Cinema 4D and may be in use
    by other generators or an interactive renderer. The caller owns this mesh.
    """
    indices = geometry.card_indices(prepared, weights.get('compact_cards', False))
    count = len(indices)
    if mesh.GetPointCount() != count * 4 or mesh.GetPolygonCount() != count:
        raise ValueError("Cached Gaussian mesh does not match the source cloud.")
    tags = {tag.GetName(): tag for tag in mesh.GetTags()}
    if update_colors or update_opacity:
        tag = tags["SplatColor"]
        data = tag.GetDataAddressW()
        colors = prepared[4]
        for index, (source_index, alpha) in enumerate(zip(indices, core.iter_attributes(cloud, 'opacity', indices))):
            if index % 1024 == 0:
                yield ('Update colour / opacity', index, count)
            rgba = c4d.Vector4d(*colors[source_index], min(1., max(0., alpha * opacity)))
            for corner in range(4):
                c4d.VertexColorTag.SetPoint(data, None, None, 4 * index + corner, rgba)
        tag.SetDirty(c4d.DIRTYFLAGS_DATA)
        tag.Message(c4d.MSG_UPDATE)
    if update_opacity:
        values = []
        for index, alpha in enumerate(core.iter_attributes(cloud, 'opacity', indices)):
            if index % 2048 == 0:
                yield ('Update opacity', index, count)
            values.extend([min(1., max(0., alpha * opacity))]*4)
        tag = tags["SplatOpacity"]
        tag.SetAllHighlevelData(values)
        tag.SetDirty(c4d.DIRTYFLAGS_DATA)
        tag.Message(c4d.MSG_UPDATE)
    for tag_name, setting in (
        ("SplatEmission", "emission_weight"),
        ("SplatDiffuse", "diffuse_weight"),
        ("SplatSubsurface", "subsurface_weight"),
    ):
        if update_weights is True or (update_weights and setting in update_weights):
            tag = tags[tag_name]
            tag.SetAllHighlevelData([float(weights[setting])] * (count * 4))
            tag.SetDirty(c4d.DIRTYFLAGS_DATA)
            tag.Message(c4d.MSG_UPDATE)
            yield ('Update ' + tag_name, count, count)
    if update_material:
        texture = mesh.GetTag(c4d.Ttexture)
        if material is None:
            if texture is not None:
                texture.Remove()
        else:
            if texture is None:
                texture = c4d.TextureTag()
                mesh.InsertTag(texture)
            texture[c4d.TEXTURETAG_MATERIAL] = material
            texture[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
            texture.SetDirty(c4d.DIRTYFLAGS_DATA)
            texture.Message(c4d.MSG_UPDATE)
    mesh.SetDirty(c4d.DIRTYFLAGS_DATA)
    mesh.Message(c4d.MSG_UPDATE)
    return mesh


class SplatObject(InteractiveScan, c4d.plugins.ObjectData):
    def __init__(self):
        super().__init__()
        self.op = None
        self.cloud = None
        self.load_key = None
        self.prepared = None
        self.spatial = self.colors = None
        self.spatial_key = self.color_key = None
        self.bounds = None
        self.draw_key = self.draw_data = None
        self.prepare_key = None
        self.cache_key = None
        self.last_camera = None
        self.last_color_key = None
        self.error = ""
        self.reported_error = ""
        self.material_key = None
        self.job = None
        self.log_offset = 0
        self.log_pending = b''
        self.progress_amount = None
        self.progress_message = ''
        self.progress_dialog = None
        INSTANCES.add(self)

    def Init(self, op, isCloneInit=False):
        self.op = op
        if not isCloneInit:
            for key, value in I.DEFAULTS.items():
                op[key] = value
        return True

    def Free(self, op):
        if self.job:
            PENDING.append((self,I.CANCEL))
            c4d.SpecialEventAdd(I.MESSAGE_ID)

    def Read(self, op, hf, level):
        # C4D merges saved containers over Init defaults. Without this explicit
        # migration, old documents would unexpectedly gain the new Y flip.
        if level < 1:
            op[I.AUTO_SOG_ORIENTATION] = False
            return True
        return hf.ReadInt32() == 1

    def Write(self, op, hf):
        return hf.WriteInt32(1)

    def CopyTo(self, dest, snode, dnode, flags, trn):
        # Persistent parameters are in the host's automatically copied container.
        # Transient meshes/workers intentionally start empty on a clone.
        return True

    def invalidate(self):
        self.cloud = self.prepared = None
        self.load_key = self.prepare_key = self.cache_key = None
        self.spatial = self.colors = None
        self.spatial_key = self.color_key = None
        self.bounds = None
        self.draw_key = self.draw_data = None

    def ensure_loaded(self, op, force=False):
        path = document_path(op,op[I.FILE])
        if not path:
            self.invalidate()
            return None
        original_path = path
        is_converted = False
        try:
            conversion_needed = converter().needs_conversion(path)
        except ImportError:
            conversion_needed = Path(path).suffix.lower() in (".sog",".ksplat")
        if conversion_needed:
            cached_path = document_path(op,op[I.CACHE_FILE])
            if (not assets.cache_source_matches(path,op[I.CACHE_SOURCE]) or not Path(cached_path).is_file()):
                raise RuntimeError("This format needs conversion. Click Initialise / Reload.")
            path = cached_path
            is_converted = True
        stat = os.stat(path)
        key = self.source_key(op)
        if force or key != self.load_key:
            cloud = None if force else CLOUD_CACHE.get(key)
            if cloud is None and not force:
                # A scene may contain more scans than the small global cache.
                # Their live generators still own the validated source arrays;
                # render clones should reuse those rather than parse them again.
                for other in list(INSTANCES):
                    if other is not self and getattr(other, 'load_key', None) == key:
                        cloud = getattr(other, 'cloud', None)
                        if cloud is not None:
                            break
            if cloud is None:
                cloud = core.load(path, max_splats=int(op[I.MAX_SPLATS]),
                    min_opacity=float(op[I.MIN_OPACITY]),
                    unconverted_coordinates=bool(op[I.SPZ_RAW]), compact=int(op[I.MAX_SPLATS]) > 262144)
                if is_converted and original_path.lower().endswith(".spz") and not op[I.SPZ_RAW]:
                    cloud = convert_spz_cloud_frame(cloud)
                # A small shared read-only cache prevents repeat disk parsing in render clones.
                if len(CLOUD_CACHE) >= 3:
                    CLOUD_CACHE.pop(next(iter(CLOUD_CACHE)))
                CLOUD_CACHE[key] = cloud
            self.cloud, self.load_key = cloud, key
            self.prepare_key = self.cache_key = None
            self.spatial_key = self.color_key = None
            self.draw_key = None
            self.error = ""
        return self.cloud

    def prepare(self, op):
        # Cinema 4D can copy Python NodeData during document reload/cloning.
        # Bind the current host object instead of retaining a copied link.
        self.op = op
        cloud = self.ensure_loaded(op)
        if cloud is None:
            return None
        values = settings(op)
        degree = cloud.metadata.get('effective_sh_degree', cloud.metadata.get('sh_degree', 0))
        camera_dependent = values['camera_facing'] or loading.effective_degree(values, degree)
        camera = projection_camera(op) if camera_dependent else (0.,0.,-500.)
        doc = op.GetDocument()
        spatial_camera = camera if op[I.CAMERA_FACING] else (0.,0.,-500.)
        spatial_key, color_key = loading.preparation_keys(
            self.load_key, values, camera, degree, color_configuration_key(doc))
        # Render document copies are new NodeData instances. Reuse immutable
        # prepared arrays from a matching live instance instead of redoing all
        # geometry/SH work each time Redshift starts a new render document.
        for other in list(INSTANCES):
            if other is self or getattr(other, 'load_key', None) != self.load_key:
                continue
            if other.spatial_key == spatial_key and other.spatial is not None:
                self.spatial, self.bounds, self.spatial_key = other.spatial, other.bounds, spatial_key
            if other.color_key == color_key and other.colors is not None:
                self.colors, self.color_key = other.colors, color_key
            if self.spatial_key == spatial_key and self.color_key == color_key:
                break
        if spatial_key != getattr(self, "spatial_key", None):
            self.spatial = geometry.prepare_geometry(cloud, values, spatial_camera)
            self.spatial_key = spatial_key
            positions, us, vs = self.spatial[:3]
            self.bounds = []
            for axis in range(3):
                lo = min((p[axis]-abs(u[axis])-abs(v[axis])
                          for p, u, v in zip(positions, us, vs)), default=0.)
                hi = max((p[axis]+abs(u[axis])+abs(v[axis])
                          for p, u, v in zip(positions, us, vs)), default=0.)
                self.bounds.append(((lo + hi) * .5, max(.01, (hi - lo) * .5)))
        if color_key != getattr(self, "color_key", None):
            colors = geometry.prepare_colors(cloud, values, camera, self.spatial[0])
            self.colors = working_colors(doc, colors)
            self.color_key = color_key
        key = (self.spatial_key, self.color_key)
        if key != self.prepare_key:
            self.prepared = self.spatial + (self.colors,)
            self.prepare_key = key
        return self.prepared

    def GetVirtualObjects(self, op, hierarchyhelp):
        flags = self.GetVirtualObjectsBuildFlags()
        render = bool(flags & (c4d.BUILDFLAGS_EXTERNALRENDERER |
            c4d.BUILDFLAGS_INTERNALRENDERER | c4d.BUILDFLAGS_MAKEEDITABLE | c4d.BUILDFLAGS_EXPORT))
        if not render and is_open_document(op.GetDocument()):
            return self.interactive_cache(op)
        return self.synchronous_cache(op, hierarchyhelp)

    def synchronous_cache(self, op, hierarchyhelp):
        try:
            prepared = self.prepare(op)
            if prepared is None:
                return c4d.BaseObject(c4d.Onull)
            flags = self.GetVirtualObjectsBuildFlags()
            render = bool(flags & (c4d.BUILDFLAGS_EXTERNALRENDERER |
                c4d.BUILDFLAGS_INTERNALRENDERER | c4d.BUILDFLAGS_MAKEEDITABLE |
                c4d.BUILDFLAGS_EXPORT))
            point_preview = bool(op[I.POINT_PREVIEW]) and not render
            weights = (float(op[I.EMISSION]),float(op[I.DIFFUSE]),float(op[I.SUBSURFACE]))
            key = (self.spatial_key, self.color_key, point_preview,
                   float(op[I.OPACITY]), op[I.MATERIAL], weights)
            cached = op.GetCache()
            if key == self.cache_key and cached:
                return cached
            previous = self.cache_key
            old_mesh = cache_mesh(cached)
            if previous is None or previous[0] != key[0] or old_mesh is None:
                for owner in [self] + [x for x in list(INSTANCES) if x is not self]:
                    ready = getattr(owner, 'ready_request', None)
                    template = getattr(owner, 'mesh_template', None)
                    if ready and template is not None and ready[0] == key[0]:
                        old_mesh = template
                        previous = (ready[0], ready[1], False, ready[2], ready[4], ready[3])
                        if ready[1] == key[1]:
                            break
            if (previous is not None and len(previous) == 6 and previous[0] == key[0]
                    and old_mesh is not None):
                # Native cloning copies the arrays in bulk. Only the changed
                # attributes cross the Python API; the document cache stays
                # untouched for render clones and MoGraph consumers.
                result = old_mesh.GetClone(c4d.COPYFLAGS_NONE)
                weight_names = ("emission_weight", "diffuse_weight", "subsurface_weight")
                changed_weights = tuple(name for i, name in enumerate(weight_names)
                                        if previous[5][i] != weights[i])
                update_mesh_attributes(result, self.cloud, prepared,
                    float(op[I.OPACITY]), settings(op),
                    update_colors=previous[1] != key[1],
                    update_opacity=previous[3] != key[3],
                    update_weights=changed_weights, material=op[I.MATERIAL],
                    update_material=previous[4] != key[4])
            else:
                result = build_mesh(
                    self.cloud, prepared, op[I.MATERIAL], float(op[I.OPACITY]),settings(op))
            result.SetEditorMode(c4d.MODE_UNDEF)
            if point_preview:
                # RenderView IPR reads the editor cache without a render build
                # flag. Keep all cards available and hide only their editor
                # display. A visible parent retains this generator's Draw()
                # callback for the independently limited point preview.
                root = c4d.BaseObject(c4d.Onull)
                root.SetName("Gaussian Preview")
                result.SetEditorMode(c4d.MODE_OFF)
                result.InsertUnder(root)
                result = root
            self.cache_key = key
            return result
        except Exception as error:
            self.error = str(error)
            self.invalidate()
            return c4d.BaseObject(c4d.Onull)

    def GetDimension(self, op, mp, rad):
        bounds = getattr(self, "bounds", None)
        if bounds is not None:
            for i, attr in enumerate(("x","y","z")):
                setattr(mp, attr, bounds[i][0])
                setattr(rad, attr, bounds[i][1])

    def Draw(self, op, drawpass, bd, bh):
        prepared = self.prepared
        if drawpass != c4d.DRAWPASS_OBJECT or not op[I.FILE] or not op[I.POINT_PREVIEW] or not prepared:
            return c4d.DRAWRESULT_SKIP
        positions, _, _, _, colors = prepared
        limit = int(op[I.PREVIEW_COUNT])
        count = len(positions) if limit <= 0 else min(limit, len(positions))
        if not count:
            return c4d.DRAWRESULT_OK
        bd.SetMatrix_Matrix(op, bh.GetMg())
        draw_key = (self.prepare_key, count)
        if draw_key != getattr(self, "draw_key", None):
            indices = [i*len(positions)//count for i in range(count)]
            points = [c4d.Vector(*positions[i]) for i in indices]
            # Mesh and point preview share document working-space RGB.
            point_colors = [value for i in indices for value in colors[i]]
            self.draw_data = points, point_colors
            self.draw_key = draw_key
        points, point_colors = self.draw_data
        bd.DrawPoints(points, point_colors, 3, None)
        return c4d.DRAWRESULT_OK

    def AddToExecution(self, op, execution_list):
        execution_list.Add(op,c4d.EXECUTIONPRIORITY_EXPRESSION,0)
        return True

    def Execute(self, op, doc, bt, priority, flags):
        self.op = op
        color_key = color_configuration_key(doc)
        if color_key != self.last_color_key:
            self.last_color_key = color_key
            op.SetDirty(c4d.DIRTYFLAGS_DATA)
        degree = (self.cloud.metadata.get('effective_sh_degree', self.cloud.metadata.get('sh_degree', 0))
                  if self.cloud else 0)
        camera_dependent = bool(op[I.CAMERA_FACING] or (op[I.SH_DEGREE] and op[I.SH_STRENGTH] and degree))
        camera = projection_camera(op) if camera_dependent else None
        if op[I.CAMERA_FACING]:
            projection = screen_projection(op)
            camera = (camera, tuple(sorted(projection.items())) if projection else None)
        camera = loading.view_key(camera)
        if camera != self.last_camera:
            self.last_camera = camera
            if camera_dependent:
                op.SetDirty(c4d.DIRTYFLAGS_DATA)
        return c4d.EXECUTIONRESULT_OK

    def Message(self, op, message, data):
        self.op = op
        if assets.handle_message(op,message,data):
            return True
        if message == c4d.MSG_DESCRIPTION_COMMAND and data:
            action = data["id"][0].id
            if action in (I.INITIALISE,I.GENERATE,I.CANCEL,I.SETUP,I.OPEN_OUTPUT,I.MOGRAPH,
                          I.DETAIL_PRESET,I.PREPARE_REDSHIFT,I.SOURCE_CAMERA,I.PREVIEW_SOURCE,
                          I.SUPPORT_AUTHOR,I.FRAME_SCAN):
                PENDING.append((self, action))
                c4d.SpecialEventAdd(I.MESSAGE_ID)
        return True

    def GetDEnabling(self, op, descid, t_data, flags, itemdesc):
        key = descid[0].id
        if key in (I.SH_DEGREE,I.SH_STRENGTH) and self.cloud:
            return bool(self.cloud.metadata.get("sh_degree",0))
        if key == I.SPZ_RAW:
            return str(op[I.FILE] or "").lower().endswith(".spz")
        if key == I.CANCEL:
            return self.job is not None
        if key in (I.INITIALISE,I.GENERATE,I.SETUP,I.PREVIEW_SOURCE,I.IMAGE,I.INPUT_MODE,
                   I.SOURCE_FRAME,I.NUM_GAUSSIANS,I.STEPS,I.SEED,I.ALPHA_EROSION,I.FRAME_SCAN):
            return self.job is None
        return True

    def GetDDescription(self, op, description, flags):
        from .description import describe
        return describe(op, description, flags)

    def set_progress(self, message, amount=None):
        self.progress_message = str(message)
        self.progress_amount = amount
        self.refresh_status(force=True)
        c4d.EventAdd()

    def refresh_status(self, force=False):
        """Explain an intentional camera override without changing it or rebuilding."""
        op = self.op
        if op is None:
            return
        warning = ('\nProjection Camera differs from the render camera. '
                   'Clear Projection Camera to follow the render camera.')
        message = str(self.progress_message if force else op[I.STATUS] or '')
        if message.endswith(warning):
            message = message[:-len(warning)]
        if not message:
            return
        doc = op.GetDocument()
        override = op[I.CAMERA]
        if doc and override and (op[I.CAMERA_FACING] or
                                (op[I.SH_DEGREE] and op[I.SH_STRENGTH])):
            bd = doc.GetRenderBaseDraw()
            current = (bd.GetSceneCamera(doc) or bd.GetEditorCamera()) if bd else None
            if current and current != override:
                message += warning
        if op[I.STATUS] != message:
            op[I.STATUS] = message

    def show_progress(self):
        from .progress_ui import show
        try:
            show(self)
        except Exception as error:
            print("Argentum Splat progress window:", error)

    def close_progress(self):
        from .progress_ui import close
        close(self)

    def sync_material(self, force=False):
        op, doc = self.op, self.op.GetDocument()
        if doc is None or not is_open_document(doc):
            return
        key = op[I.MATERIAL]
        if not force and key is not None and key == self.material_key:
            return
        c4d.StopAllThreads()
        mat = op[I.MATERIAL]
        if mat is None:
            mat = materials.create_material(doc, settings=settings(op))
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, mat)
            op[I.MATERIAL] = mat
        else:
            # Upgrade older material graphs; per-splat maps drive the weights.
            materials.update_material(mat,settings(op))
        self.material_key = mat
        c4d.EventAdd()

    def initialise(self):
        self.start_scan(explicit=True)

    def start_conversion(self, source):
        require_idle()
        signature = source_signature(source)
        import hashlib
        folder = RUNTIME.parent/"converted"/hashlib.sha256(signature.encode("utf8")).hexdigest()[:24]
        folder.mkdir(parents=True,exist_ok=True)
        target = folder/("converted-"+uuid.uuid4().hex[:8]+".ply")
        command = converter().conversion_command(source,str(target))
        log = (folder/"conversion.log").open("wb")
        try:
            proc = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                shell=False,cwd=str(folder),creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except Exception:
            log.close()
            raise
        self.job = dict(process=proc,log=log,dir=folder,result=target,kind="convert",
                        source_signature=signature,source=str(Path(source).resolve()))
        JOBS.add(self)
        self.set_progress("Converting "+Path(source).suffix+" locally; the source file is preserved.")
        self.show_progress()

    def start_generation(self, preview_only=False):
        require_idle()
        image = Path(document_path(self.op,self.op[I.IMAGE]))
        if not image.is_file():
            raise ValueError("Choose an input image, video or splat file first.")
        mode = int(self.op[I.INPUT_MODE] or 0)
        frame = int(self.op[I.SOURCE_FRAME] or 0)
        kind = input_source.classify(image, mode)
        input_source.validate_frame(frame)
        if kind == 'splat':
            if preview_only:
                raise ValueError('This is a 3D splat file. Click Load / Generate from Input to load it.')
            doc = self.op.GetDocument()
            doc.StartUndo()
            try:
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, self.op)
                self.op[I.FILE] = str(image.resolve())
                self.initialise()
            finally:
                doc.EndUndo()
            return
        if kind == 'sequence':
            input_source.sequence_frame(image, frame)
        marker = RUNTIME/"runtime.json"
        if not marker.is_file():
            raise RuntimeError("Local AI is not installed. Click Set Up Local AI Backend.")
        runtime = json.loads(marker.read_text(encoding="utf8"))
        python = runtime["python_exe"]
        if not Path(python).is_file():
            raise RuntimeError("Backend Python is missing. Run setup again.")
        base = Path(document_path(self.op,self.op[I.OUTPUT_DIR]) or RUNTIME.parent/"generated")
        jobdir = base/(time.strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:6])
        jobdir.mkdir(parents=True,exist_ok=False)
        request = dict(image_path=str(image.resolve()),output_dir=str(jobdir),
            num_gaussians=int(self.op[I.NUM_GAUSSIANS]),steps=int(self.op[I.STEPS]),
            seed=int(self.op[I.SEED]),guidance_scale=3.,shift=3.,
            erode_radius=int(self.op[I.ALPHA_EROSION] or 0),
            input_mode=mode,source_frame=frame,preview_only=bool(preview_only))
        request_path, result_path = jobdir/"request.json",jobdir/"result.json"
        request_path.write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding="utf8")
        log = (jobdir/"generation.log").open("wb")
        try:
            proc = subprocess.Popen([python,str(ROOT/"backend"/"worker.py"),
                "--request",str(request_path),"--result",str(result_path)],
                stdout=log,stderr=subprocess.STDOUT,cwd=str(ROOT),shell=False,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except Exception:
            log.close()
            raise
        self.job = dict(process=proc,log=log,dir=jobdir,result=result_path,kind="generate",
                        preview_only=bool(preview_only),input_signature=(str(image.resolve()),mode,frame))
        JOBS.add(self)
        self.log_offset = 0
        self.log_pending = b''
        self.set_progress('Preparing selected frame' if preview_only else 'Starting local TripoSplat generation', 0.)
        self.show_progress()

    def start_setup(self, kind="setup"):
        require_idle()
        RUNTIME.mkdir(parents=True,exist_ok=True)
        log = (RUNTIME/(kind+".log")).open("wb")
        script = "setup_formats.ps1" if kind == "formats" else "setup_all.ps1"
        run_id = uuid.uuid4().hex
        args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT/script)]
        if kind != 'formats':
            args += ['-RunId', run_id]
        try:
            proc = subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,
                cwd=str(ROOT),shell=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except Exception:
            log.close()
            raise
        self.job = dict(process=proc,log=log,dir=RUNTIME,result=None,kind=kind,run_id=run_id)
        JOBS.add(self)
        self.set_progress("Installing extra format support (PlayCanvas)."
            if kind == "formats" else "Installing isolated AI runtime and model weights (~several GB).")
        self.show_progress()

    def cancel(self, notify=True):
        if self.job and self.job.get('kind') == 'scan':
            self.cancel_scan(notify=notify)
            if self.job['worker'].done.is_set():
                self.release_scan()
                if notify and self.op and is_open_document(self.op.GetDocument()):
                    self.set_progress('Cancelled. Previous complete model preserved.', None)
            return
        if not self.job:
            self.close_progress()
            return
        proc = self.job["process"]
        if proc.poll() is None:
            subprocess.run(["taskkill.exe","/PID",str(proc.pid),"/T","/F"],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),timeout=5,check=False)
            proc.wait(timeout=2)
        self.job["log"].close()
        self.scan_state()
        try:
            self.blocked_request = self.request_snapshot()['key']
        except (OSError, ReferenceError):
            self.blocked_request = None
        self.queued_request = None
        self.job = None
        JOBS.discard(self)
        self.close_progress()
        if not notify:
            return
        try:
            if self.op and is_open_document(self.op.GetDocument()):
                self.op[I.STATUS] = "Cancelled. Any completed files remain in the output folder."
                c4d.EventAdd()
        except ReferenceError:
            pass

    def poll(self):
        self.scan_state()
        if self.job and self.job.get('kind') == 'scan':
            self.poll_scan()
            return
        if self.error and self.error != self.reported_error:
            self.op[I.STATUS] = "Error: "+self.error
            self.reported_error = self.error
        if not self.job:
            if self.queued_request and time.monotonic()-self.queued_at >= .60:
                self.start_scan()
                return
            if self.cloud:
                self.sync_material()
            return
        job = self.job
        code = job["process"].poll()
        if code is None:
            if job["kind"] == "generate":
                logfile = job["dir"]/"generation.log"
                updates, self.log_offset, self.log_pending = job_progress.read_updates(
                    logfile,self.log_offset,getattr(self,'log_pending',b''))
                if updates:
                    item = updates[-1]
                    self.set_progress(item['message'], item['progress'])
            return
        job["log"].close()
        self.job = None
        JOBS.discard(self)
        if job['kind'] != 'convert':
            self.close_progress()
        # Completion is delivered by the timer while viewport evaluation may
        # still be running. Stop scene readers before applying new links/data.
        c4d.StopAllThreads()
        if job["kind"] == "convert":
            if code != 0 or not job["result"].is_file():
                raise RuntimeError("Conversion failed. See "+str(job["dir"]/"conversion.log"))
            if source_signature(document_path(self.op,self.op[I.FILE])) != job["source_signature"]:
                self.close_progress()
                self.op[I.STATUS] = "Conversion completed for the previous source. Click Initialise for the current file."
                return
            # The cancellable scan reader validates the conversion exactly once.
            self.op[I.CACHE_SOURCE] = job["source_signature"]
            self.op[I.CACHE_FILE] = str(job["result"])
            self.initialise()
            return
        if job["kind"] == "formats":
            self.op[I.STATUS] = ("Extra formats are ready." if code == 0 else
                "Format setup failed. See "+str(RUNTIME/"formats.log"))
            c4d.EventAdd()
            return
        if job["kind"] == "setup":
            summary = 'Setup needs attention. See ' + str(RUNTIME/'setup.log')
            try:
                result = json.loads((RUNTIME/'setup-result.json').read_text(encoding='utf8'))
                if result.get('run_id') != job.get('run_id'):
                    raise ValueError('Setup report belongs to another run.')
                summary = 'Extra formats: %s. AI: %s.' % (result['formats'], result['ai'])
                if result.get('errors'):
                    summary += ' ' + ' | '.join(result['errors'])
                elif code != 0:
                    summary += ' Setup interrupted or failed. See ' + str(RUNTIME/'setup.log')
            except (OSError, ValueError, KeyError):
                pass
            self.op[I.STATUS] = ("AI and extra formats are ready. Choose an image and Generate." if code == 0 else summary)
            c4d.EventAdd()
            return
        if job["result"].is_file():
            result = json.loads(job["result"].read_text(encoding="utf8"))
            if code == 0 and result.get("ok"):
                current = (str(Path(document_path(self.op,self.op[I.IMAGE])).resolve()),
                           int(self.op[I.INPUT_MODE] or 0),int(self.op[I.SOURCE_FRAME] or 0))
                if job.get('input_signature',current) != current:
                    self.set_progress('Input changed. Completed files are saved in ' + str(job['dir']))
                    return
                if result.get('preview_only'):
                    bitmap = c4d.bitmaps.BaseBitmap()
                    status, _ = bitmap.InitWith(result['input_frame_path'])
                    if status != c4d.IMAGERESULT_OK:
                        raise RuntimeError('Cannot display selected input frame.')
                    c4d.bitmaps.ShowBitmap(bitmap)
                    self.set_progress('Selected frame opened in Picture Viewer. Ready to generate.')
                    return
                doc = self.op.GetDocument()
                doc.StartUndo()
                try:
                    doc.AddUndo(c4d.UNDOTYPE_CHANGE,self.op)
                    self.op[I.FILE] = result["ply_path"]
                    self.op[I.FLIP_Y] = bool(result.get("recommended_c4d_flip_y",True))
                    self.op[I.OUTPUT_DIR] = str(job["dir"].parent)
                    self.initialise()
                finally:
                    doc.EndUndo()
                return
            raise RuntimeError(result.get("error","Generation failed."))
        raise RuntimeError("AI exited with code {}. See {}".format(code,job["dir"]/"generation.log"))


class Coordinator(c4d.plugins.MessageData):
    def GetTimer(self):
        return 40

    def CoreMessage(self, message, bc):
        if message not in (c4d.MSG_TIMER,I.MESSAGE_ID,c4d.EVMSG_CHANGE):
            return True
        while PENDING:
            instance, action = PENDING.pop(0)
            if action == I.SUPPORT_AUTHOR:
                # A browser action must not rebuild geometry or overwrite job status.
                import webbrowser
                url = 'https://boosty.to/olehandrostox/donate'
                try:
                    opened = webbrowser.open_new_tab(url)
                except Exception:
                    opened = False
                if not opened:
                    print('Argentum Splat: Support the author at ' + url)
                continue
            try:
                if action == I.CANCEL:
                    instance.cancel()
                    continue
                op = instance.op
                doc = op.GetDocument()
                if doc is None or not is_open_document(doc):
                    continue
                c4d.StopAllThreads()
                if action == I.INITIALISE:
                    doc.StartUndo()
                    try:
                        doc.AddUndo(c4d.UNDOTYPE_CHANGE,op)
                        instance.initialise()
                    finally:
                        doc.EndUndo()
                elif action == I.GENERATE:
                    instance.start_generation()
                elif action == I.PREVIEW_SOURCE:
                    instance.start_generation(preview_only=True)
                elif action == I.SETUP:
                    instance.start_setup()
                elif action == I.MOGRAPH:
                    from .mograph import create_rig
                    create_rig(op)
                elif action == I.FRAME_SCAN:
                    from .scene_setup import explicit_frame
                    explicit_frame(op)
                elif action in (I.DETAIL_PRESET,I.PREPARE_REDSHIFT,I.SOURCE_CAMERA):
                    from . import quality
                    if action == I.DETAIL_PRESET:
                        quality.apply_detail_preset(op)
                    elif action == I.PREPARE_REDSHIFT:
                        quality.prepare_redshift(op)
                    else:
                        quality.create_source_camera(op)
                elif action == I.OPEN_OUTPUT:
                    folder = instance.job["dir"] if instance.job else Path(
                        document_path(op,op[I.OUTPUT_DIR]) or RUNTIME.parent/"generated")
                    if folder.is_dir():
                        os.startfile(str(folder))
            except Exception as error:
                try:
                    instance.report_failure(error)
                except ReferenceError:
                    pass
                print("Argentum Splat:",error)
        if message == c4d.MSG_TIMER:
            for instance in set(INSTANCES)|JOBS:
                try:
                    if instance.op and is_open_document(instance.op.GetDocument()):
                        instance.poll()
                        instance.refresh_status()
                    elif instance.job:
                        instance.cancel(notify=False)
                except ReferenceError:
                    if instance.job:
                        try:
                            instance.cancel(notify=False)
                        except Exception as error:
                            print("Argentum Splat cancellation:",error)
                except Exception as error:
                    try:
                        instance.report_failure(error)
                    except ReferenceError:
                        pass
        return True


class CreateSplat(c4d.plugins.CommandData):
    def Execute(self, doc):
        c4d.StopAllThreads()
        doc.StartUndo()
        try:
            op = c4d.BaseObject(I.OBJECT_ID)
            op.SetName("Argentum Splat")
            doc.InsertObject(op)
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,op)
            doc.SetActiveObject(op,c4d.SELECTION_NEW)
        finally:
            doc.EndUndo()
        c4d.EventAdd()
        return True
