import time

import bpy

# Scope groups: which Blender data categories each setting can purge.
# Only entries that exist in the running Blender are used (guarded by getattr).
PURGE_GROUPS = {
    "objects": ("objects",),
    "geometry": (
        "meshes", "curves", "surfaces", "lattices", "armatures",
        "metaballs", "volumes", "grease_pencils", "hair_curves",
        "pointclouds", "shape_keys",
    ),
    "materials": ("materials", "node_groups"),
    "textures": ("textures",),
    "images": ("images",),
    "misc": (
        "worlds", "collections", "lights", "cameras", "speakers",
        "actions", "brushes", "linestyles", "movieclips", "masks",
        "fonts", "particles", "palettes", "sounds", "lightprobes",
    ),
}

GROUP_ATTRS = {
    "objects": "purge_objects",
    "geometry": "purge_geometry",
    "materials": "purge_materials",
    "textures": "purge_textures",
    "images": "purge_images",
    "misc": "purge_misc",
}

MAX_PURGE_PASSES = 10
MIN_TIMER_INTERVAL = 0.05
MAX_TIMER_INTERVAL = 5.0

# Full add-on version, so the UI can label builds without importing Blender data.
ADDON_VERSION_STRING = "1.1.1"
POLL_INTERVAL = 0.5

# Matches bl_info["version"] in the root __init__.py (kept in sync manually).


def active_groups(settings):
    """Return the list of scope-group keys enabled on an Auto-Purge settings group."""
    return [group for group, attr in GROUP_ATTRS.items() if getattr(settings, attr, False)]


def purge_groups(active, respect_fake_user=True, max_passes=MAX_PURGE_PASSES):
    """Remove orphaned data blocks (zero users) for the requested scope groups.

    Purges directly through the data API rather than the outliner operator so it
    never runs inside a depsgraph update, and repeats several passes so nested
    orphans (e.g. object -> mesh -> shape key / material -> node -> texture) are
    cleaned up in dependency order. Data blocks that carry a Fake User are never
    touched.

    Returns a dict mapping data-category name -> number of blocks removed.
    """
    attrs = []
    for group in active:
        for attr in PURGE_GROUPS.get(group, ()):
            if attr not in attrs:
                attrs.append(attr)

    removed = {}
    for _ in range(max_passes):
        changed = False
        for attr in attrs:
            try:
                blocks = getattr(bpy.data, attr)
            except AttributeError:
                continue
            # Snapshot: removing while iterating a bpy collection is unsafe.
            for block in list(blocks):
                if getattr(block, "users", 1) != 0:
                    continue
                if respect_fake_user and getattr(block, "use_fake_user", False):
                    continue
                # Never remove a collection that still belongs to a scene.
                if attr == "collections" and _is_scene_collection(block):
                    continue
                try:
                    blocks.remove(block)
                except Exception:
                    continue
                removed[attr] = removed.get(attr, 0) + 1
                changed = True
        if not changed:
            break
    return removed


def _is_scene_collection(collection):
    for scene in bpy.data.scenes:
        for name in ("collection", "master_collection"):
            if getattr(scene, name, None) == collection:
                return True
    return False


def format_result(removed):
    """Turn the removed-counts dict into a short human readable string."""
    if not removed:
        return "Nothing to purge"
    total = sum(removed.values())
    parts = sorted(removed.items(), key=lambda kv: (-kv[1], kv[0]))
    detail = ", ".join(f"{k}: {n}" for k, n in parts)
    return f"Purged {total} block(s) ({detail})"


class AutoPurgeManager:
    """Detects object deletions and schedules safe, debounced purge runs.

    Design notes (addressing Blender's add-on review feedback):

    * Stability: the purge never runs inside the depsgraph_update_post handler
      (running operators in there is unsafe). Deletions are only *detected* there
      via a cheap object-name snapshot; the actual purge runs later from the
      persistent watchdog timer (_poll_tick), which is a safe point on the main
      thread.
    * Performance: the handler skips all work immediately unless auto-purge is
      enabled and no purge is pending/cooldowning. It does not fire the (much
      heavier) orphan-purge operator. The watchdog ticks every 0.5s and only does
      real work when enabled.
    * Safety: only data blocks with zero users and no Fake User are removed, only
      the scope groups the user enabled, and everything is opt-in (off by default).
    """

    def __init__(self):
        self._snapshot = set()
        self._pending = False
        self._purging = False
        self._ignore_until = 0.0
        self._purge_ready_at = 0.0

    def seed(self):
        """Rebuild the known-object snapshot (called at start and after a purge)."""
        try:
            self._snapshot = {o.name for o in bpy.data.objects}
        except Exception:
            self._snapshot = set()

    def reset(self):
        self._pending = False
        self._purging = False
        self._ignore_until = 0.0
        self._purge_ready_at = 0.0
        self._snapshot = set()

    def on_depsgraph_update(self, settings):
        """Handle a depsgraph update: look for removed objects, cheaply.

        Keeps the snapshot fresh on every call so deletions are never missed;
        the echo-guard only suppresses scheduling a new purge right after a
        purge has run (the purge's own removals would otherwise re-trigger it).
        """
        if self._purging or not getattr(settings, "enabled", False):
            return
        try:
            current = {o.name for o in bpy.data.objects}
        except Exception:
            return
        removed = self._snapshot - current
        self._snapshot = current
        if not removed:
            return
        if time.monotonic() < self._ignore_until:
            return
        self._schedule(settings)

    def status(self):
        """Short, human readable description of the current manager state."""
        if self._purging:
            return "purging"
        if self._pending:
            return "purge pending"
        return "watching for unused data"

    def _schedule(self, settings):
        if self._pending:
            return
        self._pending = True
        interval = min(max(float(getattr(settings, "debounce", 0.5)), MIN_TIMER_INTERVAL),
                       MAX_TIMER_INTERVAL)
        self._purge_ready_at = time.monotonic() + interval
        if getattr(settings, "report", False):
            print(f"[Auto Purge] object deletion detected; purge in ~{interval:.2f}s")

    def purge_if_due(self, settings):
        """Run the scheduled purg once the debounce has elapsed (timer safe point)."""
        if not self._pending or self._purging:
            return
        if not getattr(settings, "enabled", False):
            self._pending = False
            return
        if time.monotonic() < self._purge_ready_at:
            return
        self._pending = False
        self._purging = True
        try:
            removed = purge_groups(
                active_groups(settings),
                respect_fake_user=settings.respect_fake_user,
            )
            self._record(settings, removed)
        except Exception:
            pass
        finally:
            self._purging = False
            self._cooldown_after_purge(settings)

    @staticmethod
    def _record(settings, removed):
        result = format_result(removed)
        settings.last_result = f"{time.strftime('%H:%M:%S')} - {result}"
        if getattr(settings, "report", False):
            print(f"[Auto Purge] {result}")

    def _cooldown_after_purge(self, settings):
        self.seed()
        try:
            delay = float(getattr(settings, "debounce", 0.5))
        except Exception:
            delay = 0.5
        self._ignore_until = time.monotonic() + min(max(delay, 0.0), MAX_TIMER_INTERVAL)


manager = AutoPurgeManager()


def _depsgraph_update_handler(*args):
    """Registered on bpy.app.handlers.depsgraph_update_post (2-arg in recent Blender)."""
    try:
        scene = bpy.context.scene
        if scene is not None and hasattr(scene, "auto_purge"):
            manager.on_depsgraph_update(scene.auto_purge)
    except Exception:
        pass


def _load_post_handler(*args):
    manager.seed()


def _load_pre_handler(*args):
    manager.reset()


def _poll_tick():
    """Persistent watchdog: detect deletions and run scheduled purges.

    Runs every POLL_INTERVAL seconds while Blender is idle. The depsgraph_update_post
    handler gives fast detection when it fires; this timer is the reliable fallback (it
    detects deletions AND performs the purge at the same safe timer point) so Auto-Purge
    never depends on the handler alone. Does nothing meaningful unless Auto-Purge is
    enabled (cheap early return).
    """
    scene = bpy.context.scene
    settings = getattr(scene, "auto_purge", None) if scene is not None else None
    if settings is not None:
        manager.on_depsgraph_update(settings)
        manager.purge_if_due(settings)
    return POLL_INTERVAL


def register():
    # No data access here: bpy.context/bpy.data are restricted while an add-on
    # registers. The manager self-initialises on the first depsgraph update and
    # is re-seeded by the load_post handler whenever a file is loaded.
    # All registrations are idempotent so a reload (e.g. VS Code reconnect that
    # calls register() again) cannot duplicate handlers or watchdog timers.
    if _depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_update_handler)
    if _load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_handler)
    if _load_pre_handler not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_load_pre_handler)
    if not bpy.app.timers.is_registered(_poll_tick):
        bpy.app.timers.register(_poll_tick, first_interval=POLL_INTERVAL, persistent=True)


def unregister():
    for handler, lst in (
        (_depsgraph_update_handler, bpy.app.handlers.depsgraph_update_post),
        (_load_post_handler, bpy.app.handlers.load_post),
        (_load_pre_handler, bpy.app.handlers.load_pre),
    ):
        try:
            lst.remove(handler)
        except ValueError:
            pass
    try:
        bpy.app.timers.unregister(_poll_tick)
    except Exception:
        pass
    manager.reset()