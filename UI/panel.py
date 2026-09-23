"""UI panel + manual-purge operator for Auto-Purge.

The draw method is engineered to be impossible to crash with a NameError from
cross-module imports: the manager status comes from a module-local helper that
imports lazily and falls back gracefully, so even if a cross-module import
failed the panel would still draw. Anything that raises inside Blender's
PROPERTIES editor kills the whole panel, so draw() is kept deliberately
defensive.

Layout: the parent panel always shows the Enable toggle and "Purge Now"
button, with the scope, security, and history sections as foldable
sub-panels underneath.
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


def _status_text():
    """Return the watchdog status for the history section, never raising."""
    from ..funcs.purge import manager  # inside call -> import errors are local

    try:
        return manager.status()
    except Exception:
        return "Watching for unused data"


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


class AUTO_PURGE_PT_scope(bpy.types.Panel):
    """Scope section: the data categories Auto-Purge may remove."""

    bl_label = "What to Remove"
    bl_idname = "AUTO_PURGE_PT_scope"
    bl_parent_id = "AUTO_PURGE_PT_panel"
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
            return
        col = self.layout.column(align=True)
        col.prop(settings, "purge_objects", text="Objects")
        col.prop(settings, "purge_geometry", text="Geometry (mesh/curve/etc.)")
        col.prop(settings, "purge_materials", text="Materials")
        col.prop(settings, "purge_textures", text="Textures")
        col.prop(settings, "purge_images", text="Images")
        col.prop(settings, "purge_misc", text="Misc")


class AUTO_PURGE_PT_security(bpy.types.Panel):
    """Security section: guards that keep purging safe."""

    bl_label = "Security"
    bl_idname = "AUTO_PURGE_PT_security"
    bl_parent_id = "AUTO_PURGE_PT_panel"
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
            return
        col = self.layout.column(align=True)
        col.prop(settings, "respect_fake_user")
        col.prop(settings, "debounce")
        col.prop(settings, "report")


class AUTO_PURGE_PT_progress(bpy.types.Panel):
    """Progress section: live watchdog status and the purge history log."""

    bl_label = "Progress & History"
    bl_idname = "AUTO_PURGE_PT_progress"
    bl_parent_id = "AUTO_PURGE_PT_panel"
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
            return
        col = self.layout.column(align=True)
        col.label(text=_status_text(), icon=_icon("INFO"))
        history = getattr(settings, "history", None)
        if history is None or not len(history):
            col.label(text="No purges yet", icon=_icon("INFO"))
            return
        for entry in history:
            text = str(entry.text)
            col.label(text=f"{entry.time} - {text}")


classes = (
    AUTO_PURGE_OT_purge_now,
    AUTO_PURGE_PT_panel,
    AUTO_PURGE_PT_scope,
    AUTO_PURGE_PT_security,
    AUTO_PURGE_PT_progress,
)
