from __future__ import annotations

import json
from typing import Any

from .schemas import SpatialMap


def parse_spatial_map(raw: str | None) -> SpatialMap:
    if not raw:
        return SpatialMap()
    try:
        data = json.loads(raw)
        return SpatialMap.model_validate(data)
    except Exception:
        return SpatialMap()


def spatial_prompt_notes(spatial: SpatialMap) -> str:
    bits: list[str] = []
    if spatial.notes.strip():
        bits.append(spatial.notes.strip())
    cams = [p for p in spatial.points if p.kind == "camera"]
    props = [p for p in spatial.points if p.kind == "prop"]
    walls = [p for p in spatial.points if p.kind == "wall"]
    if cams:
        labels = ", ".join(f"{c.label or c.id} at ({c.x:.0f},{c.y:.0f})" for c in cams)
        bits.append(f"cameras: {labels}")
    if props:
        labels = ", ".join(p.label or p.id for p in props)
        bits.append(f"props: {labels}")
    if walls:
        bits.append(f"{len(walls)} wall markers for room layout")
    return "; ".join(bits)


def auto_tags_from_spatial(spatial: SpatialMap) -> dict[str, Any]:
    """Return suggested @tags derived from spatial map points with assets."""
    tags: dict[str, Any] = {}
    if spatial.background_asset_id:
        tags["set"] = spatial.background_asset_id
        tags["map"] = spatial.background_asset_id
    for p in spatial.points:
        if p.asset_id and p.label:
            safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in p.label.lower())
            if safe:
                tags[safe] = p.asset_id
    return tags
