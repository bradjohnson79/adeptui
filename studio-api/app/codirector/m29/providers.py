"""M2.9 real-provider bridge for native studio Jobs.

Fixture mode remains CI-only via ADEPT_M29_FIXTURE_MODE / fixtureComplete.
Never treats fixture success as production evidence.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from . import fixture_mode_enabled

logger = logging.getLogger(__name__)


class ProviderUnavailable(RuntimeError):
    """Infrastructure or model missing - map to executive Blocked."""


class ProviderError(RuntimeError):
    """Provider ran but failed - map to executive Failed."""


def wants_fixture(payload: dict[str, Any] | None = None) -> bool:
    payload = payload or {}
    return fixture_mode_enabled() or bool(payload.get("fixtureComplete"))


def comfy_available() -> bool:
    try:
        from ..executive.imagegen_adapter import comfy_available as _c

        return bool(_c())
    except Exception:  # noqa: BLE001
        return False


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def fal_key_present(db: Session | None = None) -> bool:
    del db
    try:
        from ...secrets_store import get_secret

        key = get_secret("fal_api_key")
        if key:
            return True
    except Exception:  # noqa: BLE001
        pass
    import os

    return bool(os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY"))


def resolve_asset_path(db: Session, asset_id: str | None) -> Path | None:
    if not asset_id:
        return None
    from ...db import Asset

    asset = db.get(Asset, asset_id)
    if not asset or not asset.path:
        return None
    path = Path(asset.path)
    return path if path.exists() else None


def handler_status_for_exc(exc: BaseException) -> str:
    if isinstance(exc, ProviderUnavailable):
        return "Blocked"
    if isinstance(exc, PermissionError):
        return "Blocked"
    return "Failed"


def _register_output_asset(
    db: Session,
    *,
    project_id: str,
    path: str,
    kind: str,
    tag: str,
    parent_asset_id: str | None = None,
) -> str:
    from ...db import Asset

    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id=project_id,
            tag=tag,
            kind=kind,
            filename=Path(path).name,
            path=path,
            parent_asset_id=parent_asset_id,
        )
    )
    db.commit()
    return aid


def enqueue_studio_job(
    db: Session,
    *,
    project_id: str,
    kind: str,
    params: dict[str, Any] | None = None,
    scene_id: str | None = None,
    message: str | None = None,
) -> Any:
    from ...db import Job, Project

    project = db.get(Project, project_id)
    if not project:
        raise ProviderError(f"Project not found: {project_id}")
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene_id,
        kind=kind,
        status="queued",
        message=message or f"Queued {kind}",
        params_json=json.dumps(params or {}),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def schedule_studio_job(job_id: str) -> None:
    from ..executive.imagegen_adapter import schedule_job_queue_enqueue

    schedule_job_queue_enqueue(job_id)


def poll_studio_job(
    db: Session,
    job_id: str,
    *,
    timeout_sec: float = 180.0,
    poll_interval: float = 0.25,
) -> dict[str, Any]:
    """Poll a studio Job until done/failed. Returns asset/output metadata."""
    from ...db import Job

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        db.expire_all()
        job = db.get(Job, job_id)
        if not job:
            raise ProviderError(f"studio job not found: {job_id}")
        if job.status == "done":
            try:
                params = json.loads(job.params_json or "{}")
            except json.JSONDecodeError:
                params = {}
            asset_id = params.get("output_asset_id") or params.get("asset_id")
            return {
                "studioJobId": job_id,
                "assetId": str(asset_id) if asset_id else None,
                "outputPath": job.output_path,
                "status": "done",
                "kind": job.kind,
                "message": job.message,
                "params": params,
            }
        if job.status in ("failed", "cancelled"):
            raise ProviderError(job.message or f"studio job {job.status}")
        time.sleep(poll_interval)

    db.expire_all()
    job = db.get(Job, job_id)
    status = job.status if job else "missing"
    msg = (job.message if job else "") or ""
    if status in ("queued", "running"):
        raise ProviderUnavailable(
            f"studio job {job_id} stuck in {status} after {timeout_sec}s "
            f"(unavailable). {msg}".strip()
        )
    raise ProviderError(f"studio job {job_id} timed out (status={status})")


def run_imagegen(
    db: Session,
    *,
    project_id: str,
    payload: dict[str, Any],
    scene_id: str | None = None,
) -> dict[str, Any]:
    """Real Comfy/Z-Image path via storyboard_jobs + imagegen_adapter."""
    from ...storyboard_jobs import enqueue_imagegen_job
    from ..executive.imagegen_adapter import poll_imagegen_job, schedule_job_queue_enqueue

    if not comfy_available():
        raise ProviderUnavailable(
            "ComfyUI unavailable; cannot run M2.9 image generation "
            "(mock/fixture completion disabled on production path)"
        )

    operation = (payload.get("operation") or "generate").lower()
    edit = operation in {"image_to_image", "i2i", "inpaint", "outpaint", "edit", "variation"}
    body: dict[str, Any] = {
        "prompt": payload.get("prompt") or "M2.9 image",
        "tag": payload.get("tag") or "m29_image",
        "labels": payload.get("labels") or ["m29", "image"],
        "width": int(payload.get("width") or 1280),
        "height": int(payload.get("height") or 720),
        "model": payload.get("model") or "auto",
        "edit": edit,
    }
    if payload.get("sourceAssetId") or payload.get("source_asset_id"):
        body["source_asset_id"] = payload.get("sourceAssetId") or payload.get("source_asset_id")
    if payload.get("seed") is not None:
        body["seed"] = payload["seed"]

    studio_job = enqueue_imagegen_job(
        db, project_id, body, scene_id=scene_id or payload.get("sceneId")
    )
    schedule_job_queue_enqueue(studio_job.id)
    try:
        asset_id, _ = poll_imagegen_job(
            db,
            studio_job.id,
            project_id=project_id,
            timeout_sec=float(payload.get("timeoutSec") or 180),
            allow_mock=False,
        )
    except RuntimeError as exc:
        raise ProviderUnavailable(str(exc)) from exc
    except TimeoutError as exc:
        raise ProviderUnavailable(str(exc)) from exc
    except ValueError as exc:
        raise ProviderError(str(exc)) from exc

    return {
        "assetId": asset_id,
        "imageJobId": studio_job.id,
        "operation": operation,
        "provider": "comfy",
        "fixture": False,
        "status": "generated",
        "mockAdapter": False,
    }


def run_video(
    db: Session,
    *,
    project_id: str,
    payload: dict[str, Any],
    scene_id: str | None = None,
) -> dict[str, Any]:
    """Real t2v/i2v via txt2vid or render_scene studio jobs."""
    mode = (payload.get("mode") or "text_to_video").lower()
    sid = scene_id or payload.get("sceneId")
    timeout = float(payload.get("timeoutSec") or 300)

    if mode in {"image_to_video", "i2v", "continuation", "extension", "transition"}:
        if not sid:
            raise ProviderError("image_to_video requires sceneId with frame assets")
        if not (comfy_available() or fal_key_present(db)):
            raise ProviderUnavailable(
                "Neither ComfyUI nor fal API key available for image-to-video"
            )
        from ...db import Scene

        scene = db.get(Scene, sid)
        if not scene or scene.project_id != project_id:
            raise ProviderError(f"Scene not found: {sid}")
        first = payload.get("firstFrameAssetId") or payload.get("startAssetId")
        last = payload.get("lastFrameAssetId") or payload.get("endAssetId")
        if first:
            scene.start_asset_id = first
        if last:
            scene.end_asset_id = last
        if payload.get("prompt"):
            scene.prompt = str(payload["prompt"])
        db.commit()
        job = enqueue_studio_job(
            db,
            project_id=project_id,
            kind="render_scene",
            params={"m29": True, "mode": mode},
            scene_id=sid,
            message="Queued M2.9 scene I2V",
        )
    else:
        if not fal_key_present(db) and not comfy_available():
            raise ProviderUnavailable(
                "No video provider available (fal key / Comfy) for text_to_video"
            )
        job = enqueue_studio_job(
            db,
            project_id=project_id,
            kind="txt2vid",
            params={
                "prompt": payload.get("prompt") or "M2.9 video",
                "duration_sec": payload.get("durationSec") or payload.get("duration_sec") or 4,
                "fps": payload.get("fps") or 24,
                "m29": True,
            },
            scene_id=sid,
            message="Queued M2.9 Txt2Vid",
        )

    schedule_studio_job(job.id)
    result = poll_studio_job(db, job.id, timeout_sec=timeout)
    asset_id = result.get("assetId")
    if not asset_id and result.get("outputPath"):
        asset_id = _register_output_asset(
            db,
            project_id=project_id,
            path=str(result["outputPath"]),
            kind="video",
            tag="m29_video",
        )
    if not asset_id:
        raise ProviderError("video job completed without output asset")
    return {
        "assetId": asset_id,
        "studioJobId": job.id,
        "mode": mode,
        "provider": "studio_queue",
        "fixture": False,
        "status": "generated",
        "outputPath": result.get("outputPath"),
    }


def run_lipsync(
    db: Session,
    *,
    project_id: str,
    payload: dict[str, Any],
    scene_id: str | None = None,
) -> dict[str, Any]:
    if not comfy_available():
        raise ProviderUnavailable("ComfyUI unavailable for lipsync")
    sid = scene_id or payload.get("sceneId")
    if not sid:
        raise ProviderError("lipsync requires sceneId")
    from ...db import Scene

    scene = db.get(Scene, sid)
    if not scene or scene.project_id != project_id:
        raise ProviderError(f"Scene not found: {sid}")
    audio_id = payload.get("audioAssetId") or payload.get("audio_asset_id")
    if audio_id:
        scene.lipsync_audio_asset_id = audio_id
        scene.lipsync_enabled = 1
        db.commit()
    kind = "dual_lipsync" if payload.get("dual") or payload.get("tracks") else "lipsync"
    job = enqueue_studio_job(
        db,
        project_id=project_id,
        kind=kind,
        params={"m29": True},
        scene_id=sid,
        message=f"Queued M2.9 {kind}",
    )
    schedule_studio_job(job.id)
    result = poll_studio_job(
        db, job.id, timeout_sec=float(payload.get("timeoutSec") or 300)
    )
    db.expire_all()
    scene = db.get(Scene, sid)
    out_path = (scene.lipsync_output_path if scene else None) or result.get("outputPath")
    asset_id = result.get("assetId")
    if not asset_id and out_path:
        asset_id = _register_output_asset(
            db,
            project_id=project_id,
            path=str(out_path),
            kind="video",
            tag="m29_lipsync",
        )
    if not asset_id:
        raise ProviderError("lipsync job completed without output")
    return {
        "assetId": asset_id,
        "studioJobId": job.id,
        "provider": "comfy_lipsync",
        "fixture": False,
        "status": "generated",
        "phonemes": payload.get("phonemes") or [],
        "visemes": payload.get("visemes") or [],
        "outputPath": out_path,
    }


def run_mouth_track(
    db: Session,
    *,
    project_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from ...mouth_tracker import Roi, track_mouth_rois

    video_id = payload.get("videoAssetId") or payload.get("video_asset_id")
    path = resolve_asset_path(db, video_id)
    if path is None:
        sid = payload.get("sceneId")
        if sid:
            from ...db import Scene

            scene = db.get(Scene, sid)
            for candidate in (
                getattr(scene, "lipsync_output_path", None) if scene else None,
                getattr(scene, "output_path", None) if scene else None,
            ):
                if candidate and Path(candidate).exists():
                    path = Path(candidate)
                    break
    if path is None:
        raise ProviderUnavailable(
            "mouth track requires an existing video asset path (MediaPipe tracker)"
        )

    rects = payload.get("rectangles") or payload.get("seed") or []
    if rects and isinstance(rects[0], dict):
        r0 = rects[0]
        seed = Roi(
            float(r0.get("x", 0.4)),
            float(r0.get("y", 0.55)),
            float(r0.get("w", 0.2)),
            float(r0.get("h", 0.12)),
        )
    else:
        seed = Roi(0.4, 0.55, 0.2, 0.12)

    try:
        track = track_mouth_rois(path, seed, max_frames=int(payload.get("maxFrames") or 0))
    except RuntimeError as exc:
        raise ProviderUnavailable(str(exc)) from exc

    return {
        "trackId": f"mouth-{uuid.uuid4().hex[:12]}",
        "keyframes": track,
        "rectangles": [
            {"t": k.get("t", 0), "x": k["x"], "y": k["y"], "w": k["w"], "h": k["h"]}
            for k in track
        ],
        "provider": "mediapipe_mouth_tracker",
        "fixture": False,
        "status": "generated",
        "projectId": project_id,
        "videoAssetId": video_id,
    }


def run_render(
    db: Session,
    *,
    project_id: str,
    payload: dict[str, Any],
    scene_id: str | None = None,
) -> dict[str, Any]:
    kind = payload.get("kind") or "timeline_render"
    studio_kind = "render_scene" if kind == "scene_render" else "render_timeline"
    sid = scene_id or payload.get("sceneId")
    if studio_kind == "render_scene" and not sid:
        raise ProviderError("scene_render requires sceneId")
    if not (comfy_available() or fal_key_present(db) or ffmpeg_available()):
        raise ProviderUnavailable(
            "No render provider available (Comfy / fal / ffmpeg)"
        )
    job = enqueue_studio_job(
        db,
        project_id=project_id,
        kind=studio_kind,
        params={"m29": True, "manifestId": payload.get("manifestId")},
        scene_id=sid,
        message=f"Queued M2.9 {studio_kind}",
    )
    schedule_studio_job(job.id)
    result = poll_studio_job(
        db, job.id, timeout_sec=float(payload.get("timeoutSec") or 600)
    )
    asset_id = result.get("assetId")
    if not asset_id and result.get("outputPath"):
        asset_id = _register_output_asset(
            db,
            project_id=project_id,
            path=str(result["outputPath"]),
            kind="video",
            tag="m29_render",
        )
    if not asset_id:
        raise ProviderError("render job completed without output")
    return {
        "assetId": asset_id,
        "studioJobId": job.id,
        "kind": kind,
        "provider": "studio_render_queue",
        "fixture": False,
        "status": "generated",
        "outputPath": result.get("outputPath"),
        "manifestId": payload.get("manifestId"),
    }


def process_audio_ffmpeg(
    db: Session,
    *,
    project_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not ffmpeg_available():
        raise ProviderUnavailable("ffmpeg not on PATH for audio_process")
    asset_id = payload.get("assetId") or payload.get("audioAssetId")
    src = resolve_asset_path(db, asset_id)
    if src is None:
        raise ProviderUnavailable(f"audio asset path missing for {asset_id}")

    from ...media_ops import run_ffmpeg

    ops = payload.get("ops") or ["normalize"]
    out = src.with_name(src.stem + "_m29_processed" + src.suffix)
    if any(str(op).lower() in {"normalize", "loudnorm", "cleanup"} for op in ops):
        run_ffmpeg(
            [
                "-i",
                str(src),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar",
                "48000",
                str(out),
            ]
        )
    else:
        run_ffmpeg(["-i", str(src), "-c", "copy", str(out)])

    new_id = _register_output_asset(
        db,
        project_id=project_id,
        path=str(out),
        kind="audio",
        tag="m29_audio_process",
        parent_asset_id=asset_id,
    )
    return {
        "assetId": new_id,
        "sourceAssetId": asset_id,
        "ops": ops,
        "provider": "ffmpeg",
        "fixture": False,
        "status": "processed",
        "outputPath": str(out),
    }
