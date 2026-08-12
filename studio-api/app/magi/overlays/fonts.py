"""Curated MAGI font registry — no remote fetch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[4]
_FONTS = _REPO / "config" / "magi" / "fonts.json"


def load_font_registry() -> dict[str, Any]:
    if not _FONTS.is_file():
        return {
            "schemaVersion": 1,
            "fonts": [
                {
                    "id": "dejavu-sans",
                    "family": "DejaVu Sans",
                    "cssFamily": '"DejaVu Sans", sans-serif',
                    "pillowNames": ["DejaVuSans"],
                    "weights": [400, 700],
                }
            ],
            "defaultFontId": "dejavu-sans",
            "remoteFetchForbidden": True,
        }
    return json.loads(_FONTS.read_text(encoding="utf-8"))


def font_ids() -> set[str]:
    reg = load_font_registry()
    return {str(f.get("id")) for f in reg.get("fonts") or [] if f.get("id")}


def resolve_font(font_id: str | None) -> dict[str, Any]:
    reg = load_font_registry()
    fonts = {str(f["id"]): f for f in reg.get("fonts") or [] if f.get("id")}
    if font_id and font_id in fonts:
        return {"found": True, "font": fonts[font_id], "substituted": False}
    default_id = reg.get("defaultFontId") or "dejavu-sans"
    return {
        "found": False,
        "font": fonts.get(default_id) or next(iter(fonts.values()), {}),
        "substituted": True,
        "requested": font_id,
    }
