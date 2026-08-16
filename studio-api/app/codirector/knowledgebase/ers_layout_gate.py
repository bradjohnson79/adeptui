"""Lightweight ERS layout gate.

A result that is four similar variations, a single beauty still, a character
sheet, or a prop sheet is ERS_LAYOUT_NONCOMPLIANT.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ERS_LAYOUT_NONCOMPLIANT = "ERS_LAYOUT_NONCOMPLIANT"

_CHARACTER_SHEET_RE = re.compile(
    r"(?is)(front\s*/\s*side\s*/\s*back|full[- ]body\s+front|full[- ]body\s+side|"
    r"full[- ]body\s+back|head[- ]and[- ]shoulders\s+close[- ]?up|"
    r"four[- ]panel\s+character|character\s+turnaround|four[- ]view\s+character)"
)
_VARIATION_RE = re.compile(
    r"(?is)(four[- ]image variation|four variations|variation grid|mood board|"
    r"four different looks|four cinematic povs?)"
)
_PROP_SHEET_RE = re.compile(
    r"(?is)(?<!not a )(?<!not an )(prop sheet|four views of (an |the )?object|product turnaround)"
)
_SINGLE_BEAUTY_RE = re.compile(
    r"(?is)(single cinematic still|single beauty|hero still only|one wide beauty shot)"
)

# Tall single-pose / poster frames are not production-design boards.
_SINGLE_BEAUTY_ASPECT_MIN = 1.35


def assess_ers_layout(
    *,
    prompt: str | None = None,
    purpose: str | None = None,
    layout: str | None = None,
    path: str | Path | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Honest lightweight gate. Does not invent a vision model."""
    out: dict[str, Any] = {
        "ok": True,
        "compliant": None,
        "verified": False,
        "layoutNoncompliant": False,
        "code": None,
        "note": "ERS layout not verified",
        "width": None,
        "height": None,
    }
    purpose_l = str(purpose or "").strip()
    layout_l = str(layout or "").strip().lower()
    text = str(prompt or "")

    if purpose_l in {"character_sheet", "project_prop", "prop_sheet"} or layout_l == "four_view":
        return _fail(out, "character or prop sheet purpose/layout is not an ERS")
    if _CHARACTER_SHEET_RE.search(text):
        return _fail(out, "character-sheet Front/Side/Back/Close-Up language")
    if _VARIATION_RE.search(text):
        return _fail(out, "four similar variations / variation grid")
    if _PROP_SHEET_RE.search(text):
        return _fail(out, "prop sheet layout")
    if _SINGLE_BEAUTY_RE.search(text):
        return _fail(out, "single beauty still")

    w, h = width, height
    if path:
        pth = Path(path)
        if pth.is_file():
            try:
                from PIL import Image

                with Image.open(pth) as im:
                    w, h = int(im.size[0]), int(im.size[1])
            except Exception:
                w, h = w, h
    if w and h and int(w) > 0 and int(h) > 0:
        out["width"] = int(w)
        out["height"] = int(h)
        aspect = float(h) / float(w)
        if aspect >= _SINGLE_BEAUTY_ASPECT_MIN:
            return _fail(out, "single beauty / tall portrait, not a production-design board")

    if purpose_l == "environment_reference_sheet" or layout_l == "production_ers":
        out["compliant"] = True
        out["note"] = "prompt/purpose looks like a production ERS (pixel layout not vision-verified)"
        return out
    return out


def _fail(out: dict[str, Any], note: str) -> dict[str, Any]:
    out["ok"] = False
    out["compliant"] = False
    out["verified"] = True
    out["layoutNoncompliant"] = True
    out["code"] = ERS_LAYOUT_NONCOMPLIANT
    out["note"] = f"{ERS_LAYOUT_NONCOMPLIANT}: {note}"
    return out
