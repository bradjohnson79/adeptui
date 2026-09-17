"""Layer A user-request language that must never become ACTION copy."""

from __future__ import annotations

import re

FORBIDDEN_ACTION_PHRASES: tuple[str, ...] = (
    "i would like you",
    "i would like",
    "build a scene in timeline",
    "build a scene",
    "use the reference sheet",
    "prop reference sheet",
    "environment reference sheet",
    "character reference sheet",
    "runtime of 10 seconds",
    "frame ratio",
    "megapixels",
    "single batch",
    "this scene will be created",
    "using minimax",
    "using timeline",
)

_FORBIDDEN_RE = re.compile(
    "|".join(re.escape(phrase) for phrase in FORBIDDEN_ACTION_PHRASES),
    re.I,
)

_META_SENTENCE_RE = re.compile(
    r"(?:"
    r"i would like you to\b[^.!?]*[.!?]?"
    r"|build (?:this|a|the) scene\b[^.!?]*[.!?]?"
    r"|this scene will be created\b[^.!?]*[.!?]?"
    r"|we will (?:also )?use (?:the )?[^.!?]*reference sheet[^.!?]*[.!?]?"
    r"|using minimax\b[^.!?]*[.!?]?"
    r"|megapixels\b[^.!?]*[.!?]?"
    r"|frame ratio\b[^.!?]*[.!?]?"
    r"|single batch\b[^.!?]*[.!?]?"
    r")",
    re.I,
)


def contains_instruction_copy(text: str) -> bool:
    return bool(_FORBIDDEN_RE.search(text or ""))


def instruction_copy_hits(text: str) -> list[str]:
    blob = (text or "").lower()
    return [phrase for phrase in FORBIDDEN_ACTION_PHRASES if phrase in blob]


def strip_instruction_copy(text: str) -> str:
    cleaned = _META_SENTENCE_RE.sub(" ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")
    return cleaned
