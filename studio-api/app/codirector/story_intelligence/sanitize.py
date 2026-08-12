"""Instruction/content separation for story intelligence compilation.
Deterministic-first layer — splits instruction prefixes from story content
before evidence extraction, and validates output against contamination.
"""

from __future__ import annotations

import re
from typing import Tuple


_INSTRUCTION_PREFIX_RE = re.compile(
    r"^\s*(?:place|put|add|set|save|write|update|change|make|turn|use this as|enter this as)\b"
    r".*\b(?:in(?:to)? (?:the )?(?:short |long )?summary"
    r"|as (?:the )?logline"
    r"|to (?:the )?wiki"
    r"|as canon|as a fact|in the bible|in my notes"
    r")\s*[:\-–—]?\s*(.+)",
    re.I | re.DOTALL,
)

_EXPLICIT_WRITE_RE = re.compile(
    r"^\s*(?:make this (?:shorter|better|more concise)|improve this|refine the|update the|rewrite the)\b"
    r".*\b(summary|logline|synopsis|description|blurb)\b",
    re.I,
)

_CREATOR_EDIT_RE = re.compile(
    r"^\s*(?:short summary|logline|long summary|summary|synopsis|description)"
    r"\s+(?:should (?:say|be|read)|is|says)\b"
    r"(?:[^:\-–—]*[:\-–—])?\s*(.+)",
    re.I | re.DOTALL,
)

_INSTRUCTION_ONLY_RE = re.compile(
    r"^\s*(?:place|put|add|save|write|update|change)\b.*\b(summary|logline|synopsis|wiki|canon|bible)\s*[.:]?\s*$",
    re.I,
)

_CONTAMINATION_PATTERNS = [
    r"Place this in(?:to)? (?:the )?(?:short |long )?summary",
    r"Put this in(?:to)? (?:the )?(?:short |long )?summary",
    r"Add this to (?:the )?(?:short |long )?summary",
    r"Make this (?:shorter|better|more concise)",
    r"Rewrite the (?:summary|logline|synopsis)",
    r"Use this as (?:the )?logline",
    r"This would make a good",
]
_CONTAMINATION_COMBINED = re.compile("|".join(_CONTAMINATION_PATTERNS), re.I)


def separate_instruction(text: str) -> Tuple[str, str]:
    if not text:
        return ("", "")

    m = _CREATOR_EDIT_RE.search(text)
    if m:
        return ("", m.group(1).strip())

    m = _INSTRUCTION_PREFIX_RE.search(text)
    if m:
        instruction = text[: m.start(1)].strip()
        content = m.group(1).strip()
        return (instruction, content)

    m = _EXPLICIT_WRITE_RE.search(text)
    if m:
        colon_idx = text.find(":")
        semicolon_idx = text.find(";")
        dash_idx = text.find("—")
        if dash_idx == -1:
            dash_idx = text.find("–")
        if dash_idx == -1:
            dash_idx = text.find("-")

        split_idx = -1
        if colon_idx >= 0:
            split_idx = colon_idx
        elif semicolon_idx >= 0:
            split_idx = semicolon_idx
        elif dash_idx >= 0:
            split_idx = dash_idx

        if split_idx >= 0:
            instruction = text[:split_idx].strip()
            content = text[split_idx + 1 :].strip()
            return (instruction, content)

        return ("", text.strip())

    return ("", text.strip())


def is_instruction_text(text: str) -> bool:
    return bool(_INSTRUCTION_ONLY_RE.search(text.strip()))


def is_contamination_free(text: str) -> bool:
    return not bool(_CONTAMINATION_COMBINED.search(text))
