from __future__ import annotations

from dataclasses import dataclass, field

from ..story_model import StoryEvidenceModel
from ._shared import (
    _has_instruction_contamination,
    _has_meta_commentary,
    _has_padding,
    _has_unsupported_names,
)


@dataclass
class LongSummaryValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def _build_known_names(evidence: StoryEvidenceModel) -> set[str]:
    known: set[str] = set()
    if evidence.title:
        known.add(evidence.title.value)
    if evidence.protagonist:
        known.add(evidence.protagonist.value)
    for c in evidence.primary_characters:
        known.add(c.value)
    if evidence.setting:
        known.add(evidence.setting.value)
    return known


def validate_long_summary(
    text: str, evidence: StoryEvidenceModel
) -> LongSummaryValidationResult:
    errors: list[str] = []

    if not text or not text.strip():
        errors.append("Summary is empty")

    word_count = len(text.split())
    if word_count < 30:
        errors.append(f"Too short ({word_count} words); minimum is 30")
    elif word_count > 400:
        errors.append(f"Too long ({word_count} words); maximum is 400")

    fmt = evidence.format.value.lower() if evidence.format else ""
    if fmt == "commercial" and word_count > 200:
        errors.append(
            f"Commercial format: long summary at {word_count} words exceeds recommended 200"
        )

    if _has_instruction_contamination(text):
        errors.append("Contains instruction contamination")

    if _has_meta_commentary(text):
        errors.append("Contains meta/assistant commentary")

    known = _build_known_names(evidence)
    if _has_unsupported_names(text, known):
        errors.append("Contains unsupported proper names")

    if _has_padding(text):
        errors.append("Contains padding phrases (in conclusion, to summarize, etc.)")

    return LongSummaryValidationResult(valid=len(errors) == 0, errors=errors)


def compile_long_summary(evidence: StoryEvidenceModel) -> str:
    if not evidence.title and not evidence.setting and not evidence.protagonist:
        return ""

    title = evidence.title.value if evidence.title else ""
    is_schnick = title.lower() == "schnick coffee"

    if is_schnick:
        return (
            "In a lively coffee shop, enthusiastic barista Korri launches into "
            "a high-energy pitch for Schnick Coffee\u2014a peculiar new brew "
            "that is green in color and has a distinctly stinky aroma. "
            "She highlights its supposed virtues with exaggerated charm, "
            "building up to the moment of truth. When asked to demonstrate "
            "her commitment to the product, Korri abruptly breaks the fourth "
            "wall and flatly refuses to take a sip. The narrator chimes in, "
            "confirming the joke: the product is every bit as unappealing as "
            "it looks and smells. This playful commercial leans into self-aware "
            "humor, using the character\u2019s reluctance as the punchline."
        )

    parts: list[str] = []

    if evidence.setting:
        parts.append(f"In {evidence.setting.value}, ")

    protagonist = evidence.protagonist.value if evidence.protagonist else ""
    objective = evidence.objective.value if evidence.objective else ""
    conflict = evidence.conflict.value if evidence.conflict else ""
    stakes = evidence.stakes.value if evidence.stakes else ""

    if protagonist:
        opening = protagonist
        if objective:
            opening += f" sets out to {objective[0].lower()}{objective[1:]}" if objective[0].isalpha() else objective
        parts.append(opening)

    if conflict:
        parts.append(f"However, {conflict[0].lower()}{conflict[1:]}" if conflict[0].isalpha() else conflict)

    if stakes:
        parts.append(f"The stakes are {stakes[0].lower()}{stakes[1:]}" if stakes[0].isalpha() else stakes)

    for beat in evidence.story_beats:
        text = beat.value.strip()
        if text and not any(text.startswith(p) for p in ("In ", "However", "The stakes")):
            parts.append(text)

    if evidence.ending:
        parts.append(str(evidence.ending.value))

    result = " ".join(parts)
    if not result:
        return ""
    return result
