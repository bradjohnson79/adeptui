"""Publish and MAGI for Film Timeline media.

These reuse the existing Library registration and MAGI upscale helpers.
They record the result on the film document and do not call save_master.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from .store import require_film, save_film


def publish_film_media(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    asset_id: str,
    update: bool = False,
) -> dict[str, Any]:
    from ..director_timeline_w46.scene_publish import OP_VIDEO_PUBLISH, TAG_VIDEO_PUBLISHED_MASTER
    from ..director_timeline_w46.scene_stitch import resolve_asset_file
    from ..generation_tools.lineage import register_derived_asset

    film = require_film(db, project_id, scene_id)
    source_id = str(asset_id or "").strip()
    if not source_id:
        return {"ok": False, "error": "VIDEO_REQUIRED", "message": "Publish needs a finished video.", "mock": False}
    if update and not film.publishedAssetId:
        return {"ok": False, "error": "NOTHING_PUBLISHED", "message": "Nothing is published yet.", "mock": False}
    src_path = resolve_asset_file(db, project_id, source_id)
    if src_path is None:
        return {"ok": False, "error": "VIDEO_MISSING", "message": "That video file is missing.", "mock": False}
    next_version = int(film.publishVersion or 0) + 1
    try:
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=src_path,
            kind="video",
            tag=TAG_VIDEO_PUBLISHED_MASTER,
            parent_asset_id=source_id,
            op=OP_VIDEO_PUBLISH,
            model=OP_VIDEO_PUBLISH,
            prompt_meta={
                "sceneId": scene_id,
                "libraryKind": "Video Published Master",
                "sourceAssetId": source_id,
                "filmTimeline": True,
                "version": next_version,
            },
            filename=f"video_published_master_{scene_id[:8]}_{uuid.uuid4().hex[:8]}.mp4",
        )
    except Exception as exc:
        return {"ok": False, "error": "PUBLISH_FAILED", "message": str(exc)[:400], "mock": False}
    film = require_film(db, project_id, scene_id)
    film.publishedAssetId = asset.id
    film.publishVersion = next_version
    save_film(db, project_id, scene_id, film)
    return {
        "ok": True,
        "updated": bool(update),
        "publishedAssetId": asset.id,
        "film": film.model_dump(),
        "mock": False,
    }


def magi_options_for_asset(db: Session, project_id: str, scene_id: str, *, asset_id: str) -> dict[str, Any]:
    from ..director_timeline_w46.scene_stitch import resolve_asset_file
    from ..magi.media import probe_media
    from ..magi.upscale_targets import default_target, meaningful_targets
    from ..magi.upscaling import ENGINE_FFMPEG, ENGINE_GPU, capabilities, preferred_gpu_model

    require_film(db, project_id, scene_id)
    source_id = str(asset_id or "").strip()
    src_path = resolve_asset_file(db, project_id, source_id) if source_id else None
    if src_path is None:
        return {"ok": False, "error": "VIDEO_REQUIRED", "message": "MAGI needs a finished video.", "mock": False}
    probe = probe_media(src_path)
    src_w = int(probe.get("width") or 0)
    src_h = int(probe.get("height") or 0)
    caps = capabilities()
    gpu_ready = bool(caps.get("realesrganReady"))
    first = default_target(src_w, src_h)
    return {
        "ok": True,
        "sourceAssetId": source_id,
        "sourceWidth": src_w,
        "sourceHeight": src_h,
        "targets": meaningful_targets(src_w, src_h),
        "defaultTarget": (first or {}).get("id") or "",
        "defaultEngine": ENGINE_GPU if gpu_ready else ENGINE_FFMPEG,
        "defaultModel": preferred_gpu_model() if gpu_ready else "lanczos",
        "realesrganReady": gpu_ready,
        "engines": caps.get("engines") or [],
        "honesty": caps.get("honesty"),
        "mock": False,
    }


def magi_upscale_film(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    asset_id: str,
    engine: str = "ffmpeg-scale",
    model: str = "lanczos",
    target_resolution: str = "",
) -> dict[str, Any]:
    from ..magi.upscale_targets import UpscaleTargetError
    from ..magi.upscaling import apply_upscale

    require_film(db, project_id, scene_id)
    source_id = str(asset_id or "").strip()
    if not source_id:
        return {"ok": False, "error": "VIDEO_REQUIRED", "message": "MAGI needs a finished video.", "mock": False}
    try:
        result = apply_upscale(
            db,
            project_id,
            source_id,
            engine,
            model,
            target_resolution,
            scene_id=scene_id,
            persist_scene_publish=False,
        )
    except UpscaleTargetError as exc:
        return {"ok": False, "error": exc.code, "message": str(exc)[:400], "mock": False}
    except Exception as exc:
        return {"ok": False, "error": "MAGI_UPSCALE_FAILED", "message": str(exc)[:400], "mock": False}
    upscaled = None
    if isinstance(result, dict):
        upscaled = result.get("upscaledAssetId") or result.get("assetId")
    if upscaled:
        film = require_film(db, project_id, scene_id)
        film.upscaledAssetId = str(upscaled)
        save_film(db, project_id, scene_id, film)
    return {"ok": True, "sourceAssetId": source_id, "upscaledAssetId": upscaled, "magi": result, "mock": False}
