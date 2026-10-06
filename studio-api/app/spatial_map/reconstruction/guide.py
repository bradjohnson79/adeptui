"""Deterministic structural guide raster — PIL/numpy, no second floorplan model.

Guide is geometric authority for the render only. It is not canonical map
truth until the Atlas visual gate passes.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .contracts import SpatialReconstructionPacket

GUIDE_TAG = "spatial_structural_guide"
VALUE_FLOOR = 0
VALUE_WALL = 1
VALUE_OPENING = 2
VALUE_UNKNOWN = 3

FLOOR_RGB = (48, 48, 56)
WALL_RGB = (214, 214, 222)
OPENING_RGB = (72, 176, 96)
UNKNOWN_RGB = (148, 92, 48)


def guide_value_grid(packet: SpatialReconstructionPacket) -> Any:
    import numpy as np

    w = max(1, int(packet.layout.widthCells))
    d = max(1, int(packet.layout.depthCells))
    grid = np.full((d, w), VALUE_FLOOR, dtype=np.uint8)
    grid[0, :] = VALUE_WALL
    grid[-1, :] = VALUE_WALL
    grid[:, 0] = VALUE_WALL
    grid[:, -1] = VALUE_WALL
    for feature in packet.features:
        if feature.cellColumn is None or feature.cellRow is None:
            continue
        col = int(feature.cellColumn)
        row = int(feature.cellRow)
        if 0 <= row < d and 0 <= col < w:
            grid[row, col] = VALUE_OPENING if feature.type in {"opening", "door"} else VALUE_FLOOR
    if packet.unknownRegions and packet.layout.environmentType in {"exterior", "uncertain"}:
        mid = max(1, d // 4)
        grid[:mid, :] = np.where(grid[:mid, :] == VALUE_FLOOR, VALUE_UNKNOWN, grid[:mid, :])
    return grid


def rasterize_guide(packet: SpatialReconstructionPacket, *, cell_px: int = 32) -> bytes:
    from PIL import Image
    import numpy as np

    grid = guide_value_grid(packet)
    palette = {
        VALUE_FLOOR: FLOOR_RGB,
        VALUE_WALL: WALL_RGB,
        VALUE_OPENING: OPENING_RGB,
        VALUE_UNKNOWN: UNKNOWN_RGB,
    }
    h, w = int(grid.shape[0]), int(grid.shape[1])
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for value, color in palette.items():
        rgb[grid == value] = color
    img = Image.fromarray(rgb)
    size = (max(64, w * cell_px), max(64, h * cell_px))
    img = img.resize(size, Image.Resampling.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def persist_guide_asset(
    db: Session,
    packet: SpatialReconstructionPacket,
) -> str:
    from uuid import uuid4

    from ...config import settings
    from ...db import Asset, Project

    png = rasterize_guide(packet)
    parent = packet.sourceAssetIds[0] if packet.sourceAssetIds else ""
    project = db.get(Project, packet.projectId) if db is not None else None
    if project is None:
        raise RuntimeError("Could not save the structural layout image.")
    asset_id = str(uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / packet.projectId
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}.png"
    dest.write_bytes(png)
    asset = Asset(
        id=asset_id,
        project_id=packet.projectId,
        tag=GUIDE_TAG,
        kind="image",
        filename=f"{GUIDE_TAG}.png",
        path=str(dest),
        comfy_name="",
        parent_asset_id=parent or None,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    try:
        from ...project_library.service import assign_asset

        assign_asset(db, asset, classified_by="spatial_reconstruction")
    except Exception:
        pass
    packet.guideAssetId = asset_id
    return asset_id


def guide_corresponds_to_packet(png_bytes: bytes, packet: SpatialReconstructionPacket) -> bool:
    """Assert geometry correspondence, not merely that a file exists."""
    from PIL import Image
    import numpy as np

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    arr = np.asarray(img)
    w = max(1, int(packet.layout.widthCells))
    d = max(1, int(packet.layout.depthCells))
    expected = guide_value_grid(packet)
    cell_h = arr.shape[0] // d
    cell_w = arr.shape[1] // w
    if cell_h < 1 or cell_w < 1:
        return False
    for row in range(d):
        for col in range(w):
            y = row * cell_h + cell_h // 2
            x = col * cell_w + cell_w // 2
            pixel = tuple(int(v) for v in arr[y, x])
            value = int(expected[row, col])
            target = {
                VALUE_FLOOR: FLOOR_RGB,
                VALUE_WALL: WALL_RGB,
                VALUE_OPENING: OPENING_RGB,
                VALUE_UNKNOWN: UNKNOWN_RGB,
            }[value]
            if sum(abs(a - b) for a, b in zip(pixel, target)) > 30:
                return False
    return True
