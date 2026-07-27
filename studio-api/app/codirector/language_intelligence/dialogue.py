"""Language-aware dialogue / subtitle model (linked variants, no scene duplication)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4


def make_dialogue(
    *,
    scene_id: str,
    speaker_id: str,
    original_language: str,
    original_text: str,
    start: float = 0.0,
    end: float = 0.0,
    dialogue_id: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "dialogueId": dialogue_id or f"dlg_{uuid4().hex[:10]}",
        "sceneId": scene_id,
        "speakerId": speaker_id,
        "originalLanguage": original_language,
        "originalText": original_text,
        "localizedVariants": {},
        "timing": {"start": start, "end": end},
        "constructedLanguage": False,
        "transliterationOnly": False,
    }


def add_variant(
    dialogue: dict[str, Any],
    *,
    locale: str,
    text: str,
    status: str = "draft",
) -> dict[str, Any]:
    out = dict(dialogue)
    variants = dict(out.get("localizedVariants") or {})
    existing = variants.get(locale) or {}
    if existing.get("status") == "locked":
        return out
    variants[locale] = {"text": text, "status": status}
    out["localizedVariants"] = variants
    return out


def mark_constructed_language(dialogue: dict[str, Any], *, enabled: bool = True) -> dict[str, Any]:
    out = dict(dialogue)
    out["constructedLanguage"] = enabled
    return out
