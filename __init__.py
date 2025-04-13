import bpy
def auto_purge_unused_data():
    """ Purge all unused data in the Blender file. """
    for _ in range(5):  # Run multiple times to ensure deep purge
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

def on_object_deleted(scene, depsgraph):
    """ Automatically purge unused data when an object is deleted, if enabled. """
    if scene.auto_purge_enabled:
        auto_purge_unused_data()

class SCENE_PT_AutoPurgePanel(bpy.types.Panel):
    """ UI Panel for Auto-Purge in the Scene Properties tab. """
    bl_label = "Auto-Purge Unused Data"
    bl_idname = "SCENE_PT_auto_purge"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        layout.prop(scene, "auto_purge_enabled", toggle=True)
        layout.operator("scene.manual_purge_unused_data", icon='TRASH')

class SCENE_OT_ManualPurge(bpy.types.Operator):
    """ Manual button to purge unused data. """
    bl_idname = "scene.manual_purge_unused_data"
    bl_label = "Purge Now"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        auto_purge_unused_data()
        self.report({'INFO'}, "Purged all unused data!")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(SCENE_PT_AutoPurgePanel)
    bpy.utils.register_class(SCENE_OT_ManualPurge)
    bpy.types.Scene.auto_purge_enabled = bpy.props.BoolProperty(
        name="Auto-Purge",
        description="Automatically purge unused data when objects are deleted",
        default=False
    )
    bpy.app.handlers.depsgraph_update_post.append(on_object_deleted)

def unregister():
    bpy.utils.unregister_class(SCENE_PT_AutoPurgePanel)
    bpy.utils.unregister_class(SCENE_OT_ManualPurge)
    del bpy.types.Scene.auto_purge_enabled
    bpy.app.handlers.depsgraph_update_post.remove(on_object_deleted)

if __name__ == "__main__":
    register()