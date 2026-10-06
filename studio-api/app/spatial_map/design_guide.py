"""Deterministic top-down structural guide from an Environment Design Packet.

Layout authority is the creator description / packet. This raster is not a
photograph and is not MoGe reconstruction. It tells a local image model the
camera (overhead) and the footprint.

Rendering is internal PIL (Apache-2.0 compatible stack). Maker.js is not used:
it is a JS CAD library and would add an unjustified frontend/runtime dependency
to a Python backend that already has a deterministic geometry renderer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from .layout_compiler import compile_spatial_layout, render_spatial_layout
from .scene_intent import EnvironmentDesignPacket, compile_environment_design, normalize_environment_class


FLOOR_RGB = (52, 56, 62)
WALL_RGB = (196, 200, 208)
OPENING_RGB = (64, 168, 96)
GUIDE_YELLOW = (232, 196, 48)
ELEVATOR_RGB = (88, 96, 112)
DESIGN_GUIDE_TAG = "spatial_design_guide"
APPEARANCE_PRIOR_TAG = "spatial_appearance_prior"


def rasterize_design_guide(
    packet: EnvironmentDesignPacket | dict[str, Any] | None,
    *,
    description: str = "",
    width: int = 1024,
    height: int = 1024,
    environment_class: str = "",
) -> bytes:
    """Paint a clean roofless footprint. No CAD text. No perspective."""
    if packet is None:
        packet = compile_environment_design(description, environment_class=environment_class)
    elif isinstance(packet, dict):
        packet = EnvironmentDesignPacket.model_validate(packet)
    env_class = normalize_environment_class(environment_class or packet.environmentClass)
    layout = compile_spatial_layout(packet, description=description, environment_class=env_class)
    return render_spatial_layout(layout, width=width, height=height)


def persist_design_guide_asset(
    db: Session | None,
    *,
    project_id: str,
    png: bytes,
    parent_asset_id: str = "",
) -> str:
    """Save the compiled structural guide so Qwen retries can reuse it."""
    if db is None:
        return ""
    from ..config import settings
    from ..db import Asset, Project

    project = db.get(Project, project_id)
    if project is None:
        return ""
    asset_id = str(uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}.png"
    dest.write_bytes(png)
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=DESIGN_GUIDE_TAG,
        kind="image",
        filename=f"{DESIGN_GUIDE_TAG}.png",
        path=str(dest),
        comfy_name="",
        parent_asset_id=parent_asset_id or None,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    try:
        from ..project_library.service import assign_asset

        assign_asset(db, asset, classified_by="spatial_layout_compiler")
    except Exception:
        pass
    return asset_id


def persist_appearance_prior_asset(
    db: Session | None,
    *,
    project_id: str,
    png: bytes,
    parent_asset_id: str = "",
) -> str:
    """Save a packet-derived material swatch. Not a location photograph."""
    if db is None:
        return ""
    from ..config import settings
    from ..db import Asset, Project

    project = db.get(Project, project_id)
    if project is None:
        return ""
    asset_id = str(uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}.png"
    dest.write_bytes(png)
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=APPEARANCE_PRIOR_TAG,
        kind="image",
        filename=f"{APPEARANCE_PRIOR_TAG}.png",
        path=str(dest),
        comfy_name="",
        parent_asset_id=parent_asset_id or None,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    try:
        from ..project_library.service import assign_asset

        assign_asset(db, asset, classified_by="spatial_layout_compiler")
    except Exception:
        pass
    return asset_id
