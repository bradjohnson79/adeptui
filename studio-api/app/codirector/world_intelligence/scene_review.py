"""Post-generation world review hook. Advisory only — never blocks ImageGen."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ...db import Asset, Job, Project
from .contracts import WorldStatePacket
from .persist import save_advisory
from .service import evaluate_project_assets, get_policy, world_consistency_text

logger = logging.getLogger(__name__)


def should_review_image(params: dict[str, Any], job: Job) -> bool:
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    purpose = str(params.get("purpose") or ctx.get("objective") or "")
    if purpose == "character_sheet":
        return False
    if job.kind == "character_sheet":
        return False
    if purpose == "environment_reference_sheet":
        return True
    if params.get("miniTakeId") or ctx.get("miniTakeId"):
        return True
    source = str(params.get("sourceFeature") or ctx.get("sourceFeature") or "")
    if source in {"scene_creator", "scene-creator", "sceneCreator"}:
        return True
    if job.scene_id or params.get("scene_id") or ctx.get("sceneId"):
        return True
    operation = str(params.get("operation") or "")
    if "inpaint" in operation or job.kind == "imagegen_edit":
        return True
    return False


def _reference_asset_ids(db: Session, project_id: str, params: dict[str, Any], asset_id: str) -> list[str]:
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    ids: list[str] = []
    for key in ("originalEnvironmentReferenceAssetIds", "groundingAssetIds"):
        raw = ctx.get(key)
        if isinstance(raw, list):
            ids.extend(str(item) for item in raw if item)
    for key in ("atlasAssetId", "source_asset_id"):
        value = ctx.get(key) or params.get(key)
        if value:
            ids.append(str(value))
    parent = params.get("source_asset_id")
    if parent:
        ids.append(str(parent))
    try:
        from .service import _get_index

        for anchor in _get_index().get_anchors(project_id=project_id, active_only=True):
            if anchor.assetId:
                ids.append(anchor.assetId)
    except Exception:
        pass
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if not item or item == asset_id or item in seen:
            continue
        if db.get(Asset, item) is None:
            continue
        seen.add(item)
        out.append(item)
    return out[:4]


def review_committed_image(
    db: Session,
    project: Project,
    job: Job,
    asset: Asset,
    dest: Path,
    params: dict[str, Any],
) -> WorldStatePacket | None:
    """Compare a finished still to approved world references. Never raises to callers."""
    if not should_review_image(params, job):
        return None
    policy = get_policy(project.id, db)
    if not policy.enabled or policy.policy == "off":
        return None
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    scene_id = str(job.scene_id or params.get("scene_id") or ctx.get("sceneId") or "")
    references = _reference_asset_ids(db, project.id, params, asset.id)
    packet = evaluate_project_assets(
        db,
        project_id=project.id,
        asset_id=asset.id,
        reference_asset_ids=references,
        scene_id=scene_id,
        image_path=str(dest),
    )
    text = world_consistency_text(packet)
    save_advisory(db, project.id, packet, text, scene_id=scene_id, asset_id=asset.id)
    try:
        import json

        hist = json.loads(job.history_json or "{}")
        if not isinstance(hist, dict):
            hist = {}
        hist["worldReview"] = {
            "packetId": packet.packetId,
            "availability": packet.availability,
            "advisoryText": text,
            "reason": packet.reason,
        }
        job.history_json = json.dumps(hist)
    except Exception:
        logger.debug("Could not stamp worldReview onto job %s", job.id)
    return packet
