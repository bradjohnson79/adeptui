"""Unify legacy panel script_sync_status and Scriptwriter sceneSync into mission statuses."""

from __future__ import annotations

from typing import Literal

ScriptLinkStatus = Literal[
    "linked",
    "script_updated",
    "override",
    "conflict",
    "unlinked",
]

# Legacy storyboard_panels.script_sync_status values
_LEGACY_MAP: dict[str, ScriptLinkStatus] = {
    "ok": "linked",
    "script_changed": "script_updated",
    "needs_regen": "script_updated",
    "non_visual": "linked",
    "override": "override",
    "conflict": "conflict",
    "unlinked": "unlinked",
}

# Scriptwriter sceneSync values
_SW_MAP: dict[str, ScriptLinkStatus] = {
    "synced": "linked",
    "linked": "linked",
    "unlinked": "unlinked",
    "stale": "script_updated",
    "conflict": "conflict",
    "override": "override",
}


def map_legacy_panel_sync(status: str | None) -> ScriptLinkStatus:
    if not status:
        return "unlinked"
    return _LEGACY_MAP.get(str(status).lower(), "unlinked")


def map_scriptwriter_scene_sync(status: str | None) -> ScriptLinkStatus:
    if not status:
        return "unlinked"
    return _SW_MAP.get(str(status).lower(), "unlinked")


def unify_status(
    *,
    panel_sync: str | None = None,
    scene_sync: str | None = None,
    has_segment_link: bool = False,
    has_scene_link: bool = False,
    creator_override: bool = False,
) -> ScriptLinkStatus:
    if creator_override:
        return "override"
    panel = map_legacy_panel_sync(panel_sync) if panel_sync else None
    scene = map_scriptwriter_scene_sync(scene_sync) if scene_sync else None
    if panel == "conflict" or scene == "conflict":
        return "conflict"
    if panel == "script_updated" or scene == "script_updated":
        return "script_updated"
    if panel == "override" or scene == "override":
        return "override"
    if panel == "linked" or scene == "linked":
        return "linked"
    if has_segment_link or has_scene_link:
        return "linked"
    return "unlinked"
