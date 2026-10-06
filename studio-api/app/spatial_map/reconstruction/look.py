"""Spatial Atlas Look — appearance only. Never overrides reconstructed topology."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

AtlasStyle = Literal[
    "auto_match_source",
    "realistic",
    "cinematic",
    "architectural",
    "clean_concept",
    "blueprint",
    "stylized",
]
AtlasDetail = Literal["low", "balanced", "high"]
AtlasSourceStrength = Literal["low", "balanced", "strong"]
AtlasPresentation = Literal["roofless", "cutaway", "floor_plan"]
AtlasLighting = Literal["match_source", "neutral", "bright_planning", "cinematic"]

DEFAULT_LOOK: dict[str, Any] = {
    "style": "auto_match_source",
    "detail": "balanced",
    "sourceAppearance": "balanced",
    "presentation": "roofless",
    "lighting": "match_source",
    "showGrid": False,
}


class SpatialAtlasLook(BaseModel):
    style: AtlasStyle = "auto_match_source"
    detail: AtlasDetail = "balanced"
    sourceAppearance: AtlasSourceStrength = "balanced"
    presentation: AtlasPresentation = "roofless"
    lighting: AtlasLighting = "match_source"
    showGrid: bool = False


def normalize_atlas_look(raw: dict[str, Any] | None) -> SpatialAtlasLook:
    data = dict(DEFAULT_LOOK)
    if isinstance(raw, dict):
        data.update({k: v for k, v in raw.items() if k in DEFAULT_LOOK})
    return SpatialAtlasLook.model_validate(data)


def look_prompt_suffix(look: SpatialAtlasLook) -> str:
    """Creator appearance only. Does not describe camera invention or new rooms."""
    parts: list[str] = []
    style_copy = {
        "auto_match_source": "Match the materials and architecture of the source location.",
        "realistic": "Realistic physical materials and lighting.",
        "cinematic": "Cinematic grade, still a readable planning Atlas.",
        "architectural": "Architectural presentation: clear walls, floors, and openings.",
        "clean_concept": "Clean concept-art surfaces, keep the same layout.",
        "blueprint": "Technical blueprint look, keep the same layout.",
        "stylized": "Stylized surfaces, keep the same layout.",
    }
    parts.append(style_copy.get(look.style, style_copy["auto_match_source"]))
    if look.detail == "low":
        parts.append("Simple surfaces, less decorative clutter.")
    elif look.detail == "high":
        parts.append("Rich surface detail on floors and walls.")
    strength = {
        "low": "Borrow only a little color from the source.",
        "balanced": "Keep source materials visible without copying the camera angle.",
        "strong": "Strong source materials and lighting character. Do not copy the source perspective.",
    }
    parts.append(strength[look.sourceAppearance])
    if look.presentation == "cutaway":
        parts.append("Cutaway building so interior rooms stay visible from above.")
    elif look.presentation == "floor_plan":
        parts.append("Clean floor-plan graphic, still the same rooms and openings.")
    else:
        parts.append("Roofless top-down view.")
    light = {
        "match_source": "Lighting character matches the source.",
        "neutral": "Neutral even lighting for planning.",
        "bright_planning": "Bright even planning light. Do not hide walls or doors.",
        "cinematic": "Cinematic light that still keeps the map readable.",
    }
    parts.append(light[look.lighting])
    if look.showGrid:
        parts.append("Subtle 1-meter planning grid on the finished overhead Atlas only.")
    return " ".join(parts)


def interpret_atlas_look_utterance(text: str, current: dict[str, Any] | None = None) -> SpatialAtlasLook:
    """Map creator language onto the same Look object the UI uses."""
    look = normalize_atlas_look(current)
    blob = (text or "").lower()
    if re.search(r"blueprint|technical drawing", blob):
        look.style = "blueprint"
    elif re.search(r"architect", blob):
        look.style = "architectural"
    elif re.search(r"concept art", blob):
        look.style = "clean_concept"
    elif re.search(r"styliz", blob):
        look.style = "stylized"
    elif re.search(r"cinematic", blob) and "bright" not in blob:
        look.style = "cinematic"
    elif re.search(r"realistic|photoreal", blob):
        look.style = "realistic"
    elif re.search(r"match (the )?(source|corridor|location)|metallic appearance", blob):
        look.style = "auto_match_source"
        look.sourceAppearance = "strong"
    if re.search(r"less detail|simpler|low detail", blob):
        look.detail = "low"
    elif re.search(r"more detail|high detail", blob):
        look.detail = "high"
    if re.search(r"match .{0,24}(metal|material|appearance) closely|strong(er)? source", blob):
        look.sourceAppearance = "strong"
    elif re.search(r"less (source|reference)|weaker source", blob):
        look.sourceAppearance = "low"
    if re.search(r"brighten|brighter|planning (view|light)", blob):
        look.lighting = "bright_planning"
    elif re.search(r"neutral light", blob):
        look.lighting = "neutral"
    if re.search(r"floor plan", blob):
        look.presentation = "floor_plan"
    elif re.search(r"cutaway", blob):
        look.presentation = "cutaway"
    if re.search(r"show (the )?grid|1 ?m grid", blob):
        look.showGrid = True
    elif re.search(r"hide (the )?grid|no grid", blob):
        look.showGrid = False
    return look


def overlay_planning_grid(
    image_path: str,
    *,
    width_cells: int,
    depth_cells: int,
) -> bytes:
    """Draw a 1 m planning grid on a validated overhead Atlas. Never on a photo."""
    import io

    from PIL import Image, ImageDraw

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    cols = max(1, int(width_cells or 10))
    rows = max(1, int(depth_cells or 10))
    w, h = img.size
    color = (255, 255, 255)
    for i in range(cols + 1):
        x = int(round(i * (w - 1) / cols))
        draw.line([(x, 0), (x, h - 1)], fill=color, width=1)
    for j in range(rows + 1):
        y = int(round(j * (h - 1) / rows))
        draw.line([(0, y), (w - 1, y)], fill=color, width=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def persist_planning_grid_asset(
    db: Any,
    *,
    project_id: str,
    source_atlas_id: str,
    width_cells: int,
    depth_cells: int,
) -> str:
    """Save a 1 m grid overlay of a validated Atlas. Never applied to a failed photo."""
    from pathlib import Path
    from uuid import uuid4

    from ...config import settings
    from ...db import Asset

    parent = db.get(Asset, source_atlas_id)
    if parent is None or str(parent.project_id or "") != project_id or not parent.path:
        return source_atlas_id
    png = overlay_planning_grid(
        str(parent.path),
        width_cells=width_cells,
        depth_cells=depth_cells,
    )
    asset_id = str(uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}.png"
    dest.write_bytes(png)
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag="spatial_atlas_grid",
        kind="image",
        filename="spatial_atlas_grid.png",
        path=str(dest),
        comfy_name="",
        parent_asset_id=source_atlas_id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    try:
        from ...project_library.service import assign_asset

        assign_asset(db, asset, classified_by="spatial_atlas_grid")
    except Exception:
        pass
    return asset_id


def look_capability_notes(renderer: str) -> dict[str, Any]:
    """Which Look controls this renderer can honor."""
    if renderer in {"qwen2512", "qwen2512.atlas"}:
        return {
            "style": True,
            "detail": True,
            "sourceAppearance": True,
            "presentation": True,
            "lighting": True,
            "showGrid": True,
            "unsupported": [],
        }
    if "flux" in renderer.lower():
        return {
            "style": True,
            "detail": True,
            "sourceAppearance": True,
            "presentation": True,
            "lighting": True,
            "showGrid": True,
            "unsupported": [],
        }
    if "gpt" in renderer.lower():
        return {
            "style": True,
            "detail": True,
            "sourceAppearance": False,
            "presentation": True,
            "lighting": True,
            "showGrid": False,
            "unsupported": ["sourceAppearance", "showGrid"],
            "reason": "This engine cannot take the structural guide as a second image.",
        }
    return {
        "style": True,
        "detail": True,
        "sourceAppearance": False,
        "presentation": True,
        "lighting": True,
        "showGrid": False,
        "unsupported": ["sourceAppearance", "showGrid"],
    }
