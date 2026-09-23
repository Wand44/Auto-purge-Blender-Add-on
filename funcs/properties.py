import bpy


class AUTO_PURGE_PG_history_entry(bpy.types.PropertyGroup):
    """One line in the purge history log."""

    time: bpy.props.StringProperty(
        name="Time",
        default="",
    )
    text: bpy.props.StringProperty(
        name="Text",
        default="",
    )


class AUTO_PURGE_PG_scene(bpy.types.PropertyGroup):
    """Per-scene settings for the Auto-Purge add-on."""

    enabled: bpy.props.BoolProperty(
        name="Auto-Purge",
        description="Automatically remove orphaned data blocks after objects are deleted. "
                    "Purging is debounced and runs safely outside of Blender's dependency graph update",
        default=False,
    )
    purge_objects: bpy.props.BoolProperty(
        name="Objects",
        description="Remove orphaned (unused) objects",
        default=True,
    )
    purge_geometry: bpy.props.BoolProperty(
        name="Geometry",
        description="Remove orphaned meshes, curves, lattices, armatures, volumes and related geometry",
        default=True,
    )
    purge_materials: bpy.props.BoolProperty(
        name="Materials",
        description="Remove orphaned materials and node groups",
        default=True,
    )
    purge_textures: bpy.props.BoolProperty(
        name="Textures",
        description="Remove orphaned legacy textures",
        default=True,
    )
    purge_images: bpy.props.BoolProperty(
        name="Images",
        description="Remove orphaned images",
        default=True,
    )
    purge_misc: bpy.props.BoolProperty(
        name="Misc",
        description="Remove orphaned worlds, collections, lights, cameras, actions and other data",
        default=False,
    )
    respect_fake_user: bpy.props.BoolProperty(
        name="Respect Fake User",
        description="Never remove data blocks that have Fake User enabled (the shield icon). "
                    "Blender's own protection mechanism for data you want to keep",
        default=True,
    )
    debounce: bpy.props.FloatProperty(
        name="Delay",
        description="How long to wait (in seconds) after a deletion before purging. "
                    "Higher values give Blender time to settle and coalesce bursts of deletions",
        default=0.5,
        min=0.0,
        max=5.0,
        subtype='TIME',
        precision=2,
    )
    report: bpy.props.BoolProperty(
        name="Report",
        description="Print a summary of removed data blocks to the status bar / console",
        default=True,
    )
    history: bpy.props.CollectionProperty(
        name="History",
        description="Chronological log of recent purge runs",
        type=AUTO_PURGE_PG_history_entry,
    )
