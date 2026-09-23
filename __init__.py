import bpy

from .funcs import purge
from .funcs.properties import AUTO_PURGE_PG_scene
from .funcs.purge import ADDON_VERSION_TUPLE
from .UI.panel import AUTO_PURGE_PT_panel, AUTO_PURGE_OT_purge_now

bl_info = {
    "name": "Auto Purge",
    "author": "BlenderFace",
    "version": ADDON_VERSION_TUPLE,
    "blender": (4, 2, 0),
    "location": "Properties > Scene",
    "description": "Automatically and safely remove orphaned data blocks after objects are deleted",
    "warning": "",
    "category": "Utilities",
}

classes = (
    AUTO_PURGE_PG_scene,
    AUTO_PURGE_OT_purge_now,
    AUTO_PURGE_PT_panel,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    bpy.types.Scene.auto_purge = bpy.props.PointerProperty(type=AUTO_PURGE_PG_scene)
    purge.register()


def unregister():
    purge.unregister()
    if hasattr(bpy.types.Scene, "auto_purge"):
        del bpy.types.Scene.auto_purge
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()