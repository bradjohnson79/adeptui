"""Fountain import/export for M4.7."""

from __future__ import annotations

import re
import uuid
from typing import Optional

from .models import ScriptElement, ScriptElementType

_SCENE_RE = re.compile(r"^(INT\.|EXT\.|INT\./EXT\.|EXT\./INT\.|I/E\.)\s+", re.I)
_TRANSITION_RE = re.compile(r"^(FADE OUT|FADE IN|CUT TO|DISSOLVE TO|SMASH CUT TO|MATCH CUT TO).*:?\s*$", re.I)
_CHARACTER_RE = re.compile(r"^[A-Z][A-Z0-9 \-'.]{1,39}$")
_PAREN_RE = re.compile(r"^\(.*\)$")


def parse_fountain(text: str) -> list[ScriptElement]:
    lines = (text or "").replace("\r\n", "\n").split("\n")
    elements: list[ScriptElement] = []
    order = 0
    i = 0
    pending_character: Optional[str] = None

    def add(etype: ScriptElementType, content: str, **meta: object) -> None:
        nonlocal order
        el = ScriptElement(
            id=str(uuid.uuid4()),
            type=etype,
            text=content.strip(),
            order=order,
            metadata={k: v for k, v in meta.items() if v is not None},
        )
        if etype == "character":
            el.metadata["speaker"] = content.strip()
        elements.append(el)
        order += 1

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line:
            pending_character = None
            continue
        if line.startswith("/*") or line.startswith("[["):
            add("note", line.strip("/* []"))
            continue
        if line.startswith("#"):
            add("section", line.lstrip("#").strip())
            continue
        if line.upper().startswith("ACT ") or line.upper() in {"TEASER", "TAG"}:
            add("act_break", line)
            continue
        if _SCENE_RE.match(line):
            add("scene_heading", line.upper())
            pending_character = None
            continue
        if _TRANSITION_RE.match(line) or (line.endswith("TO:") and line.isupper()):
            add("transition", line.upper())
            pending_character = None
            continue
        if _PAREN_RE.match(line) and pending_character:
            add("parenthetical", line)
            continue
        if _CHARACTER_RE.match(line) and not line.endswith("."):
            add("character", line)
            pending_character = line
            continue
        if pending_character:
            add("dialogue", line)
            # peek: if next is blank, clear character
            if i < len(lines) and not lines[i].strip():
                pending_character = None
            continue
        add("action", line)

    if not elements:
        add("general", text or "")
    return elements


def to_fountain(elements: list[ScriptElement], *, title: str = "") -> str:
    parts: list[str] = []
    if title:
        parts.append(f"Title: {title}")
        parts.append("")
    for el in sorted(elements, key=lambda e: e.order):
        if el.omitted:
            continue
        t = el.text or ""
        if el.type == "scene_heading":
            parts.append(t.upper())
            parts.append("")
        elif el.type == "action":
            parts.append(t)
            parts.append("")
        elif el.type == "character":
            parts.append(t.upper())
        elif el.type == "parenthetical":
            parts.append(t if t.startswith("(") else f"({t})")
        elif el.type == "dialogue":
            parts.append(t)
            parts.append("")
        elif el.type == "transition":
            parts.append(t.upper())
            parts.append("")
        elif el.type == "section":
            parts.append(f"# {t}")
            parts.append("")
        elif el.type == "act_break":
            parts.append(t.upper())
            parts.append("")
        elif el.type == "note":
            parts.append(f"[[{t}]]")
            parts.append("")
        else:
            parts.append(t)
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"
