This add-on for Blender automatically removes orphaned (unused) data blocks after you delete objects, and adds a safe one-click purge for everything else, so your .blend files stay lean without you having to think about it. Follow the steps below to get started.

## Installation

    Download the Add-On:
        Obtain the add-on ZIP file from the official source.
    Install as an Extension (Blender 4.2 and newer):
        Open Blender.
        Go to Edit > Preferences.
        In the Preferences window, select Get Extensions from the left-hand menu.
        Click on Install from Disk at the top right.
        Locate and select the downloaded ZIP file, then click Install From Disk.
    Install as a classic add-on:
        Open Blender.
        Go to Edit > Preferences.
        In the Preferences window, select Add-ons from the left-hand menu.
        Click on Install... at the top right.
        Locate and select the downloaded ZIP file, then click Install Add-on.
    Enable the Add-On:
        Once installed, find the add-on in the list (you can search by name).
        Check the box next to the add-on to enable it.
    Save Preferences:
        Click on Save Preferences to keep the add-on enabled for future sessions.

Note: Auto Purge requires Blender 4.2 or newer.

## Getting Started

    Open the Panel:
        Go to the Scene Properties tab (the tab with the world/globe icon) and look for the Auto-Purge Unused Data panel.
    Enable Auto-Purge:
        Tick the Auto-Purge switch at the top of the panel. This turns the automated behaviour on. It is off by default on purpose.
    Delete Something:
        Delete an object as you normally would. A moment later the add-on removes the data blocks that were left behind (objects, meshes, materials, textures, images and so on).
    Watch the Report:
        Every run prints a short summary in the panel (and optionally the console), for example:
        Purged 4 block(s) (meshes: 2, materials: 1, images: 1)
        If there was nothing to clean up, it reports: Nothing to purge
    Manual Purge:
        Click Purge Now at the bottom of the panel to run the exact same cleanup with one click, any time.

## Scope

The Scope options decide which kinds of data blocks the add-on is allowed to remove. Keep only the categories you care about.

    Objects: orphaned objects (left over after a deletion).
    Geometry: orphaned meshes, curves, lattices, armatures, volumes and similar.
    Materials: orphaned materials and node groups.
    Textures: orphaned legacy textures (include this if you use the old Texture system).
    Images: orphaned images.
    Misc: orphaned worlds, collections, lights, cameras, actions and other data. Off by default.

## Safety

The Safety section is what makes this add-on safe to run without watching it.

    Respect Fake User:
        On by default. Any data block that has Fake User enabled (the shield icon in the outliner) is never touched. This is Blender's own built-in "keep this for me" protection, and Auto Purge honours it.
        To protect something from being auto-purged, select it in the outliner and enable Fake User (Data > Fake User, or press the shield button). Fake User is also the recommended way to keep a texture library or a material collection around.
    Delay:
        How long the add-on waits after a deletion before purging (default 0.5s). Raising it can help when deleting large amounts at once, because all of those deletions are handled by a single purge.
    Report:
        Print the summary of each auto purge to the console as well as the panel.

Auto Purge removes nothing unless it is switched on, and even then it only ever removes data blocks that have zero users and no Fake User. Deleting an object always leaves its direct data behind, so you can press Ctrl+Z to get the object back — but once the auto purge has run, that freed-up data is gone for good. That is the point of the add-on, so treat this as a best-effort cleanup of genuinely unused data.

## How It Works

    No operator spam: Auto Purge never calls the built-in outliner purge operator repeatedly. It detects deletions with a cheap object-name snapshot in the depsgraph handler.
    Runs at a safe point: the actual purge is executed by a Blender timer, not inside the depsgraph update, so it never disturbs Blender while it is evaluating the scene. A re-entry guard and a short echo-suppression window prevent the purge from triggering itself.
    Debounced: rapid bursts of deletions are coalesced into a single purge run.
    Per-scene settings: everything is stored on the scene, so different scenes in the same file can use different scopes and settings.

## Notes and Limitations

    Auto Purge reacts to objects disappearing from the file. Deleting objects with X, or via outliner, Python, or scripts all trigger it.
    Data blocks you want to keep but which are currently unused (for example a material you are planning to reuse) should be given Fake User, otherwise they will be cleaned up like everything else with zero users.
    The add-on works purely with Blender's data API and has no external dependencies. Scenes, screen layouts, libraries and other "structural" data are never touched.

By following these steps and utilizing the settings, you can keep your Blender files clean and tidy automatically, without the risk of wiping out data you wanted to keep. Enjoy!