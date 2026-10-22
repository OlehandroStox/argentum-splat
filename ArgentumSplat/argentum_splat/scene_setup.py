"""Safe initial framing. Existing scene cameras and hand-edited views win."""
import json
import math
import c4d
from . import ids as I, import_analysis, loading


def xyz(vector):
    return vector.x,vector.y,vector.z


def source_marker(key):
    return json.dumps(key[:3]) if key else ''


def camera_state(cam):
    mg=cam.GetMg()
    return json.dumps(loading.view_key([xyz(a) for a in (mg.off,mg.v1,mg.v2,mg.v3)] +
                     [float(cam[k]) for k in (c4d.CAMERA_FOCUS,c4d.CAMERAOBJECT_APERTURE,
                      c4d.CAMERA_PROJECTION,c4d.CAMERAOBJECT_NEAR_CLIPPING,
                      c4d.CAMERAOBJECT_NEAR_CLIPPING_ENABLE,c4d.CAMERAOBJECT_FAR_CLIPPING,
                      c4d.CAMERAOBJECT_FAR_CLIPPING_ENABLE)]))


def automatic_available(op):
    doc=op.GetDocument()
    if not doc or op[I.CAMERA]:
        return False
    bd=doc.GetRenderBaseDraw()
    active=bd.GetSceneCamera(doc) if bd else None
    if bd and active==bd.GetEditorCamera():
        active=None
    owned=op[I.IMPORT_CAMERA]
    if owned is not None and camera_state(owned) != op[I.IMPORT_CAMERA_STATE]:
        return False
    if active is not None:
        if owned is None or active != owned:
            return False
    # Even hidden objects can be important scene content. Do not reframe it.
    roots=doc.GetObjects()
    return op.GetUp() is None and op.GetDown() is None and all(o==op or (owned is not None and o==owned) for o in roots)


def needs_initial_analysis(op,key):
    return (bool(op[I.AUTO_FRAME]) and op[I.AUTO_FRAME_SOURCE] != source_marker(key)
            and automatic_available(op))


def frame_scan(op, report, automatic=False):
    from . import plugin, quality
    doc=op.GetDocument()
    if automatic and not automatic_available(op):
        return None
    if not doc:
        raise ValueError('The scan must be in a document.')
    bd=doc.GetRenderBaseDraw()
    # Prefer the AI's source view when its metadata exists, but malformed or
    # missing metadata must never abort an otherwise valid Gaussian import.
    source_camera=None
    try:
        source_camera=quality.source_camera_data(op,require_match=True)
    except (ValueError,KeyError,TypeError,AttributeError,OSError):
        pass
    values=plugin.settings(op)
    scale=values['scale'];flip=values['flip_y'];mg=op.GetMg()
    def point(p):
        x,y,z=p
        return mg*c4d.Vector(x*scale,(-y if flip else y)*scale,z*scale)
    points=[xyz(point(p)) for p in import_analysis.corners(report['bounds'])]
    current=bd.GetSceneCamera(doc) or bd.GetEditorCamera()
    view=current.GetMg() if current else c4d.Matrix()
    forward,up=xyz(view.v3),xyz(view.v2)
    fov=math.radians(50.)
    rd=doc.GetActiveRenderData()
    aspect=max(1.,float(rd[c4d.RDATA_XRES]))*float(rd[c4d.RDATA_PIXELASPECT] or 1.)/max(1.,float(rd[c4d.RDATA_YRES]))
    fit=import_analysis.fit_camera(points,xyz(view.v1),up,forward,fov,aspect)
    # The inferred AI source pose gives a better starting view than a generic
    # box fit; widen the FOV for non-square output so the source stays visible.
    if source_camera:
        try:
            frame=source_camera['exported_ply']
            if not all(len(frame[k])==3 and all(math.isfinite(float(v)) for v in frame[k])
                       for k in ('eye','target','up')):
                raise ValueError('Invalid source view.')
            eye,target=point(frame['eye']),point(frame['target'])
            u=c4d.Vector(*frame['up'])
            if flip: u.y=-u.y
            f=(target-eye).GetNormalized();r=mg.MulV(u).Cross(f).GetNormalized();u=f.Cross(r).GetNormalized()
            original_fov=float(source_camera['fov_radians'])
            if not 0 < original_fov < math.pi or not all(math.isfinite(v) for a in (eye,target,u,f,r) for v in xyz(a)):
                raise ValueError('Invalid source view.')
            fov=2*math.atan(math.tan(original_fov*.5)*max(1.,aspect))
            if not 0 < fov < math.pi or r.GetLength()<.5:
                raise ValueError('Invalid source view.')
            distance=(target-eye).GetLength()
            fit.update(eye=xyz(eye),right=xyz(r),up=xyz(u),forward=xyz(f),near=max(1e-9,distance*.0001))
        except (KeyError,ValueError,TypeError,OverflowError):
            fov=math.radians(50.)
            source_camera=None
    camera=op[I.IMPORT_CAMERA] if automatic else None
    is_new=camera is None
    if is_new:
        camera=c4d.BaseObject(c4d.Ocamera)
        camera.SetName(op.GetName()+' - Import View')
    doc.StartUndo()
    try:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE,op)
        doc.AddUndo(c4d.UNDOTYPE_CHANGE,bd)
        if is_new:
            doc.InsertObject(camera)
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,camera)
        else:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE,camera)
        camera.SetMg(c4d.Matrix(*(c4d.Vector(*fit[k]) for k in ('eye','right','up','forward'))))
        camera[c4d.CAMERA_FOCUS]=36./(2.*math.tan(fov*.5))
        camera[c4d.CAMERAOBJECT_APERTURE]=2.*float(camera[c4d.CAMERA_FOCUS])*math.tan(fov*.5)
        camera[c4d.CAMERAOBJECT_NEAR_CLIPPING_ENABLE]=True
        camera[c4d.CAMERAOBJECT_NEAR_CLIPPING]=fit['near']
        camera[c4d.CAMERAOBJECT_FAR_CLIPPING_ENABLE]=False
        bd.SetSceneCamera(camera)
        op[I.CAMERA]=None
        op[I.IMPORT_CAMERA]=camera
        op[I.IMPORT_CAMERA_STATE]=camera_state(camera)
        report['framing']=(
            'AI source view fitted to output aspect.' if source_camera else
            'Frame fitted to '+report.get('frame_focus','overview')+'; orientation follows the current view.')
        op[I.SOURCE_INFO]=import_analysis.summary(report,scale)+'\n'+report['framing']
    finally:
        doc.EndUndo()
    c4d.EventAdd()
    return camera


def finish_import(op,key,report):
    marker=source_marker(key)
    message=import_analysis.summary(report,float(op[I.SCALE]))
    if report.get('framing'):
        message+='\n'+report['framing']
    if op[I.AUTO_FRAME] and not report.get('framing') and not automatic_available(op):
        message+='\nExisting scene/camera preserved. Use Frame Loaded Scan for a new overview.'
    if op[I.AUTO_FRAME_SOURCE]==marker and op[I.SOURCE_INFO]==message:
        return
    doc=op.GetDocument()
    doc.StartUndo()
    try:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE,op)
        op[I.AUTO_FRAME_SOURCE]=marker
        op[I.SOURCE_INFO]=message
    finally:
        doc.EndUndo()


def explicit_frame(op):
    from . import plugin
    instance=op.GetNodeData()
    if instance.job:
        raise ValueError('Wait for the scan or cancel processing before framing it.')
    report=getattr(instance,'source_analysis',None)
    if instance.cloud is None or instance.load_key!=instance.source_key(op):
        raise ValueError('Load the scan first, then use Frame Loaded Scan.')
    if not report:
        report=import_analysis.analyse(instance.cloud)
        instance.source_analysis=report
    frame_scan(op,report)
    instance.start_scan(explicit=True)
