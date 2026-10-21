import os
import sys
import traceback
import c4d

PLUGIN_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if PLUGIN_DIRECTORY not in sys.path:
    sys.path.insert(0, PLUGIN_DIRECTORY)

from argentum_splat import plugin
from argentum_splat import ids as I


class ArgentumObject(plugin.SplatObject):
    pass


class ArgentumCommand(plugin.CreateSplat):
    pass


class ArgentumJobs(plugin.Coordinator):
    pass


def PluginMessage(message_id, data):
    if message_id in (c4d.C4DPL_ENDPROGRAM,
                      getattr(c4d,"C4DPL_RELOADPYTHONPLUGINS",-1)):
        plugin.shutdown()
        return True
    return False


if __name__ == "__main__":
    # The registration calls must live in the .pyp entrypoint. C4D resolves the
    # owning plugin from this execution context, not an imported .py module.
    try:
        # During C4D's native Python reload the old IDs are still discoverable.
        # Register* handles that reload context and rejects real ID collisions.
        plugin.RESOURCE = c4d.plugins.GeResource()
        if not plugin.RESOURCE.Init(PLUGIN_DIRECTORY):
            raise RuntimeError("Cannot initialise plugin resources.")
        icon = c4d.bitmaps.BaseBitmap()
        icon_result, _ = icon.InitWith(os.path.join(PLUGIN_DIRECTORY, "res", "argentum_splat.png"))
        if icon_result != c4d.IMAGERESULT_OK:
            raise RuntimeError("Cannot load Argentum Splat icon.")
        result = c4d.plugins.RegisterObjectPlugin(id=I.OBJECT_ID,
            str="Argentum Splat",g=ArgentumObject,description="oargentumsplat",
            info=c4d.OBJECT_GENERATOR|c4d.OBJECT_CALL_ADDEXECUTION,icon=icon)
        result = c4d.plugins.RegisterCommandPlugin(id=I.COMMAND_ID,
            str="Argentum Splat - Image to 3D",info=c4d.PLUGINFLAG_HIDEPLUGINMENU,icon=icon,
            help="Create an image-to-Gaussian object",dat=ArgentumCommand()) and result
        result = c4d.plugins.RegisterMessagePlugin(id=I.MESSAGE_ID,
            str="Argentum Splat Jobs",info=0,dat=ArgentumJobs()) and result
        plugin.REGISTERED = bool(result)
        if not result:
            raise RuntimeError("One or more plugin registrations failed.")
    except Exception:
        error = traceback.format_exc()
        print(error)
        try:
            with open(os.path.join(PLUGIN_DIRECTORY,"startup_error.log"),"w",encoding="utf8") as handle:
                handle.write(error)
        except OSError:
            pass
