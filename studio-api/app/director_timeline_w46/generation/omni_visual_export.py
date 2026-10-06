"""Omni Wave 2B — deposit a completed Library VIDEO onto Timeline Visual.

No regeneration. Video-only. Reuses W46 master save + MAGI export_to_timeline
for batch-owned clip ledger. Does not edit 1F/3F/T2V generation graphs.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...db import Asset
from .. import store

def export_completed_video_to_timeline(
    db: Session,
    project_id: str,
    scene_id: str,
    asset_id: str,
    *,
    label: str | None = None,
    source_surface: str | None = None,
) -> dict[str, Any]:
    """Place a completed video asset onto Timeline Visual (media_mode=video).

    Primary: Master batch.visualClips upsert (kind=video).
    Secondary: MAGI/W46 export_to_timeline for batch-owned visual clip ledger.
    """
    aid = str(asset_id or "").strip()
    if not aid:
        return {"ok": False, "error": "ASSET_ID_REQUIRED", "mock": False}

    asset = (
        db.query(Asset)
        .filter(Asset.id == aid, Asset.project_id == project_id)
        .one_or_none()
    )
    if not asset:
        return {
            "ok": False,
            "error": "ASSET_OWNERSHIP",
            "message": f"Asset '{aid}' does not exist in project '{project_id}'.",
            "mock": False,
        }
    if str(asset.kind or "").lower() != "video":
        return {
            "ok": False,
            "error": "VIDEO_REQUIRED",
            "message": "Export to Timeline Visual accepts completed video only (image = reference).",
            "mock": False,
        }

    scene = store.get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}

    length = max(0.15, float(scene.duration_sec or 5.0))
    clip_label = (label or asset.tag or asset.filename or "Exported take").strip()
    surface = (source_surface or "omni").strip() or "omni"
    from ...film_timeline.insertion import add_to_timeline

    placed = add_to_timeline(
        db,
        project_id,
        scene_id,
        media_type="video",
        asset_id=aid,
        target_track_type="video",
        duration_sec=length,
        label=clip_label,
        metadata={"sourceSurface": surface, "mediaType": "video"},
    )
    if not placed.get("ok"):
        return {"ok": False, "error": placed.get("error") or "INSERT_FAILED", "message": placed.get("message"), "mock": False}
    clip = placed.get("clip") or {}
    return {
        "ok": True,
        "mock": False,
        "assetId": aid,
        "sceneId": scene_id,
        "mediaType": "video",
        "visualClipId": clip.get("id"),
        "mediaMode": "video",
        "sourceSurface": surface,
        "message": "Completed video deposited on Timeline Visual.",
    }
