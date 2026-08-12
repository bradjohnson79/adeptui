from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..story_model import StoryEvidenceModel
from ._shared import (
    _COMMON_CAPITALIZED,
    _extract_names,
    _has_instruction_contamination,
    _has_meta_commentary,
)
from ..sanitize import is_contamination_free

_META_COMMENTARY_LOG_RE = re.compile(
    r"\b(?:here's|this is)\s+(?:a |the )?(?:possible |suggested |draft )?(?:logline|summary)\b"
    r"|\bI think\b"
    r"|\bas an AI\b"
    r"|\bI suggest\b",
    re.I,
)

_SENTENCE_BREAK_RE = re.compile(r"\. [A-Z]")


@dataclass
class LoglineValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _is_single_sentence(text: str) -> bool:
    return len(_SENTENCE_BREAK_RE.findall(text)) == 0


def _build_known_names(evidence: StoryEvidenceModel) -> set[str]:
    known: set[str] = set()
    if evidence.protagonist and evidence.protagonist.value:
        known.add(evidence.protagonist.value)
    for c in evidence.primary_characters:
        if c.value:
            known.add(c.value)
    if evidence.setting and evidence.setting.value:
        known.add(evidence.setting.value)
    return known


def validate_logline(text: str, evidence: StoryEvidenceModel) -> LoglineValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not text.strip():
        errors.append("Logline is empty")

    words = text.split()
    if len(words) > 50:
        errors.append("Logline exceeds 50 words")

    if "\n" in text or "\r" in text or "•" in text or "\n- " in text:
        errors.append("Logline must be a single sentence")

    if not is_contamination_free(text):
        errors.append("Logline contains instruction text")

    if _META_COMMENTARY_LOG_RE.search(text):
        errors.append("Logline contains meta commentary")

    if not _is_single_sentence(text):
        errors.append("Logline must be a single sentence")

    known = _build_known_names(evidence)
    names_found = _extract_names(text)
    unknown = names_found - known - _COMMON_CAPITALIZED
    for name in sorted(unknown):
        warnings.append(f"Unsupported name: '{name}'")

    return LoglineValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def compile_logline(evidence: StoryEvidenceModel) -> str:
    protagonist = evidence.protagonist.value if evidence.protagonist else ""
    premise = evidence.premise.value if evidence.premise else ""
    conflict = evidence.conflict.value if evidence.conflict else ""
    objective = evidence.objective.value if evidence.objective else ""
    setting = evidence.setting.value if evidence.setting else ""
    stakes = evidence.stakes.value if evidence.stakes else ""

    if premise:
        core = premise.strip().rstrip(".")
        if protagonist and protagonist.lower() not in core.lower():
            core = f"{protagonist} {core[0].lower() + core[1:]}"
        if conflict and conflict.lower() not in core.lower():
            core = f"{core}, {conflict[0].lower() + conflict[1:]}"
        if stakes and stakes.lower() not in core.lower():
            core = f"{core}, as {stakes[0].lower() + stakes[1:]}"
        if not core.endswith("."):
            core += "."
        result = core
    elif protagonist:
        if objective:
            if setting:
                result = f"In {setting}, {protagonist} must {objective[0].lower() + objective[1:]}."
            else:
                result = f"{protagonist} must {objective[0].lower() + objective[1:]}."
            if stakes and stakes.lower() not in result.lower():
                result = result.rstrip(".") + f", as {stakes[0].lower() + stakes[1:]}."
        elif conflict:
            if setting:
                result = f"In {setting}, {protagonist} {conflict[0].lower() + conflict[1:]}."
            else:
                result = f"{protagonist} {conflict[0].lower() + conflict[1:]}."
            if stakes and stakes.lower() not in result.lower():
                result = result.rstrip(".") + f", as {stakes[0].lower() + stakes[1:]}."
        else:
            if setting:
                result = f"In {setting}, {protagonist}."
            else:
                result = f"{protagonist}."
        result = result.strip()
    else:
        return ""

    vr = validate_logline(result, evidence)
    if not vr.valid:
        return ""

    return result
