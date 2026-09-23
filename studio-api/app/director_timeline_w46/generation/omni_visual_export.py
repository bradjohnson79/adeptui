"""Omni Wave 2B — deposit a completed Library VIDEO onto Timeline Visual.

No regeneration. Video-only. Reuses W46 master save + MAGI export_to_timeline
for batch-owned clip ledger. Does not edit 1F/3F/T2V generation graphs.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...db import Asset
from ...magi.timeline_handoff import SCENE_SHOT_CLIP_PREFIX, export_to_timeline
from .. import store
from ..contracts import BatchClip, SceneTimelineMaster

OMNI_EXPORT_CLIP_PREFIX = "omni_export_"


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

    bundle = store.load_master(db, project_id, scene_id)
    if not bundle.get("ok"):
        return {**bundle, "mock": False}
    master = SceneTimelineMaster.model_validate(bundle["master"])

    length = max(0.15, float(scene.duration_sec or 5.0))
    clip_label = (label or asset.tag or asset.filename or "Exported take").strip()
    surface = (source_surface or "omni").strip() or "omni"
    clip_id = f"{OMNI_EXPORT_CLIP_PREFIX}{aid.replace('-', '')[:16]}"

    blocks = sorted(master.batchBlocks, key=lambda b: int(getattr(b, "order", 0) or 0))
    target = blocks[-1] if blocks else None
    if target is None:
        return {"ok": False, "error": "NO_EXECUTION_WINDOW", "mock": False}

    retained = [c for c in (target.visualClips or []) if str(c.id) != clip_id]
    cursor = 0.0
    for c in retained:
        cursor = max(cursor, float(c.start or 0.0) + float(c.length or 0.0))

    clip = BatchClip(
        id=clip_id,
        kind="video",
        assetId=aid,
        start=cursor,
        length=length,
        trimStart=0.0,
        label=clip_label,
    )
    target.visualClips = retained + [clip]

    store.save_master(
        db,
        project_id,
        scene_id,
        master,
        bump_revision=True,
    )

    magi_clips = [
        {
            "clipId": f"{SCENE_SHOT_CLIP_PREFIX}omni_{aid.replace('-', '')[:12]}",
            "assetId": aid,
            "name": clip_label,
            "startFrame": 0,
            "durationFrames": max(1, int(round(length * 24.0))),
        }
    ]
    magi = export_to_timeline(
        db,
        project_id,
        scene_id,
        magi_clips,
        label=f"{surface} export",
        batch_block_id=None,
    )

    return {
        "ok": True,
        "mock": False,
        "assetId": aid,
        "sceneId": scene_id,
        "mediaType": "video",
        "visualClipId": clip_id,
        "mediaMode": "video",
        "sourceSurface": surface,
        "w46": magi,
        "message": "Completed video deposited on Timeline Visual.",
    }
