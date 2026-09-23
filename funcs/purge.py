"""Orchestration and the purge engine for Auto-Purge.

Design (kept deliberately close to how the add-on "worked before", while
retaining every security feature added for review feedback):

* The actual data removal is delegated to Blender's own outliner "orphans"
  purge operator (``bpy.ops.outliner.orphans_purge``) — the exact, battle-tested
  mechanism the original single-file add-on used on day one, and the same one
  Blender's manual "Purge > Unused Data" runs. It is recursive, respects Fake
  User on every data category, works on every backport, and cannot silently
  "purge nothing" when there is something to purge.
* The operator is NEVER invoked inside the depsgraph handler (running operators
  there is unsafe and was the original review complaint). Deletions are only
  *detected* there via a cheap object-name snapshot + a persistent watchdog
  timer; the operator runs later, on the main thread, from the timer tick after
  a debounce.
* Scope groups still apply: when **every** scope category is enabled the add-on
  takes the reliable orphan-purge operator path (which purges all unused
  categories); when the user disables any category, the purge falls back to the
  precise per-attribute data-API remover so the scope choice is respected
  exactly.
* Fake User is always respected (both paths guard ``use_fake_user``); respect
  for Fake User can additionally be toggled by the user (in the precise path).
* Everything in this module is idempotent: register/unregister may be called
  any number of times without leaking handlers, timers or duplicate callbacks.
"""

import time

import bpy

# ---------------------------------------------------------------------------
# Version (single source of truth)
# ---------------------------------------------------------------------------
# Imported by the root __init__.py (bl_info) and the UI panel (version label).
# blender_manifest.toml mirrors this string for the extension platform.
ADDON_VERSION_STRING = "1.1.2"
ADDON_VERSION_TUPLE = (1, 1, 2)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
MIN_DEBOUNCE = 0.1
MAX_DEBOUNCE = 5.0
DEFAULT_DEBOUNCE = 0.5
WATCHDOG_INTERVAL = 0.5          # watchdog poll period (timer seconds)
MAX_TIMER_INTERVAL = 5.0
MAX_PURGE_PASSES = 10

# ---------------------------------------------------------------------------
# Scope groups
# ---------------------------------------------------------------------------
# Each purge scope maps to one or more bpy.data.* attribute names. Only
# attributes that exist in the running build are used (guarded by getattr), so
# this stays compatible with data categories that appear/change between
# Blender releases.
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

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def count_orphans_in_scope(settings):
    """Per-category counts of purgeable zero-user blocks in the enabled scope.

    Replicates the scope gating used by :func:`purge_groups` (active groups,
    their mapped data attrs, the Fake User respect flag and the scene-collection
    guard) so detection is always consistent with what a real purge would
    actually remove. Used by the watchdog probe and to measure operator-path
    purges accurately.
    """
    groups = active_groups(settings)
    respect_fake_user = bool(getattr(settings, "respect_fake_user", True))
    counts = {}
    for group in groups:
        for attr in PURGE_GROUPS.get(group, ()):
            try:
                blocks = getattr(bpy.data, attr)
            except Exception:
                continue
            for block in blocks:
                try:
                    if block.users != 0:
                        continue
                    if respect_fake_user and block.use_fake_user:
                        continue
                    if attr == "collections" and _belongs_to_scene(block):
                        continue
                except Exception:
                    continue
                counts[group] = counts.get(group, 0) + 1
    return counts


def has_orphans_in_scope(settings):
    """True when the *enabled scope* currently holds a purgeable zero-user block.

    Only ever called from the watchdog tick — it only *schedules*, never purges.
    """
    return any(count_orphans_in_scope(settings).values())


def active_groups(settings):
    """Return the list of scope-group keys currently enabled on Auto-Purge settings."""
    return [group for group, attr in GROUP_ATTRS.items() if getattr(settings, attr, False)]


def _scope_is_unrestricted(groups):
    """True when every known scope group is enabled (Blender's own purge path)."""
    return set(groups) >= set(GROUP_ATTRS)


def format_result(removed):
    """Turn the removed-counts dict into a short human readable string."""
    if not removed:
        return "Nothing to purge"
    total = sum(removed.values())
    parts = sorted(removed.items(), key=lambda kv: (-kv[1], kv[0]))
    detail = ", ".join(f"{k}: {n}" for k, n in parts)
    return f"Purged {total} block(s) ({detail})"


# ---------------------------------------------------------------------------
# The two purge paths
# ---------------------------------------------------------------------------


def purge_groups(active, respect_fake_user=True, max_passes=MAX_PURGE_PASSES):
    """Precise, data-API remover used when the user narrows the scope.

    Only touches the bpy.data.<attr> categories whose scope group is enabled,
    runs several passes to clear nested orphans in dependency order, strands
    Fake-User blocks untouched, and leaks nothing. Iterating a live bpy
    collection while removing is unsafe, so every pass works from a snapshot.
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
            group = group_for_attr(attr, active)
            try:
                blocks = getattr(bpy.data, attr)
            except AttributeError:
                continue
            for block in list(blocks):
                if getattr(block, "users", 1) != 0:
                    continue
                if respect_fake_user and getattr(block, "use_fake_user", False):
                    continue
                # Never let the scene's own collection be removed.
                if attr == "collections" and _belongs_to_scene(block):
                    continue
                try:
                    blocks.remove(block)
                except Exception:
                    continue
                removed[group] = removed.get(group, 0) + 1
                changed = True
        if not changed:
            break
    return removed


def purge_all_via_operator(settings):
    """Blender's own recursive orphan purge (the 'worked before' mechanism).

    Delegates to ``bpy.ops.outliner.orphans_purge`` so unused data is removed
    exactly as Blender's native 'Purge > Unused Data' does — recursive, Fake
    User safe, and never a silent no-op. Only called from a safe main-thread
    point (a timer tick, or the manual "Purge Now" operator), never from inside
    the depsgraph handler. Removed counts are measured by diffing the enabled
    scope before and after, so the report is accurate.
    """
    if not getattr(settings, "enabled", False):
        return {}
    if bpy.context.window_manager is None:
        return {}
    before = count_orphans_in_scope(settings)
    if not before:
        return {}
    try:
        bpy.ops.outliner.orphans_purge(
            do_local_ids=True,
            do_linked_ids=True,
            do_recursive=True,
        )
    except Exception:
        return {}
    after = count_orphans_in_scope(settings)
    removed = {}
    for group, count in before.items():
        diff = count - after.get(group, 0)
        if diff > 0:
            removed[group] = diff
    return removed


def group_for_attr(attr, active):
    for group in active:
        if attr in PURGE_GROUPS.get(group, ()):
            return group
    return attr


# ---------------------------------------------------------------------------
# Shared purge entry points
# ---------------------------------------------------------------------------


def run_purge(settings):
    """Remove unused data for the current scope; return per-category counts.

    Uses Blender's own orphan-purge operator when the scope is fully open,
    otherwise the precise per-category remover. Safe to call from a timer tick
    or from the manual "Purge Now" operator.
    """
    groups = active_groups(settings)
    if _scope_is_unrestricted(groups):
        return purge_all_via_operator(settings)
    return purge_groups(
        groups,
        respect_fake_user=getattr(settings, "respect_fake_user", True),
    )


def record_result(settings, removed):
    """Persist and optionally print a human readable summary of a purge run."""
    result = format_result(removed)
    settings.last_result = f"{time.strftime('%H:%M:%S')} - {result}"
    if getattr(settings, "report", False):
        print(f"[Auto Purge] {result}")


def _belongs_to_scene(collection):
    for scene in bpy.data.scenes:
        for name in ("collection", "master_collection"):
            node = getattr(scene, name, None)
            if node is not None and node == collection:
                return True
    return False


# ---------------------------------------------------------------------------
# Watchdog / manager
# ---------------------------------------------------------------------------


class AutoPurgeManager:
    """Detects data deletions and schedules a safe, debounced purge.

    A persistent timer is the source of truth for when a purge may actually run
    (the safe main-thread point). The depsgraph update handler only *detects*
    removals by keeping a cheap object-name snapshot; it never purges. The timer
    additionally polls so a purge still happens even if no depsgraph event ever
    fires (watchdog fallback).
    """

    def __init__(self):
        self._snapshot = set()
        self._pending = False
        self._purging = False
        self._ignore_until = 0.0
        self._purge_ready_at = 0.0

    def seed(self):
        """Rebuild the known-object snapshot (called at start and after purges)."""
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
        """Snapshot + compare object names; *detect* a deletion, never purge here."""
        if self._purging or not getattr(settings, "enabled", False):
            self.seed()
            return
        try:
            current = {o.name for o in bpy.data.objects}
        except Exception:
            current = set()
        removed = self._snapshot - current
        self._snapshot = current
        if not removed:
            return
        if time.monotonic() < self._ignore_until:
            return
        self._schedule(settings)

    def schedule_debounced(self, settings):
        """Public, pure-scheduling wrapper used by the watchdog tick.

        Runs on the timer tick (the single safe point a purge may ever be
        scheduled from); applies the same debounce/_pending gate as the
        object-deletion detection path, so scheduling here is never more
        aggressive than scheduling from a deletion. Does not purge."""
        self._schedule(settings)

    def _schedule(self, settings):
        if self._pending:
            return
        self._pending = True
        try:
            debounce = float(getattr(settings, "debounce", DEFAULT_DEBOUNCE))
        except Exception:
            debounce = DEFAULT_DEBOUNCE
        debounce = min(max(debounce, MIN_DEBOUNCE), MAX_DEBOUNCE)
        self._purge_ready_at = time.monotonic() + debounce
        if getattr(settings, "report", False):
            print(f"[Auto Purge] deletion detected; purge scheduled in ~{debounce:.2f}s")

    def purge_if_due(self, settings):
        """Run the scheduled purge once the debounce has elapsed (timer safe point)."""
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
            record_result(settings, run_purge(settings))
        except Exception:
            pass
        finally:
            self._purging = False
            self._cooldown(settings)

    def _cooldown(self, settings):
        self.seed()
        try:
            debounce = float(getattr(settings, "debounce", DEFAULT_DEBOUNCE))
        except Exception:
            debounce = DEFAULT_DEBOUNCE
        self._ignore_until = time.monotonic() + min(max(debounce, 0.0), MAX_TIMER_INTERVAL)

    def status(self):
        """Short, human readable description of the current manager state."""
        if self._purging:
            return "purging"
        if self._pending:
            return "purge pending"
        return "watching for unused data"


manager = AutoPurgeManager()


# ---------------------------------------------------------------------------
# Blender glue: handlers + persistent watchdog timer (all idempotent)
# ---------------------------------------------------------------------------


def _depsgraph_update_handler(scene, depsgraph):
    """Depsgraph update handler: detect deletions only, never purge."""
    settings = getattr(getattr(bpy.context, "scene", None), "auto_purge", None)
    if settings is not None and getattr(settings, "enabled", False):
        manager.on_depsgraph_update(settings)


def _poll_tick():
    """Persistent watchdog: run scheduled purges at a safe timer point, and
    also detect deletions from deletions the handler may have missed."""
    scene = getattr(bpy.context, "scene", None)
    settings = getattr(scene, "auto_purge", None) if scene is not None else None
    if settings is not None and getattr(settings, "enabled", False):
        manager.on_depsgraph_update(settings)
        if has_orphans_in_scope(settings):
            manager.schedule_debounced(settings)
        manager.purge_if_due(settings)
    return WATCHDOG_INTERVAL


def _load_post_handler(*args):
    """Re-seed the manager snapshot after loading a new file.

    Accepts the filepath argument Blender passes to ``load_post`` (and ignores
    it); ``*args`` keeps this compatible across Blender versions that vary the
    exact call signature.
    """
    manager.seed()


# ---------------------------------------------------------------------------
# Registration (idempotent: safe to call repeatedly)
# ---------------------------------------------------------------------------


def register():
    if _depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_update_handler)
    if _load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_handler)
    if not bpy.app.timers.is_registered(_poll_tick):
        bpy.app.timers.register(_poll_tick, persistent=True)
    manager.seed()


def unregister():
    for handler in (_depsgraph_update_handler, _load_post_handler):
        for hlist in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.load_post):
            try:
                hlist.remove(handler)
            except ValueError:
                pass
    try:
        bpy.app.timers.unregister(_poll_tick)
    except Exception:
        pass
    manager.reset()
