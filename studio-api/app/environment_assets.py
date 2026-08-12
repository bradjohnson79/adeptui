"""Register equirectangular panorama environment assets for Spatial Map backgrounds."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Optional

from PIL import Image
from sqlalchemy.orm import Session

from .config import settings
from .db import Asset


EQUIRECT_DEFAULT_SIZE = (2048, 1024)
PANORAMA_LIBRARY_KEY = "scenes.panoramas_360"
PANORAMA_KIND = "environment"
PANORAMA_TAXONOMY = "panorama_360"


def create_equirect_like_png(
    source_paths: list[Path] | Path,
    dest_path: Path,
    *,
    size: tuple[int, int] = EQUIRECT_DEFAULT_SIZE,
) -> Path:
    """Build a wide 2:1 equirect-like PNG from one or more source images (PIL stitch/resize)."""
    paths = [source_paths] if isinstance(source_paths, Path) else list(source_paths)
    if not paths:
        raise ValueError("At least one source image is required")
    for p in paths:
        if not Path(p).is_file():
            raise FileNotFoundError(f"Source image missing: {p}")

    tiles: list[Image.Image] = []
    for p in paths:
        tiles.append(Image.open(p).convert("RGB"))

    # Stitch horizontally; if only one image, mirror flanks for a non-trivial wide canvas.
    if len(tiles) == 1:
        base = tiles[0]
        left = base.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        right = base.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        strip = Image.new("RGB", (base.width * 3, base.height))
        strip.paste(left, (0, 0))
        strip.paste(base, (base.width, 0))
        strip.paste(right, (base.width * 2, 0))
    else:
        total_w = sum(t.width for t in tiles)
        max_h = max(t.height for t in tiles)
        strip = Image.new("RGB", (total_w, max_h))
        x = 0
        for t in tiles:
            y = (max_h - t.height) // 2
            strip.paste(t, (x, y))
            x += t.width

    out = strip.resize(size, Image.Resampling.LANCZOS)
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest_path, format="PNG")
    return dest_path


def register_equirect_panorama(
    db: Session,
    *,
    project_id: str,
    source_path: str | Path | None = None,
    source_paths: list[str | Path] | None = None,
    tag: str = "panorama_360",
    entity_name: str = "Equirect Panorama",
    entity_id: str | None = None,
    parent_asset_id: str | None = None,
    filename: str | None = None,
    size: tuple[int, int] = EQUIRECT_DEFAULT_SIZE,
    extra_meta: dict[str, Any] | None = None,
) -> Asset:
    """
    Create (if needed) and register an equirectangular panorama environment asset.

    - Writes under data/projects/{project_id}/assets/
    - kind = environment, library taxonomy scenes.panoramas_360
    - prompt_meta_json includes projection=equirectangular
    """
    paths: list[Path] = []
    if source_paths:
        paths = [Path(p) for p in source_paths]
    elif source_path:
        paths = [Path(source_path)]
    else:
        raise ValueError("source_path or source_paths required")

    dest_dir = settings.data_dir / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = filename or f"equirect_panorama_{uuid.uuid4().hex[:10]}.png"
    dest = dest_dir / dest_name

    create_equirect_like_png(paths, dest, size=size)

    meta: dict[str, Any] = {
        "projection": "equirectangular",
        "kind": PANORAMA_KIND,
        "taxonomy": PANORAMA_TAXONOMY,
        "op": "register_equirect_panorama",
        "width": size[0],
        "height": size[1],
        "parentAssetId": parent_asset_id,
        "sourceAssetPaths": [str(p) for p in paths],
        **(extra_meta or {}),
    }

    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag=(tag or "panorama_360")[:64],
        kind=PANORAMA_KIND,
        filename=dest.name,
        path=str(dest),
        comfy_name="",
        scope="project",
        labels_json=json.dumps(["environment", "panorama_360", "equirectangular"]),
        prompt_meta_json=json.dumps(meta),
        parent_asset_id=parent_asset_id,
    )
    db.add(asset)
    db.flush()

    try:
        from .project_library.service import assign_asset

        assign_asset(
            db,
            asset,
            system_key=PANORAMA_LIBRARY_KEY,
            entity_type="scene",
            entity_name=entity_name,
            entity_id=entity_id,
            classified_by="environment_assets",
            override=True,
            hints={"projection": "equirectangular", "systemKey": PANORAMA_LIBRARY_KEY},
        )
    except Exception:
        pass

    db.commit()
    db.refresh(asset)
    return asset


def find_equirect_panorama(
    db: Session,
    project_id: str,
    *,
    tag: Optional[str] = None,
) -> Optional[Asset]:
    """Return an existing equirect panorama asset if one is already registered."""
    q = db.query(Asset).filter(Asset.project_id == project_id)
    if tag:
        q = q.filter(Asset.tag == tag)
    for asset in q.order_by(Asset.id).all():
        try:
            meta = json.loads(asset.prompt_meta_json or "{}")
        except Exception:
            meta = {}
        if meta.get("projection") == "equirectangular":
            return asset
        labels = []
        try:
            labels = json.loads(asset.labels_json or "[]")
        except Exception:
            pass
        if "panorama_360" in labels or asset.kind == PANORAMA_KIND and "equirect" in (asset.filename or "").lower():
            return asset
    return None
