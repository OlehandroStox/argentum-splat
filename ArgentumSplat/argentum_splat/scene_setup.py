"""Safe initial framing. Existing scene cameras and hand-edited views win."""
import json
import math
from pathlib import Path
import c4d
from . import ids as I, import_analysis, loading


def xyz(vector):
    return vector.x,vector.y,vector.z


def source_marker(key):
    return json.dumps(key[:3]) if key else ''


def camera_state(cam):
    mg=cam.GetMg()
    state=[xyz(a) for a in (mg.off,mg.v1,mg.v2,mg.v3)] + [float(cam[k]) for k in
        (c4d.CAMERA_FOCUS,c4d.CAMERAOBJECT_APERTURE,c4d.CAMERA_PROJECTION,
         c4d.CAMERAOBJECT_NEAR_CLIPPING,c4d.CAMERAOBJECT_NEAR_CLIPPING_ENABLE,
         c4d.CAMERAOBJECT_FAR_CLIPPING,c4d.CAMERAOBJECT_FAR_CLIPPING_ENABLE)]
    # Omit defaults so untouched Import View cameras saved by earlier versions
    # keep their ownership marker. A manual film shift/parallel zoom must stop
    # subsequent automatic reframing just like a manual lens or pose edit.
    for name, default in (('CAMERAOBJECT_FILM_OFFSET_X',0.),
                          ('CAMERAOBJECT_FILM_OFFSET_Y',0.),('CAMERA_ZOOM',1.)):
        key=getattr(c4d,name,None)
        value=cam[key] if key is not None else None
        if value is not None and float(value) != default:
            state.append((name,float(value)))
    return json.dumps(loading.view_key(state))


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


def capture_near(near, scale, forward, right, up, aspect):
    """Conservative world-depth bound for the inferred source-origin view.

    Under shear, transverse source coordinates contribute to camera depth.
    Bound that contribution over both the analysis's 16:9 cone and the output
    cone. If either can cross the eye plane, use the minimum near distance.
    The axes include the complete object/parent transform, not import scale.
    """
    length=math.hypot(*forward)
    if not length or not math.isfinite(length):
        return 1e-9
    direction=tuple(v/length for v in forward)
    transverse=math.tan(math.radians(30.))*(
        max(16./9.,aspect)*abs(sum(a*b for a,b in zip(direction,right)))+
        abs(sum(a*b for a,b in zip(direction,up))))
    bound=length-transverse
    distance=near*abs(scale)*max(0.,bound)
    return max(1e-9,distance) if math.isfinite(distance) else 1e-9


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
    capture_view=False
    hint=report.get('capture_view',{})
    # Only normalized SOG has a known source convention here. Existing scene
    # cameras are protected by automatic_available; explicit AI metadata wins.
    if (not source_camera and hint.get('available') and
            Path(str(op[I.FILE] or '')).suffix.lower()=='.sog' and op[I.AUTO_SOG_ORIENTATION]):
        eye=point((0.,0.,0.))
        source_forward=c4d.Vector(*hint.get('forward',(0.,0.,1.)))
        if flip: source_forward.y=-source_forward.y
        source_up=c4d.Vector(0.,1. if flip else -1.,0.)
        world_forward=mg.MulV(source_forward)
        world_up=mg.MulV(source_up)
        world_right=mg.MulV(source_forward.Cross(source_up))
        f=world_forward.GetNormalized()
        r=world_up.Cross(f).GetNormalized()
        u=f.Cross(r).GetNormalized()
        fov=2.*math.atan(math.tan(math.radians(30.))*aspect)
        fit.update(eye=xyz(eye),right=xyz(r),up=xyz(u),forward=xyz(f),
                   near=capture_near(hint['near'],scale,xyz(world_forward),
                                     xyz(world_right),xyz(world_up),aspect))
        capture_view=True
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
            source_aspect = float(source_camera.get('width', 1))/float(source_camera.get('height', 1))
            if not math.isfinite(source_aspect) or source_aspect <= 0:
                raise ValueError('Invalid source camera aspect.')
            fov=2*math.atan(math.tan(original_fov*.5)*max(1.,aspect/source_aspect))
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
            'Source view fitted to output aspect.' if source_camera else
            'Automatic interior view: detailed coverage around the source origin.' if capture_view else
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
