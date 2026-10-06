"""Lift nested read-tool envelopes so UI handoff reaches the browser.

Read tools are wrapped in ``{status, summary, data, toolId}``. Navigation
consumers (stream ``tool_completed``, frontend workspace change) read
``uiAction`` / ``workspaceUrl`` at the top level. Without this lift, a
successful ``audio.open`` pack completes while the creator stays on the
previous workspace.
"""

from __future__ import annotations

from typing import Any

_HANDOFF_KEYS = (
    "uiAction",
    "workspaceUrl",
    "workspace",
    "audioTab",
    "contentTab",
    "projectId",
    "characterId",
    "method",
    "preferredMethod",
)

_HANDOFF_TOOLS = frozenset(
    {
        "audio.open_studio",
        "voice_environment.open_audio_studio",
        "character_creator.open_voice_creator",
        "voice_performance.open_workspace",
        "workspace.open_scriptwriter",
        "workspace.open_scene_creator",
        "workspace.open_image_generator",
        "film_timeline.send_to_magi",
    }
)


def lift_ui_handoff(plan_data: Any) -> dict[str, Any]:
    """Copy nested ``data`` handoff fields onto the top-level payload."""
    if not isinstance(plan_data, dict):
        return {}
    lifted = dict(plan_data)
    nested = lifted.get("data")
    if isinstance(nested, dict):
        for key in _HANDOFF_KEYS:
            if not lifted.get(key) and nested.get(key):
                lifted[key] = nested[key]
    return lifted


def is_ui_handoff(plan_data: Any) -> bool:
    """True when the payload should emit ``tool_completed`` for navigation."""
    payload = lift_ui_handoff(plan_data)
    if payload.get("uiAction") or payload.get("workspaceUrl"):
        return True
    return str(payload.get("toolId") or "") in _HANDOFF_TOOLS
