"""Compose final provider prompt from English + language modules."""

from __future__ import annotations

from typing import Optional

from .errors import FINAL_PROMPT_EMPTY, PROMPT_TOO_LONG, PromptIntelligenceError
from .profiles import PromptProfile


def merge_english(base: str, layers: list[str]) -> str:
    parts = [base.strip()] if base and base.strip() else []
    for layer in layers:
        text = (layer or "").strip().rstrip(".")
        if not text:
            continue
        # Avoid duplicate appends
        if text.lower() in (base or "").lower():
            continue
        parts.append(text)
    merged = ". ".join(parts).strip()
    merged = merged.replace("..", ".").strip()
    if merged and not merged.endswith("."):
        merged += "."
    return merged


def compose_final(
    refined_english: str,
    language_enhancements: dict[str, str],
    *,
    profile: PromptProfile,
    ordering: Optional[str] = None,
) -> str:
    en = (refined_english or "").strip()
    zh = (language_enhancements.get("zh") or "").strip()
    order = ordering or profile.promptOrdering or "english-first"

    if not en and not zh:
        raise PromptIntelligenceError(
            FINAL_PROMPT_EMPTY,
            "Final provider prompt would be empty.",
            recoverable=True,
            recommended_action="fallback_english_only",
        )

    if order == "chinese-first" and zh:
        final = f"{zh}\n{en}".strip() if en else zh
    elif order == "interleaved" and zh:
        # Keep blocks separate — never word-by-word mixing
        final = f"{en}\n{zh}".strip() if en else zh
    else:
        final = f"{en}\n{zh}".strip() if zh else en

    max_len = profile.maxPromptLength or 4000
    if len(final) > max_len:
        raise PromptIntelligenceError(
            PROMPT_TOO_LONG,
            f"Final provider prompt exceeds profile max length ({max_len}).",
            details={"length": len(final), "maxPromptLength": max_len},
            recoverable=True,
            recommended_action="shorten_or_disable_language_modules",
        )
    if not final.strip():
        raise PromptIntelligenceError(
            FINAL_PROMPT_EMPTY,
            "Final provider prompt is empty after composition.",
            recoverable=True,
            recommended_action="fallback_english_only",
        )
    return final
