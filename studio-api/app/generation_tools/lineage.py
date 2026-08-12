"""Non-destructive asset registration + library assignment for M3.2a."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset
from ..config import settings


def register_derived_asset(
    db: Session,
    *,
    project_id: str,
    source_path: str | Path,
    kind: str,
    tag: str,
    parent_asset_id: str | None,
    op: str,
    model: str | None = None,
    prompt_meta: dict[str, Any] | None = None,
    library_key: str | None = None,
    filename: str | None = None,
) -> Asset:
    """Copy output into project assets, never overwrite parent; attach lineage + optional taxonomy."""
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(f"Output missing: {src}")

    dest_dir = settings.data_dir / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix or (".png" if kind == "image" else ".wav" if kind == "audio" else ".mp4")
    dest_name = filename or f"{op}_{uuid.uuid4().hex[:10]}{suffix}"
    dest = dest_dir / dest_name
    shutil.copy2(src, dest)

    meta = {
        **(prompt_meta or {}),
        "op": op,
        "model": model,
        "nonDestructive": True,
        "parentAssetId": parent_asset_id,
        "localProvider": True,
        "cloudPaid": False,
    }
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag=tag[:64],
        kind=kind,
        filename=dest.name,
        path=str(dest),
        comfy_name="",
        scope="project",
        labels_json=json.dumps([op]),
        prompt_meta_json=json.dumps(meta),
        parent_asset_id=parent_asset_id,
    )
    db.add(asset)
    db.flush()

    try:
        from ..asset_graph import add_edge, add_version

        add_version(
            db,
            asset_id=asset.id,
            op=op,
            path=str(dest),
            seed=None,
            prompt=meta,
            model=model or op,
        )
        if parent_asset_id:
            add_edge(db, parent_asset_id, asset.id, "derived_from", {"op": op, "model": model})
    except Exception:
        pass

    if library_key:
        try:
            from ..project_library.service import assign_asset

            assign_asset(db, asset, system_key=library_key, classified_by="generation_tools", override=True)
        except Exception:
            pass

    db.commit()
    db.refresh(asset)
    return asset


def require_source_asset(db: Session, project_id: str, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("Source asset not found in active project")
    if not asset.path or not Path(asset.path).is_file():
        raise ValueError("Source asset file missing on disk")
    return asset
