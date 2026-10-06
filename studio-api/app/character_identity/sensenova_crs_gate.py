"""SenseNova native production CRS layout gate.

This is not the Flux/Qwen 2x2 four-view checker. A Korri-style production
poster is landscape and information-dense. A square unlabeled 2x2 dump fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..image_prompting.sensenova.crs_compiler import SENSENOVA_CRS_LAYOUT


def assess_native_production_crs(path: str | Path | None) -> dict[str, Any]:
    """Heuristic production-sheet gate. Full visual gold-standard is Phase 6."""
    out: dict[str, Any] = {
        "ok": False,
        "layout": SENSENOVA_CRS_LAYOUT,
        "layoutVerified": False,
        "layoutNoncompliant": True,
        "code": "CRS_LAYOUT_NONCOMPLIANT",
        "note": "Native production CRS was not readable.",
    }
    if not path:
        return out
    p = Path(path)
    if not p.is_file():
        out["note"] = "Native production CRS file is missing."
        return out
    try:
        from PIL import Image

        with Image.open(p) as im:
            width, height = im.size
    except Exception:
        out["note"] = "Native production CRS could not be opened."
        return out
    if width < 1024 or height < 768:
        out["note"] = "Native production CRS is too small to hold a readable sheet."
        return out
    ratio = width / float(height)
    if abs(ratio - 1.0) < 0.08:
        out["note"] = (
            "Result looks like a square 2x2 dump. SenseNova CRS must be a "
            "landscape production sheet (Front + 3/4 + Side + Back, close-up, details)."
        )
        return out
    if ratio < 1.2:
        out["note"] = "Native production CRS must be a landscape composed page, not a portrait tile."
        return out
    out.update(
        {
            "ok": True,
            "layoutVerified": True,
            "layoutNoncompliant": False,
            "code": "PASS",
            "note": "Landscape production-sheet geometry accepted. Gold-standard visual review is still required.",
            "width": width,
            "height": height,
        }
    )
    return out
