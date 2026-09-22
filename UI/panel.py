import bpy

from ..funcs.purge import active_groups, format_result, manager, purge_groups


def _icon(name):
    """Return a valid icon enum, falling back to 'NONE' on any Blender build."""
    if name in getattr(_icon, "_known", ()):
        return name
    _icon._known = frozenset(
        bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items.keys()
    )
    return name if name in _icon._known else 'NONE'


class AUTO_PURGE_OT_purge_now(bpy.types.Operator):
    """Manually remove orphaned data blocks using the current scope settings."""
    bl_idname = "scene.auto_purge_now"
    bl_label = "Purge Now"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        settings = context.scene.auto_purge
        manager.seed()
        removed = purge_groups(
            active_groups(settings),
            respect_fake_user=settings.respect_fake_user,
        )
        result = format_result(removed)
        settings.last_result = f"{self.bl_label} - {result}"
        self.report({'INFO'}, result)
        return {'FINISHED'}


class AUTO_PURGE_PT_panel(bpy.types.Panel):
    """Panel for Auto-Purge in the Scene Properties tab."""
    bl_label = "Auto-Purge Unused Data"
    bl_idname = "AUTO_PURGE_PT_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.auto_purge

        layout.prop(settings, "enabled", toggle=True)
        layout.label(
            text=f"v{ADDON_VERSION_STRING} - {manager.status()}",
            icon=_icon('INFO') if settings.enabled else 'NONE',
        )
        if settings.enabled:
            layout.label(text=f"Active - {manager.status()}", icon=_icon('INFO'))

        box = layout.box()
        box.label(text="Scope", icon=_icon('FILTER'))
        col = box.column(align=True)
        col.prop(settings, "purge_objects", toggle=True)
        col.prop(settings, "purge_geometry", toggle=True)
        col.prop(settings, "purge_materials", toggle=True)
        col.prop(settings, "purge_textures", toggle=True)
        col.prop(settings, "purge_images", toggle=True)
        col.prop(settings, "purge_misc", toggle=True)

        box = layout.box()
        box.label(text="Safety", icon=_icon('FAKE_USER_ON'))
        box.prop(settings, "respect_fake_user")
        box.prop(settings, "debounce")
        box.prop(settings, "report")

        if settings.last_result:
            layout.label(text=settings.last_result, icon=_icon('INFO'))

        layout.separator()
        layout.operator("scene.auto_purge_now", icon=_icon('TRASH'))