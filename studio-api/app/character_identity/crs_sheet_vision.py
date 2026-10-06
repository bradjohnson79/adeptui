"""Interpret a Character Reference Sheet from pixels — not from filename or prose.

Vision here is for Co-Director understanding. It is not identity authority
for video generation. The sheet image remains the authority.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

SHEET_VISION_INSTRUCTIONS = """You are inspecting a character reference sheet image.

This image may be a labeled multi-panel turnaround sheet or a stitched
multi-view sheet with no formal labels. In either case, treat every panel
as a different view of ONE character — not several different people.
If the panels have no printed Front/Side/Back labels, layout is
stitched_multiview. Labeled turnaround sheets are structured_labeled_sheet.

Do not use the filename, folder name, or any stored character biography.
Use only what is visible in the image.

Return JSON only with these keys:
{
  "one_identity": true or false,
  "panel_count_estimate": number,
  "layout": "structured_labeled_sheet" or "stitched_multiview" or "single_view" or "unknown",
  "identity": {
    "apparent_age": "",
    "sex_or_gender_presentation": "",
    "face_shape": "",
    "eye_appearance": "",
    "eye_color": "",
    "skin_tone": "",
    "ears": "",
    "hairstyle": "",
    "hair_color": "",
    "body_proportions": "",
    "distinguishing_marks": ""
  },
  "wardrobe": {
    "top": "",
    "bottom": "",
    "footwear": "",
    "jewelry_or_accessories": "",
    "distinctive_materials": ""
  },
  "persistent_identity_features": [],
  "multi_angle_consistency": "",
  "notes": ""
}

Rules:
- Empty string if unknown. Do not invent.
- one_identity is true only when the panels clearly show the same person.
- persistent_identity_features lists only traits visible across multiple views.
- Do not write personality, backstory, or relationships.
No markdown.
"""


def is_likely_reference_sheet(path: str | Path) -> bool:
    """Cheap layout hint. Vision still decides one-identity vs many people."""
    try:
        from .crs_single_figure import detect_collage_layout

        return bool(detect_collage_layout(path))
    except Exception:
        return False


async def interpret_reference_sheet(
    path: str | Path,
    *,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Run Co-Director vision on a sheet. Never invents a pass."""
    from ..codirector.vision.vision_review import chat_vision

    pth = Path(path)
    if not pth.is_file():
        return {"ok": False, "error": "sheet_missing", "path": str(pth)}
    response = await chat_vision(
        instructions=SHEET_VISION_INSTRUCTIONS,
        image_paths=[pth],
        model_id=model_id or "",
        temperature=0.0,
    )
    if not response.get("ok"):
        return {
            "ok": False,
            "error": response.get("error") or response.get("reason") or "vision_failed",
            "provider": response.get("provider"),
            "model": response.get("model"),
        }
    facts = _parse_json(str(response.get("output") or ""))
    return {
        "ok": True,
        "provider": response.get("provider"),
        "model": response.get("model"),
        "raw": response.get("output"),
        "facts": facts,
        "identity_authority": "reference_image",
        "used_for_video_prompt": False,
    }


def _parse_json(text: str) -> dict[str, Any]:
    import json
    import re

    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return {"notes": raw[:800]}
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {"notes": raw[:800]}
        except json.JSONDecodeError:
            return {"notes": raw[:800]}
