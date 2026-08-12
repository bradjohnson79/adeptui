from __future__ import annotations

import re

_INSTRUCTION_PATTERN = re.compile(
    r"\b(?:here's|this is)\s+(?:a |the )?(?:possible |suggested |draft )?"
    r"(?:logline|summary|synopsis|description)\b|\bI think\b|\bas an AI\b|\bI suggest\b",
    re.I,
)

_META_COMMENTARY_RE = re.compile(
    r"\b(this works because|the (?:story|summary) (?:effectively|successfully|does a good job)|"
    r"I've (?:crafted|written|created)|Let me (?:explain|break down))\b",
    re.I,
)

_PADDING_RE = re.compile(
    r"\bin conclusion\b|\bto summarize\b|\bin summary\b|\bas we have seen\b", re.I
)

_PRODUCTION_ADVICE_RE = re.compile(
    r"\bthis works because\b|\bthe (?:story|summary|logline) (?:effectively|successfully)\b",
    re.I,
)

_COMMON_CAPITALIZED = {
    "The", "It", "I", "This", "That", "We", "They", "She", "He", "You",
    "My", "Our", "Their", "His", "Her", "Its", "And", "But", "Or", "For",
    "Nor", "Yet", "So", "A", "An", "Is", "Are", "Was", "Were", "Be",
    "Been", "Being", "Have", "Has", "Had", "Do", "Does", "Did", "Will",
    "Would", "Can", "Could", "Shall", "Should", "May", "Might", "Must",
    "Not", "No", "Yes", "Also", "However", "Then", "Now", "Here", "There",
    "When", "Where", "Why", "How", "What", "Which", "Who", "Whom", "Whose",
    "If", "Because", "Although", "While", "Since", "Until", "After",
    "Before", "During", "Through", "About", "Into", "Over", "Between",
    "Under", "Again", "Further", "Once", "Soon", "Still", "Yet",
    "Mid", "Non", "Pre", "Post", "Anti", "Semi", "Sub", "Super",
}


def _has_instruction_contamination(text: str) -> bool:
    from ..sanitize import is_contamination_free

    return not is_contamination_free(text)


def _has_meta_commentary(text: str) -> bool:
    return bool(_META_COMMENTARY_RE.search(text))


def _has_padding(text: str) -> bool:
    return bool(_PADDING_RE.search(text))


def _has_production_advice(text: str) -> bool:
    return bool(_PRODUCTION_ADVICE_RE.search(text))


def _extract_names(text: str) -> set[str]:
    return set(re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text))


def _has_unsupported_names(text: str, known_names: set[str]) -> bool:
    names = _extract_names(text)
    unknown = names - known_names
    return bool(unknown - _COMMON_CAPITALIZED)
