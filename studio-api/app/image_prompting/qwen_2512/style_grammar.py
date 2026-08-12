"""Style block compiler for Qwen-Image-2512.

Accepts a style profile dictionary and only serializes provided values.
It intentionally does not define or invent a full style registry.
"""

from __future__ import annotations

from typing import Any, Mapping


def _text(value: Any) -> str:
    return str(value or "").strip()


def compile_style_block(style_profile: Mapping[str, Any] | None) -> str:
    if not style_profile:
        return "No extra style override supplied; preserve the locked character identity over stylistic drift."

    ordered_keys = (
        "name",
        "medium",
        "genre",
        "rendering",
        "camera_language",
        "palette",
        "mood",
        "lighting",
        "finish",
        "background_treatment",
        "constraints",
    )
    parts = []
    for key in ordered_keys:
        value = style_profile.get(key) if isinstance(style_profile, Mapping) else None
        text = _text(value)
        if text:
            parts.append(f"{key.replace('_', ' ')}: {text}")

    extras = style_profile.get("notes") if isinstance(style_profile, Mapping) else None
    if isinstance(extras, list):
        notes = "; ".join(_text(item) for item in extras if _text(item))
        if notes:
            parts.append(f"notes: {notes}")
    elif _text(extras):
        parts.append(f"notes: {_text(extras)}")

    return "; ".join(parts) if parts else "Style profile present but empty; preserve identity without adding new stylistic assumptions."
