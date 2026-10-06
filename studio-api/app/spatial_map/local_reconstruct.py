"""Free / local Spatial Map reconstruction.

One observed image → MoGe-2 → deterministic Atlas.
Two or more genuine observed images → VGGT when eligible, plus complementary MoGe.
Generated views never satisfy the observed-view contract.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset, Job, Project

logger = logging.getLogger(__name__)

RECONSTRUCT_KIND = "spatial_reconstruct"
GENERATED_TAGS = {
    "atlas_shot",
    "environment_supplementary_view",
    "environment_reference_sheet",
    "codirector_image",
}
GENERATED_PURPOSES = {
    "atlas_shot",
    "environment_supplementary_view",
    "environment_reference_sheet",
    "image.generate",
}


def is_generated_asset(asset: Asset | None) -> bool:
    """True when the asset is a generator output, not an observed photograph."""
    if asset is None:
        return False
    tag = str(getattr(asset, "tag", "") or "").strip().lower()
    if tag in GENERATED_TAGS:
        return True
    meta: dict[str, Any] = {}
    raw = getattr(asset, "prompt_meta_json", "") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                meta = parsed
        except (TypeError, json.JSONDecodeError):
            meta = {}
    purpose = str(meta.get("purpose") or meta.get("objective") or "").strip().lower()
    if purpose in GENERATED_PURPOSES:
        return True
    if str(meta.get("geometryRole") or "").strip().lower() == "inferred":
        return True
    return False


def observed_asset_ids(db: Session, project_id: str, asset_ids: list[str]) -> list[str]:
    """Keep only genuine user/Library photographs of the same location."""
    observed: list[str] = []
    for asset_id in asset_ids:
        aid = str(asset_id or "").strip()
        if not aid:
            continue
        asset = db.get(Asset, aid) if db is not None else None
        if asset is None or str(getattr(asset, "project_id", "") or "") != project_id:
            continue
        if is_generated_asset(asset):
            continue
        path = str(getattr(asset, "path", "") or "").strip()
        if not path or not Path(path).is_file():
            continue
        if aid not in observed:
            observed.append(aid)
    return observed


def enqueue_spatial_reconstruct_job(
    db: Session,
    project_id: str,
    body: dict[str, Any],
) -> Job:
    if db is None:
        raise RuntimeError("Local reconstruction needs the project database.")
    project = db.get(Project, project_id)
    if project is None:
        raise RuntimeError("Project not found")
    job = Job(
        id=str(uuid4()),
        project_id=project_id,
        kind=RECONSTRUCT_KIND,
        status="queued",
        progress=0.0,
        stage="analyzing",
        message="Analyzing environment",
        params_json=json.dumps(body),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def persist_deterministic_atlas(
    db: Session,
    *,
    project_id: str,
    plate_path: str,
    parent_asset_id: str = "",
) -> str:
    src = Path(plate_path)
    if not src.is_file():
        raise RuntimeError("The reconstructed Atlas plate was not created.")
    asset_id = str(uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}.png"
    shutil.copyfile(src, dest)
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag="atlas_shot",
        kind="image",
        filename="spatial_atlas_reconstructed.png",
        path=str(dest),
        comfy_name="",
        parent_asset_id=parent_asset_id or None,
        prompt_meta_json=json.dumps(
            {
                "purpose": "atlas_shot",
                "geometrySource": "reconstructed",
                "renderer": "adept.atlas.deterministic.v1",
            }
        ),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    try:
        from ..project_library.service import assign_asset

        assign_asset(db, asset, classified_by="spatial_reconstruct")
    except Exception:
        pass
    return asset_id


def run_spatial_reconstruct_job(db: Session, job: Job) -> dict[str, Any]:
    """MoGe / VGGT → deterministic Atlas. No diffusion."""
    from .geometry.infer import run_moge2_plate, run_vggt_plate

    params = json.loads(job.params_json or "{}")
    if not isinstance(params, dict):
        params = {}
    project_id = job.project_id
    requested = [str(a) for a in (params.get("observedAssetIds") or params.get("attachment_asset_ids") or []) if a]
    source = str(params.get("sourceAssetId") or params.get("source_asset_id") or "").strip()
    if source and source not in requested:
        requested.insert(0, source)
    observed = observed_asset_ids(db, project_id, requested)
    if not observed:
        raise RuntimeError(
            "Local reconstruction needs a real location photograph. "
            "Generated images cannot be used as observed geometry."
        )

    def _stage(stage: str, message: str, progress: float) -> None:
        job.stage = stage
        job.message = message
        job.progress = progress
        job.status = "running"
        db.commit()

    _stage("analyzing", "Analyzing environment", 0.08)
    asset_paths = []
    for aid in observed:
        asset = db.get(Asset, aid)
        asset_paths.append(str(asset.path))

    out_dir = Path(settings.data_dir) / "spatial_reconstruct" / project_id / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    vggt_status: dict[str, Any] = {"eligible": len(observed) >= 2, "used": False}

    _stage("reconstructing", "Reconstructing geometry", 0.22)
    if len(observed) >= 2:
        vggt = run_vggt_plate(asset_paths, out_dir / "vggt")
        vggt_status = {
            "eligible": True,
            "used": bool(vggt.get("ok")),
            "code": vggt.get("code") or "",
            "message": vggt.get("message") or "",
            "observedImageCount": len(observed),
        }
        if vggt.get("ok"):
            plate = str((vggt.get("render") or {}).get("mandatoryPlate") or "")
            engine = "vggt"
            infer = vggt
        else:
            # Honest VGGT blocker does not invent multi-view geometry. MoGe still
            # produces a usable one-image Atlas from the master photograph.
            moge = run_moge2_plate(asset_paths[0], out_dir / "moge2")
            if not moge.get("ok"):
                raise RuntimeError(str(moge.get("message") or "Local reconstruction failed."))
            plate = str((moge.get("render") or {}).get("mandatoryPlate") or "")
            engine = "moge2"
            infer = moge
    else:
        moge = run_moge2_plate(asset_paths[0], out_dir / "moge2")
        if not moge.get("ok"):
            raise RuntimeError(str(moge.get("message") or "Local reconstruction failed."))
        plate = str((moge.get("render") or {}).get("mandatoryPlate") or "")
        engine = "moge2"
        infer = moge

    if not plate or not Path(plate).is_file():
        raise RuntimeError("Local reconstruction did not produce a top-down Atlas.")

    _stage("rendering", "Rendering Atlas", 0.72)
    atlas_id = persist_deterministic_atlas(
        db,
        project_id=project_id,
        plate_path=plate,
        parent_asset_id=observed[0],
    )

    _stage("saving", "Saving Spatial Map", 0.9)
    from .service import assign_existing_atlas

    document = assign_existing_atlas(
        db,
        project_id,
        atlas_id,
        original_environment_reference_asset_id=observed[0],
        scene_description=str(params.get("scene_description") or params.get("prompt") or "") or None,
    )
    document.geometrySource = "reconstructed"
    from .service import SpatialMapUpdateBody, update_document

    update_document(
        db,
        project_id,
        document.id,
        SpatialMapUpdateBody(geometrySource="reconstructed"),
    )

    result = {
        "ok": True,
        "output_asset_id": atlas_id,
        "outputAssetId": atlas_id,
        "geometrySource": "reconstructed",
        "engine": engine,
        "observedAssetIds": observed,
        "observedCount": len(observed),
        "vggt": vggt_status,
        "spatial_map_id": document.id,
        "infer": {k: v for k, v in infer.items() if k != "render"},
    }
    job.params_json = json.dumps({**params, **result})
    job.status = "done"
    job.stage = "done"
    job.progress = 1.0
    job.message = "Spatial Map saved"
    db.commit()
    return result
