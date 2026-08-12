"""Character / bible continuity refinement."""

from __future__ import annotations

from ..intent import PromptIntent
from ..models import GenerationDomain


def refine(prompt: str, intent: PromptIntent, domain: GenerationDomain, continuity_hints: list[str] | None = None) -> str:
    hints = [h.strip() for h in (continuity_hints or []) if h and h.strip()]
    if intent.continuity and intent.continuity not in hints:
        hints.append(intent.continuity)
    if not hints:
        return ""
    # Do not invent identity — only echo provided continuity constraints
    joined = "; ".join(hints[:6])
    return f"continuity: {joined}"
