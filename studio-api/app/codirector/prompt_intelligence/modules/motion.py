"""Motion refinement — subject / camera / environment motion."""

from __future__ import annotations

from ..intent import PromptIntent
from ..models import GenerationDomain


def refine(prompt: str, intent: PromptIntent, domain: GenerationDomain) -> str:
    if domain != "video":
        return ""
    bits: list[str] = []
    lower = (prompt or "").lower()
    if not intent.motion and "camera" not in lower:
        bits.append("stable, fluent camera motion")
    if "micro-expression" not in lower and "expression" not in lower:
        bits.append("subtle natural facial micro-expressions when the face is visible")
    if "environment" not in lower and "wind" not in lower and "ambient motion" not in lower:
        bits.append("fine environmental motion for realism")
    return "; ".join(bits)
