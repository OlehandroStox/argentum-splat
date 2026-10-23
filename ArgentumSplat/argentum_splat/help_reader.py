"""A resizable offline reader for narrow Attribute Manager layouts."""
import webbrowser
import c4d
from . import __version__, help_content, ids as I

LANGUAGE, TOPIC, TEXT, SUPPORT, VERSION = 101, 102, 103, 104, 105
_dialog = None


class HelpReader(c4d.gui.GeDialog):
    def __init__(self, language=0, topic=0):
        super().__init__()
        self.language = help_content.language(language)
        self.topic = max(0, min(9, int(topic or 0)))

    def CreateLayout(self):
        self.SetTitle('Argentum Splat — Help')
        self.GroupBegin(100, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1)
        self.GroupBorderSpace(12, 12, 12, 12)
        self.GroupBegin(110, c4d.BFH_SCALEFIT, cols=2)
        self.AddComboBox(LANGUAGE, c4d.BFH_LEFT, initw=150)
        self.AddChild(LANGUAGE, 0, 'English')
        self.AddChild(LANGUAGE, 1, 'Русский')
        self.AddComboBox(TOPIC, c4d.BFH_SCALEFIT, initw=250)
        self.GroupEnd()
        self.AddMultiLineEditText(TEXT, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                                 initw=420, inith=360,
                                 style=c4d.DR_MULTILINE_READONLY | c4d.DR_MULTILINE_WORDWRAP)
        self.GroupBegin(111, c4d.BFH_SCALEFIT, cols=2)
        self.AddStaticText(VERSION, c4d.BFH_SCALEFIT, name='Argentum Splat ' + __version__)
        self.AddButton(SUPPORT, c4d.BFH_RIGHT, name='Support the Author - Boosty')
        self.GroupEnd()
        self.GroupEnd()
        return True

    def InitValues(self):
        self.SetInt32(LANGUAGE, self.language)
        self.refresh_topics()
        return True

    def refresh_topics(self):
        self.FreeChildren(TOPIC)
        for index, title in enumerate(help_content.TOPICS[self.language]):
            self.AddChild(TOPIC, index, title)
        self.SetInt32(TOPIC, self.topic)
        self.SetString(TEXT, help_content.text(self.language, self.topic))

    def Command(self, control, message):
        if control == LANGUAGE:
            self.language = help_content.language(self.GetInt32(LANGUAGE))
            self.refresh_topics()
        elif control == TOPIC:
            self.topic = self.GetInt32(TOPIC)
            self.SetString(TEXT, help_content.text(self.language, self.topic))
        elif control == SUPPORT:
            url = 'https://boosty.to/olehandrostox/donate'
            try:
                opened = webbrowser.open_new_tab(url)
            except Exception:
                opened = False
            if not opened:
                print('Argentum Splat: Support the author at ' + url)
        return True


def show(op):
    global _dialog
    if _dialog is not None:
        _dialog.Close()
    _dialog = HelpReader(op[I.HELP_LANGUAGE], op[I.HELP_TOPIC])
    return _dialog.Open(c4d.DLG_TYPE_ASYNC, defaultw=760, defaulth=660)
