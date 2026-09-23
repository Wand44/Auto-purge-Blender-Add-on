# Auto Purge

Auto Purge keeps your `.blend` files lean by automatically removing *orphaned*
(unused) data blocks after you delete objects - and by giving you a safe,
one-click purge for everything else.

It runs without supervision: deletion is detected, the cleanup is debounced,
and it only ever removes data that has zero users (and no Fake User).

> Requires Blender **4.2 or newer** (the add-on also ships an extension manifest
> for the 4.2+ extension system).

## Installation

**As an extension (Blender 4.2 and newer):**

1. Download the add-on ZIP file.
2. `Edit > Preferences`, then open **Get Extensions**.
3. Click **Install from Disk**, select the ZIP, and install.
4. Enable **Auto Purge** and press **Save Preferences**.

**As a classic add-on:**

1. Download the add-on ZIP file.
2. `Edit > Preferences`, then open **Add-ons**.
3. Click **Install...**, select the ZIP, and install.
4. Enable **Auto Purge** and press **Save Preferences**.

## Getting started

1. Open the **Scene** properties tab (the globe/world icon).
2. In the **Auto-Purge Unused Data** panel, tick **Enable Auto-Purge**. It is
   off by default on purpose.
3. Delete an object as you normally would. A short moment later the orphaned
   data (objects, meshes, materials, images, …) is removed.
4. The panel shows the result of the last run, for example:

   ```
   Purged 4 block(s) (meshes: 2, materials: 1, images: 1)
   ```

   When there was nothing to clean up: `Nothing to purge`.

Use **Purge Now** at the top of the panel to run the exact same cleanup
manually, any time.

## Scope

The **Scope** options decide which kinds of data blocks the add-on may remove.
Only the enabled categories are ever touched.

| Option    | Covers                                                          | Default |
|-----------|-----------------------------------------------------------------|---------|
| Objects   | Orphaned objects left behind after a deletion                   | On      |
| Geometry  | Meshes, curves, surfaces, lattices, armatures, volumes and more | On      |
| Materials | Materials and node groups                                       | On      |
| Textures  | Legacy textures (the old Texture system)                        | On      |
| Images    | Images                                                          | On      |
| Misc      | Worlds, collections, lights, cameras, actions and other data    | Off     |

Because the scope is stored per scene, different scenes in the same file can use
different settings.

## Safety

The **Safety** section is what makes Auto Purge safe to leave running.

* **Respect Fake User** (default on): data with Fake User enabled (the shield
  icon in the Outliner) is never touched. Set Fake User on anything you want to
  keep around even though it is currently unused - for example a material
  library or a texture collection (`Data > Fake User`, or the shield button).
* **Delay**: how long to wait after a deletion before purging (default 0.5s).
  Raising it helps when deleting large batches at once - the burst is coalesced
  into a single purge.
* **Report**: also print each purge summary to the console.

Auto Purge removes nothing unless it is switched on, and it only ever removes
data that has zero users and no Fake User. Deleting an object always leaves its
direct data behind, so you can undo the deletion with `Ctrl+Z` - but once the
auto purge has run, that freed-up data is gone. That is the point of the
add-on: treat it as a best-effort cleanup of genuinely unused data.

## How it works

* **Detection, not spam**: Auto Purge never calls the outliner purge operator
  on a loop. A cheap object-name snapshot in the depsgraph handler detects
  deletions, and a persistent watchdog timer also probes for zero-user blocks
  so nothing is missed.
* **Runs at a safe point**: the actual purge runs from a Blender timer (the
  main thread), never inside the depsgraph update, so Blender is never disturbed
  mid-evaluation. A re-entry guard and an echo-suppression window keep the
  purge from triggering itself.
* **Debounced**: rapid bursts of deletions are coalesced into a single purge run.
* **Two purge paths**: when every scope category is enabled, removal is
  delegated to Blender's own recursive **Purge > Unused Data** mechanism -
  battle-tested and Fake-User safe on every data category. If any category is
  disabled, Auto Purge falls back to a precise per-category remover so your
  scope choice is respected *exactly*.

## Notes and limitations

* Auto Purge reacts to objects disappearing from the file - deleting with `X`,
  via the Outliner, or from a script all trigger it.
* Data you want to keep but which is currently unused must be given Fake User,
  otherwise it is cleaned up like any other zero-user block.
* The add-on works purely with Blender's data API and has no external
  dependencies. Scenes, screen layouts, library links and other structural
  data are never touched.