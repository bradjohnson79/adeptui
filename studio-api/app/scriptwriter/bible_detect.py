"""Detect new entities for Production Bible proposals — never silent write."""

from __future__ import annotations

import re
from typing import Any

from .models import ScriptDocument

_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b")


def detect_entities(doc: ScriptDocument, *, known_names: set[str] | None = None) -> list[dict[str, Any]]:
    known = {n.upper() for n in (known_names or set())}
    found: dict[str, dict[str, Any]] = {}
    for el in doc.elements:
        if el.type == "character":
            name = (el.text or "").strip()
            key = name.upper()
            if name and key not in known:
                found[key] = {
                    "kind": "character",
                    "name": name.title() if name.isupper() else name,
                    "elementId": el.id,
                    "status": "detected_new",
                }
        if el.type == "scene_heading":
            text = el.text or ""
            # location between INT./EXT. and -
            m = re.match(
                r"^(?:INT\.|EXT\.|INT\./EXT\.|EXT\./INT\.|I/E\.)\s*(.+?)\s*-\s*",
                text,
                re.I,
            )
            if m:
                loc = m.group(1).strip()
                key = loc.upper()
                if loc and key not in known and key not in found:
                    found[key] = {
                        "kind": "location",
                        "name": loc.title(),
                        "elementId": el.id,
                        "status": "detected_new",
                    }
    return list(found.values())
