"""Cinematic refinement — framing, lighting, lens language."""

from __future__ import annotations

from ..intent import PromptIntent
from ..models import GenerationDomain


def refine(prompt: str, intent: PromptIntent, domain: GenerationDomain) -> str:
    if domain not in ("image", "video"):
        return ""
    bits: list[str] = []
    if not intent.camera:
        bits.append("cinematic framing with clear visual hierarchy")
    if not intent.lighting:
        bits.append("soft cinematic lighting with gentle depth")
    if domain == "image" and "composition" not in (prompt or "").lower() and not intent.composition:
        bits.append("balanced composition")
    return "; ".join(bits)
