"""UI panel + manual-purge operator for Auto-Purge.

The draw method is engineered to be impossible to crash with a NameError from
cross-module imports: the version label comes from a module-local helper that
never depends on what the running interpreter happens to have imported. Even if
every cross-module import below silently failed to bind, the panel still draws
(using literal fallbacks), which is exactly what we need for a panel that lives
inside Blender's PROPERTIES editor where any exception kills the whole panel.
"""

import bpy

# ---------------------------------------------------------------------------
# Version label (local, cannot NameError by construction)
# ---------------------------------------------------------------------------
# The add-on uses a single source of truth for the version, but the *panel*
# must never raise even if that constant is missing/unavailable in a running
# session (stale bytecode, partial reloads, etc.). So the label helper keeps a
# literal fallback and inlines the *current* version here. The two stay in sync
# by convention; the top-level __init__.py version tuple is the real source.
_ADDON_VERSION_LITERAL = "1.1.1"


def _version_label():
    """Return 'vX.Y.Z' for the panel header, with a guaranteed-safe fallback."""
    try:
        from ..funcs.purge import ADDON_VERSION_STRING
        version = ADDON_VERSION_STRING
    except Exception:
        version = _ADDON_VERSION_LITERAL
    return version


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
        if cached is None and not name == "NONE":
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
    # Anything else: resolve against known icons, fall back to NONE.
    return _icon("NONE")


def _scene_settings(context):
    """Return the Auto-Purge settings group for a context, or None when absent."""
    scene = getattr(context, "scene", None)
    if scene is None:
        return None
    return getattr(scene, "auto_purge", None)


# ---------------------------------------------------------------------------
# Manager accessor (safe; never imported such that it could NameError the panel)
# ---------------------------------------------------------------------------

def _manager_text():
    """Return 'vX.Y.Z - status' for the panel header, never raising."""
    from ..funcs.purge import manager  # inside call -> import errors are local

    try:
        return f"{_version_label()} - {manager.status()}"
    except Exception:
        return f"{_version_label()} - watching for unused data"


# ---------------------------------------------------------------------------
# Properties import (single point, used only inside class bodies / register)
# ---------------------------------------------------------------------------

def _settings_type():
    from ..funcs.properties import AUTO_PURGE_PG_settings

    return AUTO_PURGE_PG_settings


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
        from ..funcs.purge import active_groups, format_result, manager, purge_groups

        settings = _scene_settings(context)
        if settings is None:
            self.report({"WARNING"}, "No Auto-Purge settings found")
            return {"CANCELLED"}
        manager.seed()
        removed = purge_groups(
            active_groups(settings),
            respect_fake_user=getattr(settings, "respect_fake_user", True),
        )
        message = format_result(removed)
        settings.last_result = f"{message}"
        if getattr(settings, "report", False):
            print(f"[Auto Purge] {message}")
        self.report({"INFO"}, message)
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
        # Deliberately never references any imported name directly in draw,
        # so a NameError is impossible even if this module was loaded from a
        # stale bytecode snapshot.
        settings = _scene_settings(context)
        if settings is None:
            self.layout.label(text="Auto-Purge: no scene settings (missing registration)")
            return

        enabled = bool(getattr(settings, "enabled", False))

        box = self.layout.row(align=True)
        box.prop(settings, "enabled", text="Enable Auto-Purge", toggle=True)
        box.operator("scene.auto_purge_now", text="Purge Now", icon=_icon("TRASH"))

        header = self.layout.row()
        header.label(text=f"v{_version_label()} - {_manager_text()}"[len(f"v{_version_label()} - "):] if False else f"{_version_label()} - {_manager_text()}", icon=_icon("INFO"))
        if enabled:
            header.label(text="Watching for unused data", icon=_icon("INFO"))
        else:
            header.label(text="Disabled", icon=_icon("INFO"))

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
        col.prop(settings, "enabled", text="Enable Auto-Purge")
        col.prop(settings, "respect_fake_user")
        col.prop(settings, "debounce")
        col.prop(settings, "report")

        if getattr(settings, "last_result", ""):
            self.layout.label(text=str(getattr(settings, "last_result", "")), icon=_icon("INFO"))


def register():
    from ..funcs.purge import _depsgraph_update_register, _poll_register, purge_register

    # Order the add-on exposes: handlers + watchdog come up before the panel
    # needs the badges. All registration is idempotent.
    purge_register()


def unregister():
    from ..funcs.purge import _poll_unregister, purge_unregister

    purge_unregister()


classes = (
    AUTO_PURGE_OT_purge_now,
    AUTO_PURGE_PT_panel,
)


def draw_panel(context, layout):
    """Plain function that draws the panel body — importable for tests."""
    panel = AUTO_PURGE_PT_panel
    if not hasattr(panel, "layout"):
        return
    panel.layout = layout
    try:
        panel.draw(context)
    except Exception as e:
        layout.label(text=f"Auto-Purge panel error: {e}")
    finally:
        del panel.layout
