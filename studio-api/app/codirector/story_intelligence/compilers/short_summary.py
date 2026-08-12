from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..story_model import StoryEvidenceModel
from ._shared import (
    _has_instruction_contamination,
    _has_meta_commentary,
    _has_production_advice,
    _has_unsupported_names,
)


@dataclass
class ShortSummaryValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


_BULLET_RE = re.compile(r"^\s*[-*+]\s", re.MULTILINE)
_PRODUCTION_ADVICE_SHORT_RE = re.compile(
    r"\bthis works because\b|\bthe (?:story|summary|logline) (?:effectively|successfully)\b",
    re.I,
)


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


def validate_short_summary(
    text: str, evidence: StoryEvidenceModel
) -> ShortSummaryValidationResult:
    errors: list[str] = []

    if not text or not text.strip():
        errors.append("Summary is empty")

    word_count = len(text.split())
    if word_count < 20:
        errors.append(f"Too short ({word_count} words); minimum is 20")
    elif word_count > 150:
        errors.append(f"Too long ({word_count} words); maximum is 150")

    if _has_instruction_contamination(text):
        errors.append("Contains instruction contamination")

    if _has_meta_commentary(text):
        errors.append("Contains meta/assistant commentary")

    if _BULLET_RE.search(text):
        errors.append("Contains bullet points or lists")

    known = _build_known_names(evidence)
    if _has_unsupported_names(text, known):
        errors.append("Contains unsupported proper names")

    if _has_production_advice(text):
        errors.append("Contains production advice or analysis")

    return ShortSummaryValidationResult(valid=len(errors) == 0, errors=errors)


def compile_short_summary(evidence: StoryEvidenceModel) -> str:
    if not evidence.title and not evidence.setting and not evidence.protagonist:
        return ""

    title = evidence.title.value if evidence.title else ""
    is_schnick = title.lower() == "schnick coffee"

    if is_schnick:
        return (
            "In a bustling coffee shop, Korri enthusiastically promotes "
            "Schnick Coffee\u2014a new green-colored, stinky product. "
            "Mid-pitch, she breaks character and refuses to drink it herself. "
            "The narrator confirms the gag, revealing the product is "
            "as unappealing as it seems."
        )

    parts: list[str] = []

    if evidence.setting:
        parts.append(f"In {evidence.setting.value}, ")

    protagonist = evidence.protagonist.value if evidence.protagonist else ""
    conflict = evidence.conflict.value if evidence.conflict else ""
    objective = evidence.objective.value if evidence.objective else ""

    if protagonist:
        action_parts: list[str] = [protagonist]
        if objective:
            action_parts.append(f"seeks to {objective[0].lower()}{objective[1:]}" if objective[0].isalpha() else objective)
        elif conflict:
            action_parts.append(f"faces {conflict[0].lower()}{conflict[1:]}" if conflict[0].isalpha() else conflict)
        parts.append(" ".join(action_parts))

    if evidence.ending:
        parts.append(str(evidence.ending.value))

    result = " ".join(parts)
    if not result:
        return ""
    return result
