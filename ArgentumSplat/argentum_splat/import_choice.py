"""Non-modal large-source choice before conversion or geometry allocation."""
import json
import weakref
import c4d
from . import ids as I, import_budget as budget, loading
from .progress_ui import viewport_position


def marker(key):
    return json.dumps(key[:3], ensure_ascii=True)


class ImportDialog(c4d.gui.GeDialog):
    def __init__(self, owner, request, count_path):
        super().__init__()
        self.owner = weakref.ref(owner)
        self.request = request
        self.count_path = count_path
        self.finished = False

    def CreateLayout(self):
        self.SetTitle('Argentum Splat — Import Quality')
        self.GroupBegin(100, c4d.BFH_SCALEFIT, 1, 0)
        self.GroupBorderSpace(16, 12, 16, 12)
        self.AddStaticText(101, c4d.BFH_SCALEFIT, name='Large scan: choose how much detail to load')
        self.AddComboBox(102, c4d.BFH_SCALEFIT, initw=480)
        for key, label in budget.LABELS.items():
            self.AddChild(102, key, label)
        for key in (103, 104, 105):
            self.AddStaticText(key, c4d.BFH_SCALEFIT, initw=480, name='')
        self.AddCheckbox(106, c4d.BFH_LEFT, 0, 0, name='Ask for new large files on this object')
        self.GroupBegin(110, c4d.BFH_CENTER, 2, 0)
        self.AddButton(107, c4d.BFH_CENTER, initw=150, name='Load')
        self.AddButton(108, c4d.BFH_CENTER, initw=150, name='Cancel')
        self.GroupEnd()
        self.GroupEnd()
        return True

    def InitValues(self):
        self.SetInt32(102, budget.preset_for(self.request['source_key'][3]))
        self.SetBool(106, True)
        self.refresh()
        self.SetTimer(500)
        return True

    def refresh(self):
        key = self.request['source_key']
        limit = budget.PRESETS.get(self.GetInt32(102), key[3])
        lines = budget.plan(self.count_path, limit).splitlines()
        self.SetString(103, lines[0])
        self.SetString(104, lines[1] if len(lines) > 1 else '')
        free = budget.available_memory()
        self.SetString(105, 'Free RAM: {:.1f} GiB. MAX has no count reduction.'.format(free/2**30)
                       if free is not None else 'MAX keeps all splats after the opacity filter.')

    def Timer(self, msg):
        owner = self.owner()
        from .scene_jobs import plugin_document_open
        if owner is None or not plugin_document_open(owner.op):
            self.finish()
        else:
            try:
                key = owner.source_key(owner.op)
                if key is None or marker(key) != marker(self.request['source_key']):
                    self.finish()  # source changed while the choice was open
            except (OSError, ReferenceError):
                self.finish()

    def finish(self):
        self.finished = True
        self.SetTimer(0)
        self.Close()
        owner = self.owner()
        if owner is not None:
            owner.import_dialog = None

    def cancel(self):
        owner = self.owner()
        if owner is not None:
            request = owner.request_snapshot()
            owner.blocked_request = request['key']
            owner.cancelled_non_view = loading.non_view_key(request)
            owner.queued_request = None
            owner.set_progress('Import cancelled. Previous complete model preserved.', None)
        self.finish()

    def AskClose(self):
        if not self.finished:
            self.cancel()
        return False

    def Command(self, identifier, msg):
        if identifier == 102:
            self.refresh()
        elif identifier == 108:
            self.cancel()
        elif identifier == 107:
            owner = self.owner()
            if owner is None:
                self.finish()
                return True
            op = owner.op
            selected = self.GetInt32(102)
            doc = op.GetDocument()
            doc.StartUndo()
            try:
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
                op[I.MAX_SPLATS] = budget.PRESETS.get(selected, self.request['source_key'][3])
                op[I.ASK_LARGE_IMPORT] = self.GetBool(106)
                op[I.IMPORT_APPROVED] = marker(self.request['source_key'])
            finally:
                doc.EndUndo()
            self.finish()
            try:
                owner.start_scan(explicit=True)
            except Exception as error:
                owner.report_failure(error)
            c4d.EventAdd()
        return True


def offer(owner, request):
    if getattr(owner, 'import_dialog', None) is not None:
        return True
    op, key = owner.op, request['source_key']
    if (not op[I.ASK_LARGE_IMPORT] or op[I.IMPORT_APPROVED] == marker(key)
            or owner.load_key == key):
        return False
    count_path = key[0]
    count = budget.source_count(count_path)
    if count is None:
        # Some converter inputs expose no simple header count. Once converted,
        # still offer the choice before allocating the large native geometry.
        from . import assets
        cached = assets.resolve_path(op, op[I.CACHE_FILE])
        if cached and assets.cache_source_matches(key[0], op[I.CACHE_SOURCE]):
            count_path = cached
            count = budget.source_count(count_path)
    if count is None or count <= budget.LARGE_SOURCE:
        return False
    dialog = ImportDialog(owner, request, count_path)
    owner.import_dialog = dialog
    x, y = viewport_position(op.GetDocument(), 540, 250)
    if not dialog.Open(c4d.DLG_TYPE_ASYNC, xpos=x, ypos=y, defaultw=540, defaulth=250):
        owner.import_dialog = None
        raise RuntimeError('Cannot open import quality window. Choose Import Quality and disable Ask for Large Files to proceed.')
    owner.set_progress('Waiting for Import Quality selection — no heavy scan calculation has started.', None)
    return True
