"""Production refinement — clarity, pacing, restraint."""

from __future__ import annotations

from ..intent import PromptIntent
from ..models import GenerationDomain


def refine(prompt: str, intent: PromptIntent, domain: GenerationDomain) -> str:
    base = (prompt or "").strip()
    if not base:
        return ""
    extras: list[str] = []
    if domain in ("image", "video") and "coherent" not in base.lower():
        extras.append("maintain visual coherence and production-ready clarity")
    if domain == "video" and "continuity" not in base.lower() and not intent.continuity:
        extras.append("preserve temporal continuity across the shot")
    if domain in ("audio", "music", "sfx") and "dynamic range" not in base.lower():
        extras.append("balanced dynamic range")
    if domain == "voice" and "natural" not in base.lower():
        extras.append("natural pacing with restrained emphasis")
    if not extras:
        return base
    return f"{base.rstrip('.')}. {'; '.join(extras)}."
