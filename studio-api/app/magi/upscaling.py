"""MAGI Video Upscaling — Real-ESRGAN-ncnn-Vulkan + honest FFmpeg fallback.

GPU engine is never silently relabeled as FFmpeg. Video GPU path is
extract frames → Real-ESRGAN directory → remux + optional audio.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset, Job
from ..editor_mix import probe_has_audio
from ..generation_tools.lineage import register_derived_asset
from . import jobs as magi_jobs
from . import realesrgan_runtime
from .media import (
    cleanup_dir,
    disk_preflight,
    estimate_frame_tree_bytes,
    new_temp_dir,
    probe_media,
    run_ffmpeg,
)

logger = logging.getLogger(__name__)

ENGINE_GPU = "realesrgan-ncnn-vulkan"
ENGINE_FFMPEG = "ffmpeg-scale"
CREATOR_GPU_UNAVAILABLE = realesrgan_runtime.CREATOR_UNAVAILABLE


def _realesrgan_bin() -> str | None:
    path = realesrgan_runtime.binary_path()
    return str(path) if path.is_file() else None


def _realesrgan_models_dir() -> Path:
    return realesrgan_runtime.models_dir()


def _parse_resolution(resolution_str: str) -> tuple[int, int]:
    resolution_str = (resolution_str or "").strip().upper()
    preset = {
        "480P": (854, 480),
        "720P": (1280, 720),
        "1080P": (1920, 1080),
        "1440P": (2560, 1440),
        "4K": (3840, 2160),
        "8K": (7680, 4320),
    }
    if resolution_str in preset:
        return preset[resolution_str]
    if "X" in resolution_str:
        parts = resolution_str.split("X")
        try:
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
    return (1920, 1080)


def capabilities() -> dict[str, Any]:
    ready = realesrgan_runtime.readiness()
    gpu_ready = bool(ready.get("realesrganReady"))
    return {
        "supportedInCode": True,
        "realesrganReady": gpu_ready,
        "creatorMessage": None if gpu_ready else CREATOR_GPU_UNAVAILABLE,
        "engines": [
            {
                "id": ENGINE_GPU,
                "label": "Real-ESRGAN (GPU)",
                "available": gpu_ready,
                "readyOnThisMachine": gpu_ready,
                "models": [
                    {"id": "realesrgan-x4plus", "label": "General 4x", "scale": 4, "content": "general"},
                    {"id": "realesr-animevideov3", "label": "Anime Video", "scale": 4, "content": "anime"},
                    {"id": "realesrgan-x4plus-anime", "label": "Anime 4x", "scale": 4, "content": "anime"},
                ],
            },
            {
                "id": ENGINE_FFMPEG,
                "label": "FFmpeg (fast)",
                "available": True,
                "readyOnThisMachine": True,
                "models": [
                    {"id": "lanczos", "label": "Lanczos", "scale": 0, "content": "general"},
                    {"id": "bicubic", "label": "Bicubic", "scale": 0, "content": "general"},
                ],
            },
        ],
        "autoRouting": False,
        "device": ready.get("device"),
        "version": ready.get("version"),
    }


def _require_gpu_ready() -> dict[str, Any]:
    ready = realesrgan_runtime.readiness()
    if not ready.get("realesrganReady"):
        raise RuntimeError(CREATOR_GPU_UNAVAILABLE)
    return ready


def upscale_frame(
    input_path: str,
    output_path: str,
    engine: str = ENGINE_FFMPEG,
    model: str = "lanczos",
    target_width: int = 1920,
    target_height: int = 1080,
) -> str:
    """Upscale a single image or video. GPU requests never silently become FFmpeg."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if engine == ENGINE_GPU:
        _require_gpu_ready()
        src = Path(input_path)
        if src.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
            _upscale_video_realesrgan(src, out, model, target_width, target_height)
            return str(out)
        _upscale_image_realesrgan(src, out, model)
        return str(out)

    audio_args = ["-c:a", "copy"] if probe_has_audio(Path(input_path)) else ["-an"]
    run_ffmpeg(
        [
            "-i",
            str(input_path),
            "-vf",
            f"scale={target_width}:{target_height}:flags={model or 'lanczos'}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            *audio_args,
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
    )
    return str(out)


def _upscale_image_realesrgan(src: Path, dest: Path, model: str) -> None:
    name, scale = realesrgan_runtime.resolve_model(model)
    cmd = [
        str(realesrgan_runtime.binary_path()),
        "-i",
        str(src),
        "-o",
        str(dest),
        "-n",
        name,
        "-s",
        str(scale),
        "-m",
        str(realesrgan_runtime.models_dir()),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError(f"Real-ESRGAN upscale failed: {(proc.stderr or proc.stdout)[:1000]}")


def _upscale_video_realesrgan(
    src: Path,
    dest: Path,
    model: str,
    target_width: int,
    target_height: int,
    *,
    preview_seconds: float | None = None,
    cancel_check: Any | None = None,
) -> dict[str, Any]:
    probe = probe_media(src)
    frames = max(int(probe.get("frames") or 1), 1)
    if preview_seconds:
        frames = max(1, int(round(float(preview_seconds) * float(probe.get("fps") or 24))))
    need = estimate_frame_tree_bytes(int(probe.get("width") or 1280), int(probe.get("height") or 720), frames)
    disk_preflight(need_bytes=need + 200_000_000, label="GPU upscaling")
    work = new_temp_dir("upscale")
    frames_in = work / "in"
    frames_out = work / "out"
    frames_in.mkdir()
    frames_out.mkdir()
    name, scale = realesrgan_runtime.resolve_model(model)
    try:
        extract = ["-i", str(src)]
        if preview_seconds:
            extract = ["-t", f"{preview_seconds:.2f}", "-i", str(src)]
        run_ffmpeg([*extract, "-vsync", "0", str(frames_in / "frame_%06d.png")], timeout=300)
        if cancel_check and cancel_check():
            raise RuntimeError("Upscale cancelled.")
        cmd = [
            str(realesrgan_runtime.binary_path()),
            "-i",
            str(frames_in),
            "-o",
            str(frames_out),
            "-n",
            name,
            "-s",
            str(scale),
            "-m",
            str(realesrgan_runtime.models_dir()),
            "-f",
            "png",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=max(1800, frames * 25), check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"Real-ESRGAN upscale failed: {(proc.stderr or proc.stdout)[:1000]}")
        if cancel_check and cancel_check():
            raise RuntimeError("Upscale cancelled.")
        fps = max(float(probe.get("fps") or 24), 1.0)
        assembled = work / "assembled.mp4"
        run_ffmpeg(
            [
                "-framerate",
                f"{fps:.3f}",
                "-i",
                str(frames_out / "frame_%06d.png"),
                "-vf",
                f"scale={target_width}:{target_height}:flags=lanczos",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                str(assembled),
            ]
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        if probe.get("hasAudio") and not preview_seconds:
            audio_src = src
            run_ffmpeg(
                [
                    "-i",
                    str(assembled),
                    "-i",
                    str(audio_src),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(dest),
                ]
            )
        else:
            dest.write_bytes(assembled.read_bytes()) if assembled != dest else None
            if assembled != dest:
                import shutil

                shutil.copy2(assembled, dest)
        return {
            "engine": ENGINE_GPU,
            "model": name,
            "scale": scale,
            "frames": frames,
            "source": probe,
        }
    finally:
        cleanup_dir(work)


def upscale_asset(
    db: Session,
    project_id: str,
    asset_id: str,
    engine: str,
    model: str,
    target_resolution: str,
    *,
    preview: bool = False,
) -> dict[str, Any]:
    source = db.get(Asset, asset_id)
    if not source:
        raise ValueError(f"Asset {asset_id} not found")
    if source.project_id != project_id:
        raise ValueError("Asset is not in this project.")
    source_path = str(source.path) if source.path else ""
    if not source_path or not Path(source_path).is_file():
        raise ValueError(f"Asset {asset_id} has no valid file path")

    chosen_engine = engine or ENGINE_FFMPEG
    if chosen_engine == ENGINE_GPU:
        _require_gpu_ready()

    target_w, target_h = _parse_resolution(target_resolution)
    probe = probe_media(source_path)
    work = new_temp_dir("upscale_asset")
    dest = work / f"upscaled_{target_w}x{target_h}.mp4"
    try:
        if chosen_engine == ENGINE_GPU:
            meta = _upscale_video_realesrgan(
                Path(source_path),
                dest,
                model,
                target_w,
                target_h,
                preview_seconds=3.0 if preview else None,
            )
        else:
            args = ["-i", source_path]
            if preview:
                args = ["-t", "3", "-i", source_path]
            audio_args = ["-c:a", "copy"] if probe.get("hasAudio") and not preview else ["-an"]
            run_ffmpeg(
                [
                    *args,
                    "-vf",
                    f"scale={target_w}:{target_h}:flags={model or 'lanczos'}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    *audio_args,
                    "-pix_fmt",
                    "yuv420p",
                    str(dest),
                ]
            )
            meta = {"engine": ENGINE_FFMPEG, "model": model or "lanczos"}
        out_probe = probe_media(dest)
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=dest,
            kind="video" if Path(source_path).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} else "image",
            tag="magi_upscale",
            parent_asset_id=source.id,
            op="upscale",
            model=str(meta.get("model") or model),
            prompt_meta={
                "operation": "upscale",
                "engine": chosen_engine,
                "model": meta.get("model") or model,
                "target": f"{target_w}x{target_h}",
                "preview": preview,
                "sourceAssetId": source.id,
                "sourceProbe": probe,
                "outputProbe": out_probe,
                "device": realesrgan_runtime.readiness().get("device") if chosen_engine == ENGINE_GPU else "cpu",
            },
            library_key="video.generated",
        )
        db.commit()
        return {
            "ok": True,
            "output_asset_id": asset.id,
            "assetId": asset.id,
            "engine": chosen_engine,
            "model": meta.get("model") or model,
            "input_resolution": f"{probe.get('width')}x{probe.get('height')}",
            "output_resolution": f"{out_probe.get('width')}x{out_probe.get('height')}",
            "preview": preview,
            "sourcePreserved": True,
        }
    finally:
        cleanup_dir(work)


def preview_upscale(
    db: Session,
    project_id: str,
    asset_id: str,
    engine: str,
    model: str,
    target_resolution: str,
) -> dict[str, Any]:
    return upscale_asset(db, project_id, asset_id, engine, model, target_resolution, preview=True)


def apply_upscale(
    db: Session,
    project_id: str,
    asset_id: str,
    engine: str,
    model: str,
    target_resolution: str,
) -> dict[str, Any]:
    return enqueue_upscale(
        db,
        project_id=project_id,
        asset_id=asset_id,
        engine=engine,
        model=model,
        target_resolution=target_resolution,
        preview=False,
    )


def enqueue_upscale(
    db: Session,
    *,
    project_id: str,
    asset_id: str,
    engine: str,
    model: str,
    target_resolution: str,
    preview: bool,
) -> dict[str, Any]:
    fingerprint = f"{asset_id}|{engine}|{model}|{target_resolution}|{int(preview)}"
    if engine == ENGINE_GPU:
        _require_gpu_ready()
    existing = magi_jobs.find_active_duplicate(db, project_id, "magi_upscale", fingerprint)
    if existing is not None:
        return {
            "ok": True,
            "queued": existing.status in magi_jobs.ACTIVE,
            "duplicate": True,
            "jobId": existing.id,
            "status": existing.status,
            "stage": existing.stage,
            "engine": engine,
            "preview": preview,
            "message": "An equivalent upscale is already in progress.",
        }
    params = {
        "assetId": asset_id,
        "engine": engine,
        "model": model,
        "targetResolution": target_resolution,
        "preview": preview,
        "fingerprint": fingerprint,
    }
    job = magi_jobs.enqueue_job(
        db,
        project_id=project_id,
        kind="magi_upscale",
        params=params,
        message="Queued MAGI upscale",
    )
    if job.status == "queued":
        magi_jobs.start_background(job.id, lambda jid: magi_jobs.run_with_session(jid, run_upscale_job))
    return {
        "ok": True,
        "queued": job.status == "queued",
        "duplicate": False,
        "jobId": job.id,
        "status": job.status,
        "stage": job.stage,
        "engine": engine,
        "preview": preview,
    }


def run_upscale_job(db: Session, job: Job) -> dict[str, Any]:
    params = {}
    try:
        import json

        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    if magi_jobs.job_cancelled(db, job.id):
        return {"ok": False, "message": "Cancelled"}
    job.stage = "Rendering"
    job.message = "Upscaling"
    db.commit()
    result = upscale_asset(
        db,
        job.project_id,
        str(params.get("assetId")),
        str(params.get("engine") or ENGINE_FFMPEG),
        str(params.get("model") or "lanczos"),
        str(params.get("targetResolution") or "1920x1080"),
        preview=bool(params.get("preview")),
    )
    return {
        **result,
        "message": "Upscale ready" if result.get("ok") else "Upscale failed",
        "outputPath": result.get("assetId"),
    }
