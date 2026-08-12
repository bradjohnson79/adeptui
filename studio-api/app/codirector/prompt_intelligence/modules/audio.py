"""Audio refinement — texture, space, dynamics, performance."""

from __future__ import annotations

from ..intent import PromptIntent
from ..models import GenerationDomain


def refine(prompt: str, intent: PromptIntent, domain: GenerationDomain) -> str:
    if domain not in ("audio", "music", "sfx", "voice"):
        return ""
    bits: list[str] = []
    lower = (prompt or "").lower()
    if domain == "voice":
        if "breath" not in lower:
            bits.append("natural breath and restrained delivery")
        if not intent.emotion:
            bits.append("clear emotional intention without overacting")
    else:
        if "spatial" not in lower and "stereo" not in lower and "space" not in lower:
            bits.append("clear spatial placement")
        if "texture" not in lower:
            bits.append("rich but controlled texture")
        if domain in ("music", "audio") and "emotion" not in lower and not intent.emotion:
            bits.append("cinematic emotional tone")
        if domain == "sfx" and "decay" not in lower:
            bits.append("natural attack and decay")
    return "; ".join(bits)
