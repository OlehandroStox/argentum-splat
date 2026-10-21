"""Optional native Fracture setup for independently transforming splat cards."""
import c4d
from . import ids as I


def create_rig(op):
    doc = op.GetDocument()
    if doc is None or op.GetType() != I.OBJECT_ID:
        raise ValueError("Select an Argentum Splat object in an open document.")
    parent = op.GetUp()
    if parent and parent.CheckType(c4d.Omgfracture):
        c4d.StopAllThreads()
        doc.StartUndo()
        try:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, parent)
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
            parent[c4d.MGFRACTUREOBJECT_MODE] = c4d.MGFRACTUREOBJECT_MODE_EXPLODE
            op[I.POINT_PREVIEW] = False
            op[I.STATUS] = "MoGraph rig ready. Add native effectors to the parent Fracture object."
            parent.SetDirty(c4d.DIRTYFLAGS_DATA)
            op.SetDirty(c4d.DIRTYFLAGS_DATA)
            doc.SetActiveObject(parent,c4d.SELECTION_NEW)
        finally:
            doc.EndUndo()
        c4d.EventAdd()
        return parent
    c4d.StopAllThreads()
    doc.StartUndo()
    try:
        local = op.GetMl()
        rig = c4d.BaseObject(c4d.Omgfracture)
        rig.SetName(op.GetName()+" - MoGraph")
        rig[c4d.MGFRACTUREOBJECT_MODE] = c4d.MGFRACTUREOBJECT_MODE_EXPLODE
        doc.InsertObject(rig,parent,op)
        # Keep the inserted parent neutral. Existing PSR tracks then retain
        # their original local coordinate system on every evaluated frame.
        rig.SetMl(c4d.Matrix())
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,rig)
        # Record the move after the new parent, so Undo moves the source out
        # before deleting its parent. Generic CHANGE snapshots duplicate it.
        doc.AddUndo(c4d.UNDOTYPE_HIERARCHY_PSR,op)
        op.Remove()
        op.InsertUnder(rig)
        op.SetMl(local)
        # The native Fracture generator needs the polygon cache in the editor.
        doc.AddUndo(c4d.UNDOTYPE_CHANGE_SMALL,op)
        op[I.POINT_PREVIEW] = False
        op[I.STATUS] = "MoGraph rig created. Add native effectors to the parent Fracture object."
        op.SetDirty(c4d.DIRTYFLAGS_DATA)
        doc.SetActiveObject(rig,c4d.SELECTION_NEW)
    finally:
        doc.EndUndo()
    c4d.EventAdd()
    return rig
