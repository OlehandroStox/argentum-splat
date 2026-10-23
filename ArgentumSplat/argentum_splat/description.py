"""Static/live resource parity without touching saved parameter values."""
import c4d
from . import ids as I
from . import help_content

FINE_PARAMETERS = (I.HIGHLIGHT, I.SH_STRENGTH, I.EMISSION, I.DIFFUSE,
                   I.SUBSURFACE, I.GAMMA, I.CONTRAST, I.HUE, I.SATURATION,
                   I.LEVEL, I.SPLAT_SCALE, I.OPACITY, I.SCALE)


def describe(op, description, flags):
    if not description.LoadDescription(op.GetType()):
        return False, flags
    single = description.GetSingleDescID()
    entries = [(bc.GetClone(c4d.COPYFLAGS_NONE), did, parent) for bc, did, parent in description]
    existing = {did[0].id for _, did, _ in entries if did.GetDepth()}
    locale = help_content.language(op[I.HELP_LANGUAGE])
    labels = {I.IMAGE: 'Image / Video File',
              I.GENERATE: 'Generate from Image / Video',
              I.CANCEL: 'Cancel Processing', 2000: 'INPUT — IMAGE / VIDEO',
              I.HELP_LANGUAGE: 'Language / Язык',
              I.HELP_TOPIC: 'Тема' if locale else 'Topic',
              I.HELP_TEXT: 'Инструкция' if locale else 'Instructions'}
    for container, did, parent in entries:
        if not did.GetDepth():
            continue
        key = did[0].id
        changed = False
        if key in I.DEFAULTS:
            # Attribute Manager's Reset to Default must match object creation.
            # Description metadata does not assign values to saved objects.
            container[c4d.DESC_DEFAULT] = I.DEFAULTS[key]
            changed = True
        if key in FINE_PARAMETERS or key == I.MIN_OPACITY:
            container[c4d.DESC_STEP] = .001 if key == I.MIN_OPACITY else .1
            changed = True
        if key in labels:
            container[c4d.DESC_NAME] = labels[key]
            container[c4d.DESC_SHORT_NAME] = labels[key]
            changed = True
        if key == I.MAX_SPLATS:
            container[c4d.DESC_MIN] = 0
            container[c4d.DESC_MAX] = 100000000
            changed = True
        if key == I.IMPORT_QUALITY:
            container[c4d.DESC_DEFAULT] = 3
            changed = True
        if key in (I.HELP_TOPIC, I.HELP_LANGUAGE, I.INPUT_MODE):
            options = (help_content.TOPICS[locale] if key == I.HELP_TOPIC else
                       ('English', 'Русский') if key == I.HELP_LANGUAGE else
                       ('Auto (Image / Video)', 'Numbered Image Sequence'))
            cycle = c4d.BaseContainer()
            for index, label in enumerate(options):
                cycle.SetString(index, label)
            container[c4d.DESC_CYCLE] = cycle
            changed = True
        if key == I.PIXEL_VARIANCE:
            container[c4d.DESC_STEP] = .025
            changed = True
        if key == I.COLOR_MODE:
            cycle = c4d.BaseContainer()
            cycle.SetString(0, 'sRGB Source to Scene Linear')
            cycle.SetString(1, 'Treat Source as Linear')
            container[c4d.DESC_CYCLE] = cycle
            changed = True
        if changed:
            description.SetParameter(did, container, parent)
    controls = (
        (I.IMPORT_QUALITY, c4d.DTYPE_LONG, 2001, 'Import Quality', 4),
        (I.IMPORT_PLAN, c4d.DTYPE_STRING, 2001, 'Import Budget', 0),
        (I.ASK_LARGE_IMPORT, c4d.DTYPE_BOOL, 2001, 'Ask for Large Files', 0),
        (I.AUTO_SOG_ORIENTATION, c4d.DTYPE_BOOL, 2005, 'Auto SOG Orientation (Y-down to Y-up)', 0),
        (I.AUTO_FRAME, c4d.DTYPE_BOOL, 2001, 'Auto Frame in Empty Scene', 0),
        (I.FRAME_SCAN, c4d.DTYPE_BUTTON, I.SCAN_TOOLS_GROUP, 'Frame Loaded Scan', 0),
        (I.SOURCE_INFO, c4d.DTYPE_STRING, 2006, 'Source Summary', 0),
        (I.AUTO_REDSHIFT, c4d.DTYPE_BOOL, 2001, 'Auto Prepare Redshift on Import', 0),
        (I.PIXEL_VARIANCE, c4d.DTYPE_REAL, 2005, 'Pixel Footprint (variance; 0 = Off)', 2),
        (I.ALPHA_EROSION, c4d.DTYPE_LONG, 2000, 'Alpha Erosion (0 = Keep Fine Edges)', 8),
        (I.DETAIL_PRESET, c4d.DTYPE_BUTTON, I.SCAN_TOOLS_GROUP, 'Source Fidelity - Preserve Detail', 0),
        (I.PREPARE_REDSHIFT, c4d.DTYPE_BUTTON, I.SCAN_TOOLS_GROUP, 'Set Redshift Detail Quality', 0),
        (I.SOURCE_CAMERA, c4d.DTYPE_BUTTON, I.SCAN_TOOLS_GROUP, 'Create Estimated Source Camera', 0),
        (I.INPUT_MODE, c4d.DTYPE_LONG, 2000, 'Input Mode', 1),
        (I.SOURCE_FRAME, c4d.DTYPE_LONG, 2000, 'Source Frame / Sequence Offset (0 = First)', 99999),
        (I.PREVIEW_SOURCE, c4d.DTYPE_BUTTON, 2000, 'Preview Selected Frame', 0),
        (I.SUPPORT_AUTHOR, c4d.DTYPE_BUTTON, 2006, 'Support the author - Boosty', 0),
    )
    for key, datatype, group, label, maximum in controls:
        did = c4d.DescID(c4d.DescLevel(key, datatype, 0))
        if key in existing or (single is not None and single.GetDepth() and not did.IsPartOf(single)[0]):
            continue
        container = c4d.GetCustomDataTypeDefault(datatype)
        container[c4d.DESC_NAME] = container[c4d.DESC_SHORT_NAME] = label
        container[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_OFF
        if datatype in (c4d.DTYPE_LONG, c4d.DTYPE_REAL):
            container[c4d.DESC_MIN] = 0
            container[c4d.DESC_MAX] = maximum
            container[c4d.DESC_STEP] = .025 if key == I.PIXEL_VARIANCE else .1 if datatype == c4d.DTYPE_REAL else 1
            container[c4d.DESC_DEFAULT] = I.DEFAULTS.get(key, 0)
        elif datatype == c4d.DTYPE_BOOL:
            container[c4d.DESC_DEFAULT] = I.DEFAULTS[key]
        elif datatype == c4d.DTYPE_STRING:
            container[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_STRINGMULTI
            container[c4d.DESC_EDITABLE] = False
        else:
            container[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_BUTTON
        if key == I.INPUT_MODE:
            cycle = c4d.BaseContainer()
            cycle.SetString(0, 'Auto (Image / Video)')
            cycle.SetString(1, 'Numbered Image Sequence')
            container[c4d.DESC_CYCLE] = cycle
        if key == I.IMPORT_QUALITY:
            from . import import_budget
            cycle = c4d.BaseContainer()
            for value, label in import_budget.LABELS.items():
                cycle.SetString(value, label)
            container[c4d.DESC_CYCLE] = cycle
            container[c4d.DESC_DEFAULT] = 3
        if not description.SetParameter(did, container, c4d.DescID(c4d.DescLevel(group, c4d.DTYPE_GROUP, 0))):
            return False, flags
    return True, flags | c4d.DESCFLAGS_DESC_LOADED
