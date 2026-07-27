"""Translation adapter with provenance — never silent overwrite of originals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from .glossary import PLATFORM_PROTECTED_TERMS, apply_glossary_protection
from .registry import resolve_locale

TranslationState = Literal[
    "MACHINE_DRAFT", "REVIEW_REQUIRED", "APPROVED", "LOCKED", "STALE", "FAILED"
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def translate_text(
    text: str,
    *,
    source_language: str,
    target_language: str,
    glossary: Optional[list[dict[str, Any]]] = None,
    locked: bool = False,
    method: str = "passthrough_or_identity",
) -> dict[str, Any]:
    src = resolve_locale(source_language)
    tgt = resolve_locale(target_language)
    original = text or ""
    if locked:
        return {
            "translationId": f"tr_{uuid4().hex[:12]}",
            "sourceLanguage": src,
            "targetLanguage": tgt,
            "originalText": original,
            "translatedText": original,
            "translationMethod": method,
            "state": "LOCKED",
            "confidence": 1.0,
            "protectedTermsApplied": [],
            "timestamp": _now(),
            "humanReviewStatus": "locked",
            "notes": ["Locked translation was not replaced"],
        }

    glossary = list(glossary or [])
    protected_from_glossary: list[str] = []
    _, protected_from_glossary = apply_glossary_protection(original, glossary)
    protected = sorted(set(protected_from_glossary + [t for t in PLATFORM_PROTECTED_TERMS if t in original]))

    # Offline-safe identity path when source==target; otherwise MACHINE_DRAFT placeholder
    # that preserves original (cloud MT may replace later). Never fabricates fluency.
    if src == tgt:
        translated = original
        state: TranslationState = "APPROVED"
        confidence = 1.0
        notes = ["Identity translation"]
    else:
        translated = original
        state = "REVIEW_REQUIRED"
        confidence = 0.0
        notes = [
            "Offline identity draft — cloud/LLM translation not applied; original preserved for review",
            f"Target locale requested: {tgt}",
        ]

    # Negation safety: if source had "no music" style intent markers, keep them in output
    dangerous_flip = False
    lower = original.lower()
    if ("no music" in lower or "without music" in lower) and (
        "with music" in translated.lower() and "without music" not in translated.lower()
    ):
        dangerous_flip = True
        state = "FAILED"
        notes.append("Dangerous audio negation inversion detected")

    return {
        "translationId": f"tr_{uuid4().hex[:12]}",
        "sourceLanguage": src,
        "targetLanguage": tgt,
        "originalText": original,
        "translatedText": translated,
        "translationMethod": method,
        "state": state,
        "confidence": confidence,
        "protectedTermsApplied": protected,
        "timestamp": _now(),
        "glossaryVersion": "m30f-v1",
        "humanReviewStatus": "machine_draft" if state == "REVIEW_REQUIRED" else state.lower(),
        "notes": notes,
        "dangerousFlipDetected": dangerous_flip,
    }
