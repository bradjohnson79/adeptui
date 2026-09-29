"""Adept-owned shot stitch. A stitch failure leaves the segments in place."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset
from ..media_ops import stitch_videos
from .contracts import Shot
from .store import require_film, save_film

log = logging.getLogger("adept.film_timeline")


def stitch_shot(db: Session, project_id: str, scene_id: str, shot_id: str) -> dict:
    film = require_film(db, project_id, scene_id)
    shot = next((item for item in film.shots if item.id == shot_id), None)
    if shot is None:
        return {"ok": False, "error": "SHOT_NOT_FOUND", "message": "That shot is not on this scene."}
    completed = [segment for segment in sorted(shot.segments, key=lambda item: item.order) if segment.status == "completed" and segment.assetId]
    if len(completed) < 2:
        shot.state.stitchStatus = "not_needed"
        shot.state.stitchError = None
        shot.state.stitchSegmentIds = []
        save_film(db, project_id, scene_id, film)
        return {"ok": True, "stitchStatus": "not_needed", "film": film.model_dump()}
    if not (shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")):
        shot.state.stitchStatus = "failed"
        shot.state.stitchError = "ffmpeg is not available, so the shot segments stay separate."
        save_film(db, project_id, scene_id, film)
        return {"ok": False, "error": "FFMPEG_UNAVAILABLE", "message": shot.state.stitchError, "film": film.model_dump()}

    paths: list[Path] = []
    for segment in completed:
        asset = db.get(Asset, segment.assetId)
        path = Path(asset.path) if asset and asset.path else None
        if path is None or not path.exists():
            shot.state.stitchStatus = "failed"
            shot.state.stitchError = f"Segment {segment.order + 1} has no playable file. The other segments were kept."
            save_film(db, project_id, scene_id, film)
            return {"ok": False, "error": "SOURCE_ASSET_MISSING", "message": shot.state.stitchError, "segmentId": segment.id}
        paths.append(path)

    # Canonical data root owner (never process-relative): asset serving resolves
    # the stored path against settings.data_dir, so a relative "data/..." path
    # became data/data/... and 404ed the stitched take.
    out_dir = Path(settings.data_dir) / "assets" / project_id / "film-stitch"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{shot.id}-{uuid4().hex[:8]}.mp4"
    try:
        stitch_videos(paths, out_path)
    except Exception as exc:
        log.exception("film-timeline stitch failed project=%s scene=%s shot=%s", project_id, scene_id, shot_id)
        shot.state.stitchStatus = "failed"
        shot.state.stitchError = f"Stitch failed: {exc}. Every generated segment is still on the shot."
        save_film(db, project_id, scene_id, film)
        return {"ok": False, "error": "STITCH_FAILED", "message": shot.state.stitchError, "film": film.model_dump()}

    asset_id = str(uuid4())
    row = Asset(
        id=asset_id,
        project_id=project_id,
        tag="shot-stitch",
        kind="video",
        filename=out_path.name,
        path=str(out_path),
    )
    db.add(row)
    shot.state.stitchAssetId = asset_id
    shot.state.stitchStatus = "ready"
    shot.state.stitchError = None
    # B-F2 (c): record what this take actually covers. A stitch is only 'ready'
    # while its included set == the shot's completed set; anything else (a later
    # segment landing, a legacy take with no record) is treated as stale by the
    # orchestrator and rebuilt from every completed segment.
    shot.state.stitchSegmentIds = [segment.id for segment in completed]
    save_film(db, project_id, scene_id, film)
    log.info(
        "film-timeline stitch project=%s scene=%s shot=%s asset=%s segments=%s",
        project_id,
        scene_id,
        shot_id,
        asset_id,
        len(completed),
    )
    return {"ok": True, "stitchAssetId": asset_id, "film": film.model_dump()}


def restitch_after_segment(db: Session, project_id: str, scene_id: str, shot: Shot) -> None:
    completed = [segment for segment in shot.segments if segment.status == "completed" and segment.assetId]
    if len(completed) >= 2:
        stitch_shot(db, project_id, scene_id, shot.id)
