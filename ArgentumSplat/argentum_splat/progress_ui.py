"""Non-modal, viewport-centred progress. All methods run on the UI thread."""
import time
import weakref
import c4d


def viewport_position(doc, width=450, height=170):
    try:
        frame = doc.GetActiveBaseDraw().GetFrameScreen()
        return (round((frame['cl'] + frame['cr'] - width) / 2),
                round((frame['ct'] + frame['cb'] - height) / 2))
    except (AttributeError, KeyError, ReferenceError, TypeError):
        return -2, -2


class ProgressBar(c4d.gui.GeUserArea):
    amount = None

    def GetMinSize(self):
        return 380, 12

    def DrawMsg(self, x1, y1, x2, y2, msg):
        self.OffScreenOn()
        self.SetClippingRegion(x1, y1, x2, y2)
        width, height = self.GetWidth(), self.GetHeight()
        self.DrawSetPen(c4d.Vector(.12))
        self.DrawRectangle(0, 0, width, height)
        self.DrawSetPen(c4d.Vector(.45, .42, .88))
        if self.amount is None:
            start = int((time.monotonic() % 1.5) / 1.5 * max(1, width - 80))
            self.DrawRectangle(start, 0, start + 80, height)
        else:
            end = round(width * max(0., min(1., self.amount)))
            if end:
                self.DrawRectangle(0, 0, end, height)


class JobDialog(c4d.gui.GeDialog):
    def __init__(self, owner):
        super().__init__()
        self.owner = weakref.ref(owner)
        self.bar = ProgressBar()
        self.started = time.monotonic()
        self.completing = False
        self.cancel_requested = False
        self.last_text = None

    def CreateLayout(self):
        self.SetTitle('Argentum Splat — Processing')
        self.GroupBegin(100, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)
        self.GroupBorderSpace(16, 12, 16, 12)
        self.AddStaticText(101, c4d.BFH_SCALEFIT, initw=410, name='Starting…')
        self.AddUserArea(102, c4d.BFH_SCALEFIT, initw=410, inith=12)
        self.AttachUserArea(self.bar, 102)
        self.AddStaticText(103, c4d.BFH_SCALEFIT, name='')
        self.AddButton(104, c4d.BFH_CENTER, initw=150, inith=24, name='Cancel')
        self.GroupEnd()
        return True

    def InitValues(self):
        self.SetTimer(200)
        self.refresh()
        return True

    def refresh(self):
        owner = self.owner()
        if owner is None:
            self.finish()
            return
        message = getattr(owner, 'progress_message', 'Starting…')
        if message != self.last_text:
            self.SetString(101, message)
            self.last_text = message
        self.bar.amount = getattr(owner, 'progress_amount', None)
        elapsed = int(time.monotonic() - self.started)
        percent = '%d%% · ' % round(100 * self.bar.amount) if self.bar.amount is not None else ''
        self.SetString(103, '%s%02d:%02d elapsed' % (percent, elapsed // 60, elapsed % 60))
        self.bar.Redraw()

    def Timer(self, msg):
        self.refresh()

    def request_cancel(self):
        owner = self.owner()
        if owner is not None and owner.job and not self.cancel_requested:
            from . import plugin, ids
            self.cancel_requested = True
            self.Enable(104, False)
            self.SetString(101, 'Cancelling…')
            plugin.PENDING.append((owner, ids.CANCEL))
            c4d.SpecialEventAdd(ids.MESSAGE_ID)

    def Command(self, identifier, msg):
        if identifier == 104:
            self.request_cancel()
        return True

    def AskClose(self):
        if not self.completing:
            self.request_cancel()
        return False

    def finish(self):
        self.completing = True
        self.SetTimer(0)
        self.Close()


def show(owner):
    close(owner)
    dialog = JobDialog(owner)
    owner.progress_dialog = dialog
    x, y = viewport_position(owner.op.GetDocument())
    if not dialog.Open(c4d.DLG_TYPE_ASYNC, xpos=x, ypos=y, defaultw=450, defaulth=170):
        owner.progress_dialog = None


def close(owner):
    dialog = getattr(owner, 'progress_dialog', None)
    if dialog is not None:
        dialog.finish()
        owner.progress_dialog = None
