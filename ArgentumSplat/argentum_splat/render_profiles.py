"""Owned render presets: preserve the user's original settings and effects."""
import c4d
from . import ids as I

MARKER = 'ArgentumSplat.Transparency.v1'


def target(doc, original):
    """Called inside the caller's undo block. Never match a user preset by name."""
    if original.GetDataInstance().GetString(I.OBJECT_ID) == MARKER:
        return original
    result = original.GetClone(c4d.COPYFLAGS_NONE)
    if result is None:
        raise MemoryError('Cannot copy render settings.')
    result.SetName('Argentum Splat - Splatting Transparency')
    result.GetDataInstance().SetString(I.OBJECT_ID, MARKER)
    doc.AddUndo(c4d.UNDOTYPE_CHANGE, doc)
    doc.InsertRenderData(result, pred=original)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, result)
    doc.SetActiveRenderData(result)
    return result
