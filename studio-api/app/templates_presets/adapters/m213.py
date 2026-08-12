"""Read-only adapter: M2.13 lighting/theme/blocking → unified intent preview."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...codirector.m213.scene_state import LIGHT_PRESETS, default_camera_state, default_lighting_state


def preview_light_preset(preset_name: str) -> dict[str, Any]:
    if preset_name not in LIGHT_PRESETS:
        return {
            "intent": {},
            "providerMappings": {},
            "source": {"system": "m213", "id": preset_name, "version": None},
            "gaps": ["unknown_light_preset"],
            "needsClarification": True,
        }
    state = default_lighting_state(preset_name)
    return {
        "intent": {
            "lighting": {
                "preset": state.get("preset"),
                "rig": state.get("rig"),
                "promptLayers": state.get("promptLayers"),
            },
            "camera": default_camera_state(),
        },
        "providerMappings": {},
        "source": {"system": "m213", "id": preset_name, "version": 1, "kind": "light_preset"},
        "gaps": [],
        "needsClarification": False,
        "note": "Read-only preview. Not a native creative_item.",
    }


def preview_theme(db: Session, theme_id: str) -> dict[str, Any]:
    gaps: list[str] = []
    theme: dict[str, Any] = {}
    try:
        from ...codirector.m213 import theme as theme_mod

        if hasattr(theme_mod, "get_theme"):
            theme = theme_mod.get_theme(db, theme_id) or {}
        elif hasattr(theme_mod, "ThemeService"):
            theme = theme_mod.ThemeService.get(db, theme_id) or {}
    except Exception as exc:
        gaps.append(f"theme_read_error:{exc.__class__.__name__}")
    if not theme:
        gaps.append("not_found")
    profile_json = theme.get("profile") or theme.get("profile_json") or theme
    intent = {
        "color": {
            "palette": (profile_json or {}).get("palette") if isinstance(profile_json, dict) else None,
            "mood": (profile_json or {}).get("mood") if isinstance(profile_json, dict) else None,
        },
        "approval": theme.get("approvalState") or theme.get("approval_state"),
    }
    return {
        "intent": intent,
        "providerMappings": {},
        "source": {"system": "m213", "id": theme_id, "version": theme.get("version"), "kind": "theme"},
        "gaps": gaps,
        "needsClarification": bool(gaps),
        "note": "Read-only preview. Not a native creative_item.",
    }


def list_light_preset_previews() -> list[dict[str, Any]]:
    return [preview_light_preset(name) for name in LIGHT_PRESETS]
