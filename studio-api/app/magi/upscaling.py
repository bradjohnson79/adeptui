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
from .upscale_targets import (
    UpscaleTargetError,
    aspect_label,
    parse_resolution,
    resolve_apply_target,
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
    return parse_resolution(resolution_str)


def scale_filter(width: int, height: int, flags: str = "lanczos") -> str:
    """Spatial scale to exact pixels. No crop, pad, letterbox, or stretch."""
    return f"scale={int(width)}:{int(height)}:flags={flags or 'lanczos'},setsar=1"


def _gpu_model_ready(model_id: str) -> bool:
    name, scale = realesrgan_runtime.resolve_model(model_id)
    return realesrgan_runtime._model_pair_exists(name) or realesrgan_runtime._model_pair_exists(f"{name}-x{scale}")


def preferred_gpu_model() -> str:
    for model_id in ("realesr-animevideov3", "realesrgan-x4plus-anime", "realesrgan-x4plus"):
        if _gpu_model_ready(model_id):
            return model_id
    return "realesrgan-x4plus"


def capabilities() -> dict[str, Any]:
    ready = realesrgan_runtime.readiness()
    gpu_ready = bool(ready.get("realesrganReady"))
    gpu_models = [
        row
        for row in (
            {"id": "realesrgan-x4plus", "label": "General 4x", "scale": 4, "content": "general"},
            {"id": "realesr-animevideov3", "label": "Anime Video", "scale": 4, "content": "anime"},
            {"id": "realesrgan-x4plus-anime", "label": "Anime 4x", "scale": 4, "content": "anime"},
        )
        if _gpu_model_ready(str(row["id"]))
    ]
    if not gpu_models:
        gpu_models = [{"id": "realesrgan-x4plus", "label": "General 4x", "scale": 4, "content": "general"}]
    return {
        "supportedInCode": True,
        "realesrganReady": gpu_ready,
        "creatorMessage": None if gpu_ready else CREATOR_GPU_UNAVAILABLE,
        "spatialEnhancementOnly": True,
        "temporalConsistency": False,
        "honesty": "Spatial frame enhancement only. Not temporal AI restoration.",
        "preferredGpuModel": preferred_gpu_model(),
        "engines": [
            {
                "id": ENGINE_GPU,
                "label": "Real-ESRGAN (GPU)",
                "available": gpu_ready,
                "readyOnThisMachine": gpu_ready,
                "models": gpu_models,
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
            scale_filter(target_width, target_height, model or "lanczos"),
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
    include_audio: bool = True,
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
                scale_filter(target_width, target_height, "lanczos"),
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
        if include_audio and probe.get("hasAudio") and not preview_seconds:
            assembled_probe = probe_media(assembled)
            video_dur = float(assembled_probe.get("duration") or probe.get("duration") or 0)
            mux = [
                "-i",
                str(assembled),
                "-i",
                str(src),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-af",
                "apad",
            ]
            if video_dur > 0:
                mux.extend(["-t", f"{video_dur:.6f}"])
            mux.append(str(dest))
            run_ffmpeg(mux)
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
    sound_profile: str = "preserve_original",
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

    probe = probe_media(source_path)
    src_w = int(probe.get("width") or 0)
    src_h = int(probe.get("height") or 0)
    from .sound_enhancement import analyze_source, attach_soundtrack, output_layout, profile_label, recommend, resolve_profile

    analysis = analyze_source(source_path)
    chosen_sound = resolve_profile(sound_profile, analysis)
    recommendation = recommend(analysis)
    prior_meta: dict[str, Any] = {}
    try:
        import json

        prior_meta = json.loads(getattr(source, "prompt_meta_json", None) or "{}")
    except (TypeError, ValueError):
        prior_meta = {}
    already_baked = bool(prior_meta.get("audioEnhancementBaked")) and str(prior_meta.get("audioEnhancement") or "") == chosen_sound
    if already_baked:
        chosen_sound = "preserve_original"
    try:
        target_w, target_h, target_label = resolve_apply_target(src_w, src_h, target_resolution)
    except UpscaleTargetError:
        raise
    work = new_temp_dir("upscale_asset")
    picture = work / f"picture_{target_w}x{target_h}.mp4"
    dest = work / f"upscaled_{target_w}x{target_h}.mp4"
    try:
        if chosen_engine == ENGINE_GPU:
            meta = _upscale_video_realesrgan(
                Path(source_path),
                picture,
                model,
                target_w,
                target_h,
                preview_seconds=3.0 if preview else None,
                include_audio=False,
            )
        else:
            args = ["-i", source_path]
            if preview:
                args = ["-t", "3", "-i", source_path]
            fps = float(probe.get("fps") or 0)
            rate_args = ["-r", f"{fps:.6f}"] if fps > 1 else []
            run_ffmpeg(
                [
                    *args,
                    "-vf",
                    scale_filter(target_w, target_h, model or "lanczos"),
                    *rate_args,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    "-an",
                    "-pix_fmt",
                    "yuv420p",
                    str(picture),
                ]
            )
            meta = {"engine": ENGINE_FFMPEG, "model": model or "lanczos"}
        picture_probe = probe_media(picture)
        sound_duration = 3.0 if preview else float(picture_probe.get("duration") or analysis.get("duration") or 0)
        sound = attach_soundtrack(
            picture,
            source_path,
            dest,
            chosen_sound,
            analysis,
            duration=sound_duration,
        )
        out_probe = probe_media(dest)
        if not preview and analysis.get("hasAudio"):
            src_dur = float(analysis.get("duration") or 0)
            out_dur = float(out_probe.get("duration") or 0)
            if src_dur > 0.4 and abs(out_dur - src_dur) > 0.35:
                raise RuntimeError("The enhanced soundtrack drifted from the picture.")
        sound_probe_channels = int(sound.get("channels") or 0)
        sound_layout = str(sound.get("layout") or "")
        expected_channels, expected_layout = output_layout(chosen_sound, analysis)
        out_w = int(out_probe.get("width") or target_w)
        out_h = int(out_probe.get("height") or target_h)
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
                "operation": "magi_upscale",
                "engine": chosen_engine,
                "model": meta.get("model") or model,
                "target": f"{out_w}x{out_h}",
                "videoTarget": target_label,
                "upscaleTarget": target_label,
                "width": out_w,
                "height": out_h,
                "aspectRatio": round(out_w / out_h, 6) if out_h else None,
                "aspect": aspect_label(out_w, out_h),
                "sourceWidth": src_w,
                "sourceHeight": src_h,
                "sourceAspect": aspect_label(src_w, src_h),
                "preview": preview,
                "sourceAssetId": source.id,
                "sourceProbe": probe,
                "outputProbe": out_probe,
                "audioEnhancement": chosen_sound,
                "audioEnhancementLabel": profile_label(chosen_sound),
                "audioChannels": sound_probe_channels or expected_channels,
                "audioLayout": sound_layout or expected_layout,
                "audioEnhancementBaked": chosen_sound != "preserve_original",
                "audioAlreadyBaked": already_baked,
                "analysisVersion": analysis.get("version"),
                "analysisSummary": analysis.get("summary"),
                "recommendation": recommendation.get("profile"),
                "recommendationReason": recommendation.get("reason"),
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
            "output_resolution": f"{out_w}x{out_h}",
            "width": out_w,
            "height": out_h,
            "aspect": aspect_label(out_w, out_h),
            "upscaleTarget": target_label,
            "preview": preview,
            "sourcePreserved": True,
            "audioEnhancement": chosen_sound,
            "audioChannels": sound_probe_channels or expected_channels,
            "audioLayout": sound_layout or expected_layout,
            "recommendation": recommendation,
            "analysis": {
                "hasAudio": analysis.get("hasAudio"),
                "channels": analysis.get("channels"),
                "summary": analysis.get("summary"),
            },
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
    sound_profile: str = "preserve_original",
) -> dict[str, Any]:
    return upscale_asset(
        db,
        project_id,
        asset_id,
        engine,
        model,
        target_resolution,
        preview=True,
        sound_profile=sound_profile,
    )


def apply_upscale(
    db: Session,
    project_id: str,
    asset_id: str,
    engine: str,
    model: str,
    target_resolution: str,
    *,
    scene_id: str = "",
    persist_scene_publish: bool = False,
    sound_profile: str = "preserve_original",
) -> dict[str, Any]:
    return enqueue_upscale(
        db,
        project_id=project_id,
        asset_id=asset_id,
        engine=engine,
        model=model,
        target_resolution=target_resolution,
        preview=False,
        scene_id=scene_id,
        persist_scene_publish=persist_scene_publish,
        sound_profile=sound_profile,
    )


def analyze_upscale_sound(db: Session, project_id: str, asset_id: str) -> dict[str, Any]:
    from .sound_enhancement import analyze_source, profile_catalog, recommend

    source = db.get(Asset, asset_id)
    if not source or source.project_id != project_id:
        raise ValueError("Asset is not in this project.")
    source_path = str(source.path or "")
    if not source_path or not Path(source_path).is_file():
        raise ValueError("Asset file is missing.")
    analysis = analyze_source(source_path)
    return {
        "ok": True,
        "assetId": asset_id,
        "analysis": analysis,
        "recommendation": recommend(analysis),
        "profiles": profile_catalog(),
    }


def enqueue_upscale(
    db: Session,
    *,
    project_id: str,
    asset_id: str,
    engine: str,
    model: str,
    target_resolution: str,
    preview: bool,
    scene_id: str = "",
    persist_scene_publish: bool = False,
    sound_profile: str = "preserve_original",
) -> dict[str, Any]:
    from .sound_enhancement import normalize_sound_request

    source = db.get(Asset, asset_id)
    if not source or source.project_id != project_id:
        raise ValueError("Asset is not in this project.")
    source_path = str(source.path or "")
    if not source_path or not Path(source_path).is_file():
        raise ValueError("Asset file is missing.")
    probe = probe_media(source_path)
    target_w, target_h, resolved = resolve_apply_target(
        int(probe.get("width") or 0),
        int(probe.get("height") or 0),
        target_resolution,
    )
    target_resolution = f"{target_w}x{target_h}"
    profile = normalize_sound_request(sound_profile)
    fingerprint = f"{asset_id}|{engine}|{model}|{target_resolution}|{profile}|{int(preview)}|{scene_id}"
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
            "targetResolution": target_resolution,
            "message": "An equivalent upscale is already in progress.",
        }
    params = {
        "assetId": asset_id,
        "engine": engine,
        "model": model,
        "targetResolution": target_resolution,
        "soundProfile": profile,
        "preview": preview,
        "fingerprint": fingerprint,
        "sceneId": scene_id,
        "persistScenePublish": bool(persist_scene_publish) and not preview,
        "sourceWidth": int(probe.get("width") or 0),
        "sourceHeight": int(probe.get("height") or 0),
        "resolvedLabel": resolved,
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
        "targetResolution": target_resolution,
        "soundProfile": profile,
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
    preview = bool(params.get("preview"))
    result = upscale_asset(
        db,
        job.project_id,
        str(params.get("assetId")),
        str(params.get("engine") or ENGINE_FFMPEG),
        str(params.get("model") or "lanczos"),
        str(params.get("targetResolution") or ""),
        preview=preview,
        sound_profile=str(params.get("soundProfile") or "preserve_original"),
    )
    if (
        result.get("ok")
        and not preview
        and params.get("persistScenePublish")
        and str(params.get("sceneId") or "").strip()
        and result.get("assetId")
    ):
        from ..director_timeline_w46.scene_publish import persist_scene_upscaled_asset

        persisted = persist_scene_upscaled_asset(
            db,
            job.project_id,
            str(params.get("sceneId")).strip(),
            str(result.get("assetId")),
        )
        result["scenePublish"] = persisted.get("scenePublish")
        result["upscaledAssetId"] = result.get("assetId")
        result["scenePersistOk"] = bool(persisted.get("ok"))
        if not persisted.get("ok"):
            result["ok"] = False
            result["message"] = persisted.get("creatorMessage") or "MAGI could not save the upscaled master on Timeline."
            return {
                **result,
                "outputPath": result.get("assetId"),
            }
    if result.get("ok") and not preview and result.get("assetId"):
        from .finishing import merge_finishing

        merge_finishing(job.project_id, {"visualResultAssetId": str(result.get("assetId"))})
    return {
        **result,
        "message": "Upscale ready" if result.get("ok") else "Upscale failed",
        "outputPath": result.get("assetId"),
    }
