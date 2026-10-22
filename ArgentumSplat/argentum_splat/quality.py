"""Explicit, undoable quality actions; never silently modify render settings."""
import json
import math
from pathlib import Path
import c4d
import maxon
from . import ids as I, assets, materials


def apply_detail_preset(op):
    """Keep captured appearance and all covariance dimensions for the camera."""
    doc = op.GetDocument()
    if doc is None:
        raise ValueError("The Splat object must be in a document.")
    doc.StartUndo()
    try:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
        op[I.CAMERA_FACING] = True
        # Our Jacobian uses actual pixels (width / (2*tan(fov/2))).
        # A viewer using width/tan(fov/2) and a 0.3 covariance ridge therefore
        # corresponds to 0.3/4 = 0.075 here, not 0.3 real pixel squared.
        op[I.PIXEL_VARIANCE] = .075
        op[I.SH_DEGREE] = 3
        op[I.SH_STRENGTH] = 1.0
        op[I.SMOOTHING] = 0  # Captured unlit colour does not need smoothed normals.
        op[I.MAX_SPLATS] = max(int(op[I.MAX_SPLATS]), 3000000)
        # Follow the current render camera, including camera switches.
        op[I.CAMERA] = None
        op[I.EMISSION] = 1.0
        op[I.DIFFUSE] = 0.0
        op[I.SUBSURFACE] = 0.0
        op[I.MIN_OPACITY] = min(float(op[I.MIN_OPACITY]), 1.0/255.0)
        instance = op.GetNodeData()
        mat = op[I.MATERIAL]
        if mat:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, mat)
            materials.update_material(mat, {
                "emission_weight": 1.0, "diffuse_weight": 0.0,
                "subsurface_weight": 0.0,
            }, undo_mode=maxon.nodes.UNDO_MODE.ADD)
        op[I.STATUS] = (
            "Source Fidelity: up to 3,000,000 splats, full SH, perspective pixel filtering, "
            "captured colour (Emission 1 / Diffuse 0). Larger scans remain sampled. "
            "SH0 files contain fixed highlights, not dynamic glass reflections."
        )
        op.SetDirty(c4d.DIRTYFLAGS_DATA)
    finally:
        doc.EndUndo()
    # The same cancellable pipeline handles opacity reloading and new cards.
    # Preserve the old complete model until the replacement is ready.
    instance.start_scan()
    c4d.EventAdd()


def prepare_redshift(op):
    """Raise depth/sampling floors only after the user presses the named button."""
    doc = op.GetDocument()
    rd = doc.GetActiveRenderData()
    if rd[c4d.RDATA_RENDERENGINE] != 1036219:
        raise ValueError("Select Redshift in Render Settings first.")
    vp = rd.GetFirstVideoPost()
    while vp and vp.GetType() != 1036219:
        vp = vp.GetNext()
    if vp is None:
        raise ValueError("Redshift settings are not initialized.")
    # Use SDK symbols; never change unrelated lighting, GI, OCIO, or exposure.
    depth_ids = [
        getattr(c4d, name) for name in (
            "REDSHIFT_RENDERER_MAX_TRACE_DEPTH_TRANSPARENCY",
            "REDSHIFT_RENDERER_BASIC_MAX_TRACE_DEPTH_TRANSPARENCY",
        ) if hasattr(c4d, name)
    ]
    if not depth_ids:
        raise RuntimeError("The required Redshift transparency settings are unavailable.")
    doc.StartUndo()
    try:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, vp)
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
        for key in depth_ids:
            vp[key] = max(int(vp[key] or 0), 128)
        for name, minimum in (
            ("REDSHIFT_RENDERER_UNIFIED_MIN_SAMPLES", 16),
            ("REDSHIFT_RENDERER_UNIFIED_MAX_SAMPLES", 128),
        ):
            key = getattr(c4d, name)
            vp[key] = max(int(vp[key] or 0), minimum)
        # Manual sample floors have no effect while Automatic Sampling is on.
        vp[c4d.REDSHIFT_RENDERER_ENABLE_AUTOMATIC_SAMPLING] = False
        for name in ('REDSHIFT_RENDERER_UNIFIED_ADAPTIVE_ERROR_THRESHOLD',
                     'REDSHIFT_RENDERER_BASIC_UNIFIED_ADAPTIVE_ERROR_THRESHOLD'):
            key = getattr(c4d, name, None)
            if key is not None:
                current = float(.01 if vp[key] is None else vp[key])
                vp[key] = min(current, .01)
        op[I.STATUS] = (
            "Redshift detail settings: transparency depth >= 128; "
            "manual samples >= 16 / 128; threshold <= 0.01. "
            "Existing stricter settings are preserved. "
            "Rendering can take longer."
        )
    finally:
        doc.EndUndo()
    c4d.EventAdd()


def source_camera_data(op):
    source = Path(assets.resolve_path(op, op[I.FILE]))
    metadata_path = source.parent/"generation.json"
    if not metadata_path.is_file():
        raise ValueError("This scan has no generated source-camera metadata.")
    if metadata_path.stat().st_size > 1024*1024:
        raise ValueError("Generation metadata is too large.")
    metadata = json.loads(metadata_path.read_text(encoding="utf8"))
    camera = metadata.get("source_camera", {})
    if not camera.get("available"):
        raise ValueError("Source camera is unavailable. Generate a new image with version 0.2 or later.")
    return camera


def create_source_camera(op):
    """Create a new editable camera; keep existing cameras in the document."""
    camera = source_camera_data(op)
    frame = camera["exported_ply"]
    scale = float(op[I.SCALE])
    flip = bool(op[I.FLIP_Y])
    def transform(value, direction=False):
        x,y,z = [float(v) for v in value]
        if not all(math.isfinite(v) for v in (x,y,z)):
            raise ValueError("Source camera contains non-finite values.")
        if flip:
            y = -y
        vector = c4d.Vector(x,y,z)
        return op.GetMg().MulV(vector).GetNormalized() if direction else op.GetMg()*(vector*scale)
    eye = transform(frame["eye"])
    target = transform(frame["target"])
    up = transform(frame["up"], True)
    forward = (target-eye).GetNormalized()
    right = up.Cross(forward).GetNormalized()
    corrected_up = forward.Cross(right).GetNormalized()
    if right.GetLength() < 0.5:
        raise ValueError("Source camera orientation is singular.")
    fov = float(camera["fov_radians"])
    if not 0 < fov < math.pi:
        raise ValueError("Source camera field of view is invalid.")
    doc = op.GetDocument()
    cam = c4d.BaseObject(c4d.Ocamera)
    cam.SetName(op.GetName()+" - Source View")
    cam.SetMg(c4d.Matrix(eye,right,corrected_up,forward))
    cam[c4d.CAMERA_FOCUS] = float(cam[c4d.CAMERAOBJECT_APERTURE])/(2.0*math.tan(fov/2.0))
    # C4D clamps focal length (e.g. to 10000 mm). Near-orthographic TripoSplat
    # predictions often exceed that with a 36 mm sensor. Adjust the aperture
    # using the accepted focal length so the predicted field of view survives.
    cam[c4d.CAMERAOBJECT_APERTURE] = (
        2.0 * float(cam[c4d.CAMERA_FOCUS]) * math.tan(fov / 2.0))
    actual_fov = 2.0 * math.atan2(
        float(cam[c4d.CAMERAOBJECT_APERTURE]), 2.0 * float(cam[c4d.CAMERA_FOCUS]))
    if not math.isclose(actual_fov, fov, rel_tol=1e-6, abs_tol=1e-10):
        raise ValueError("The predicted camera field of view exceeds Cinema 4D's lens range.")
    doc.StartUndo()
    try:
        doc.InsertObject(cam)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, cam)
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
        op[I.STATUS] = (
            "Source View camera created from the model prediction. "
            "Use a square frame to match prepared.png. "
            "Position/framing is an estimate and remains editable."
        )
        doc.SetActiveObject(cam,c4d.SELECTION_NEW)
    finally:
        doc.EndUndo()
    c4d.EventAdd()
    return cam
