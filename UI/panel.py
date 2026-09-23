"""UI panel + manual-purge operator for Auto-Purge.

The draw method is engineered to be impossible to crash with a NameError from
cross-module imports: the version label and manager status come from module-local
helpers that import lazily and fall back gracefully, so even if a cross-module
import failed the panel would still draw. Anything that raises inside Blender's
PROPERTIES editor kills the whole panel, so draw() is kept deliberately defensive.
"""

import bpy


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------

_KNOWN_ICON_FALLBACK = "NONE"
_ICON_CACHE = {}


def _icon(name):
    """Return an icon enum name that is guaranteed valid on this Blender.

    Blender throws on unknown icon enums, and valid icon lists differ across
    versions (e.g. 'FAKE_USER_ON' is 2.8+; older panel icons were removed in
    4.x). We resolve lazily against the actual ``enum_items`` of the running
    build on first use and cache the result.
    """
    if name in ("NONE", "INFO", "TRASH", "FILTER", "FAKE_USER_ON"):
        cached = _ICON_CACHE.get(name)
        if cached is None and name != "NONE":
            try:
                items = bpy.types.UILayout.bl_rna.functions[
                    "label"
                ].parameters["icon"].enum_items.keys()
                _ICON_CACHE["_all"] = frozenset(items)
            except Exception:
                _ICON_CACHE["_all"] = frozenset()
            cached = name if name in _ICON_CACHE["_all"] else _KNOWN_ICON_FALLBACK
            _ICON_CACHE[name] = cached
        return cached if cached is not None else name
    return _KNOWN_ICON_FALLBACK


# ---------------------------------------------------------------------------
# Lazy, never-raising accessors
# ---------------------------------------------------------------------------


def _scene_settings(context):
    """Return the Auto-Purge settings group for a context, or None when absent."""
    scene = getattr(context, "scene", None)
    if scene is None:
        return None
    return getattr(scene, "auto_purge", None)


def _version_label():
    """Return the add-on version string, preferring the module source of truth."""
    try:
        from ..funcs.purge import ADDON_VERSION_STRING

        return ADDON_VERSION_STRING
    except Exception:
        return "0.0.0"


def _manager_text():
    """Return 'vX.Y.Z - status' for the panel header, never raising."""
    from ..funcs.purge import manager  # inside call -> import errors are local

    try:
        return f"v{_version_label()} - {manager.status()}"
    except Exception:
        return f"v{_version_label()} - watching for unused data"


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


class AUTO_PURGE_OT_purge_now(bpy.types.Operator):
    """Run a purge immediately with the current scope settings."""

    bl_idname = "scene.auto_purge_now"
    bl_label = "Purge Now"
    bl_description = "Remove unused data blocks right now, respecting scope + fake user"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from ..funcs.purge import format_result, manager, record_result, run_purge

        settings = _scene_settings(context)
        if settings is None:
            self.report({"WARNING"}, "No Auto-Purge settings found")
            return {"CANCELLED"}
        manager.seed()
        removed = run_purge(settings)
        record_result(settings, removed)
        self.report({"INFO"}, format_result(removed))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


class AUTO_PURGE_PT_panel(bpy.types.Panel):
    """Auto-Purge controls in the Scene properties."""

    bl_label = "Auto-Purge Unused Data"
    bl_idname = "AUTO_PURGE_PT_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _scene_settings(context) is not None

    def draw(self, context):
        settings = _scene_settings(context)
        if settings is None:
            self.layout.label(text="Auto-Purge: no scene settings (missing registration)")
            return

        row = self.layout.row(align=True)
        row.prop(settings, "enabled", text="Enable Auto-Purge", toggle=True)
        row.operator("scene.auto_purge_now", text="Purge Now", icon=_icon("TRASH"))

        self.layout.label(text=_manager_text(), icon=_icon("INFO"))

        box = self.layout.box()
        col = box.column(align=True)
        col.prop(settings, "purge_objects", text="Objects")
        col.prop(settings, "purge_geometry", text="Geometry (mesh/curve/etc.)")
        col.prop(settings, "purge_materials", text="Materials")
        col.prop(settings, "purge_textures", text="Textures")
        col.prop(settings, "purge_images", text="Images")
        col.prop(settings, "purge_misc", text="Misc")

        box = self.layout.box()
        box.label(text="Safety", icon=_icon("FAKE_USER_ON"))
        col = box.column(align=True)
        col.prop(settings, "respect_fake_user")
        col.prop(settings, "debounce")
        col.prop(settings, "report")

        if getattr(settings, "last_result", ""):
            self.layout.label(text=str(settings.last_result), icon=_icon("INFO"))


classes = (
    AUTO_PURGE_OT_purge_now,
    AUTO_PURGE_PT_panel,
)
