import bpy

from .funcs import purge
from .funcs.properties import AUTO_PURGE_PG_history_entry, AUTO_PURGE_PG_scene
from .UI.panel import (
    AUTO_PURGE_PT_panel,
    AUTO_PURGE_PT_scope,
    AUTO_PURGE_PT_security,
    AUTO_PURGE_PT_progress,
    AUTO_PURGE_OT_purge_now,
)

# Version and packaging info live in blender_manifest.toml (single source of
# truth for the extension platform).

classes = (
    AUTO_PURGE_PG_history_entry,
    AUTO_PURGE_PG_scene,
    AUTO_PURGE_OT_purge_now,
    AUTO_PURGE_PT_panel,
    AUTO_PURGE_PT_scope,
    AUTO_PURGE_PT_security,
    AUTO_PURGE_PT_progress,
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