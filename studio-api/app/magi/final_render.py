"""Unified MAGI finishing render — edit → overlays → color → audio → composite → late upscale → encode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset, Job
from ..editor_mix import MixStem, probe_has_audio
from ..generation_tools.lineage import register_derived_asset
from . import jobs as magi_jobs
from .color_grading import COLOR_PRESETS, apply_color_grade, compile_filter_string
from .finishing import clip_grade, finishing_of
from .media import cleanup_dir, disk_preflight, new_temp_dir, probe_media, run_ffmpeg
from .sequence.store import get_sequence
from .upscaling import ENGINE_FFMPEG, ENGINE_GPU, upscale_frame

DEFAULT_MUSIC_GAIN = 0.28
DEFAULT_SFX_GAIN = 0.35
PICTURE_TRACK_KINDS = {"video", "image"}


def picture_clips(sequence: dict[str, Any]) -> list[dict[str, Any]]:
    """Picture-track clips only. Audio/text/fx clips are mixed later, not edited as video."""
    tracks = {t.get("id"): t for t in (sequence.get("tracks") or [])}
    selected: list[dict[str, Any]] = []
    for clip in sequence.get("clips") or []:
        if not clip.get("assetId"):
            continue
        track = tracks.get(clip.get("trackId")) or {}
        kind = str(track.get("kind") or "")
        if tracks and kind and kind not in PICTURE_TRACK_KINDS:
            continue
        selected.append(clip)
    return selected


def enqueue_final_render(
    db: Session,
    project_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    profile = str(body.get("profile") or "final")
    fingerprint = json.dumps(
        {
            "profile": profile,
            "range": body.get("range") or "entire",
            "resolution": body.get("resolution") or body.get("targetResolution"),
            "upscale": body.get("upscale"),
            "includeColor": body.get("includeColor", True),
            "includeAudio": body.get("includeAudio", True),
        },
        sort_keys=True,
    )
    params = {
        **body,
        "profile": profile,
        "fingerprint": f"render|{fingerprint}",
    }
    existing = magi_jobs.find_active_duplicate(db, project_id, "magi_final_render", params["fingerprint"])
    if existing is not None:
        return {
            "ok": True,
            "queued": existing.status in magi_jobs.ACTIVE,
            "jobId": existing.id,
            "status": existing.status,
            "stage": existing.stage,
            "profile": profile,
            "duplicate": True,
            "message": "An equivalent MAGI render is already in progress.",
        }
    job = magi_jobs.enqueue_job(
        db,
        project_id=project_id,
        kind="magi_final_render",
        params=params,
        message="Queued MAGI final render",
    )
    if job.status == "queued":
        magi_jobs.start_background(job.id, lambda jid: magi_jobs.run_with_session(jid, run_final_render_job))
    return {
        "ok": True,
        "queued": job.status in {"queued", "running"},
        "jobId": job.id,
        "status": job.status,
        "stage": job.stage,
        "profile": profile,
        "duplicate": False,
    }


def run_final_render_job(db: Session, job: Job) -> dict[str, Any]:
    params = json.loads(job.params_json or "{}")
    profile = str(params.get("profile") or "final")
    preview = profile == "preview"
    sequence = get_sequence(job.project_id)
    finishing = finishing_of(sequence)
    clips = picture_clips(sequence)
    if not clips:
        raise RuntimeError("Add a clip to MAGI before rendering.")

    range_mode = str(params.get("range") or finishing.get("audio", {}).get("range") or "entire")
    selected_clip_id = params.get("clipId") or params.get("selectedClipId")
    if range_mode in {"clip", "selected"} and selected_clip_id:
        clips = [c for c in clips if c.get("id") == selected_clip_id] or clips[:1]
    elif preview:
        clips = clips[:1]

    job.stage = "Dispatching"
    job.message = "Preparing finishing render"
    db.commit()
    if magi_jobs.job_cancelled(db, job.id):
        return {"ok": False, "message": "Cancelled"}

    work = new_temp_dir("render")
    try:
        disk_preflight(need_bytes=2_000_000_000, label="MAGI final render")
        job.stage = "Rendering"
        job.progress = 0.15
        db.commit()
        edit_path = _build_edit(db, job.project_id, clips, sequence, work / "edit.mp4", preview=preview)

        current = edit_path
        if params.get("includeOverlays", True):
            overlaid = _maybe_overlay(db, job.project_id, current, work / "overlay.mp4")
            if overlaid:
                current = overlaid

        grade_meta: dict[str, Any] = {}
        if params.get("includeColor", True):
            grade = clip_grade(sequence, clips[0].get("id"))
            preset_id = grade.get("presetId") or ""
            grade_params = dict(COLOR_PRESETS.get(preset_id, {}).get("params") or {})
            grade_params.update(grade.get("params") or {})
            if grade_params:
                graded = work / "graded.mp4"
                apply_color_grade(str(current), str(graded), grade_params)
                current = graded
                grade_meta = {"preset": preset_id or "custom", "parameters": grade_params}

        job.progress = 0.45
        db.commit()
        audio_meta: dict[str, Any] = {}
        if params.get("includeAudio", True):
            mixed = _mix_audio(db, job.project_id, sequence, finishing, current, work / "mixed.mp4")
            current = mixed[0]
            audio_meta = mixed[1]

        job.progress = 0.6
        job.stage = "Encoding"
        db.commit()

        upscale_spec = params.get("upscale")
        if upscale_spec is None:
            upscale_spec = finishing.get("upscale") or {}
        upscale_meta: dict[str, Any] = {}
        if isinstance(upscale_spec, dict) and (upscale_spec.get("enabled") or upscale_spec.get("engine")):
            engine = str(upscale_spec.get("engine") or (ENGINE_FFMPEG if preview else ENGINE_GPU))
            if preview and engine == ENGINE_GPU:
                engine = ENGINE_FFMPEG
            model = str(upscale_spec.get("model") or ("lanczos" if engine == ENGINE_FFMPEG else "realesrgan-x4plus"))
            target = str(
                params.get("resolution")
                or params.get("targetResolution")
                or upscale_spec.get("target")
                or "1920x1080"
            )
            tw, th = (1920, 1080)
            if "x" in target.lower():
                parts = target.lower().split("x")
                tw, th = int(parts[0]), int(parts[1])
            elif target.upper() == "4K":
                tw, th = 3840, 2160
            elif target.upper() == "1080P":
                tw, th = 1920, 1080
            upscaled = work / "upscaled.mp4"
            upscale_frame(str(current), str(upscaled), engine, model, tw, th)
            current = upscaled
            upscale_meta = {"engine": engine, "model": model, "target": f"{tw}x{th}"}

        if magi_jobs.job_cancelled(db, job.id):
            return {"ok": False, "message": "Cancelled"}

        probe = probe_media(current)
        asset = register_derived_asset(
            db,
            project_id=job.project_id,
            source_path=current,
            kind="video",
            tag="magi_final" if not preview else "magi_preview",
            parent_asset_id=clips[0].get("assetId"),
            op="magi_final_render",
            model=profile,
            prompt_meta={
                "operation": "final_render",
                "sequenceId": sequence.get("id"),
                "renderProfile": profile,
                "sourceAssets": [c.get("assetId") for c in clips],
                "grade": grade_meta,
                "audio": audio_meta,
                "upscale": upscale_meta,
                "probe": probe,
                "preview": preview,
            },
            library_key="video.generated",
        )
        db.commit()
        from .finishing import merge_finishing

        merge_finishing(job.project_id, {"render": {"lastJobId": job.id, "profile": profile, "assetId": asset.id}})
        return {
            "ok": True,
            "assetId": asset.id,
            "output_asset_id": asset.id,
            "profile": profile,
            "preview": preview,
            "probe": probe,
            "grade": grade_meta,
            "audio": audio_meta,
            "upscale": upscale_meta,
            "message": "Final render ready" if not preview else "Preview render ready",
            "sourcePreserved": True,
        }
    finally:
        cleanup_dir(work)


def _asset_path(db: Session, project_id: str, asset_id: str | None) -> Path | None:
    if not asset_id:
        return None
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id or not asset.path:
        return None
    path = Path(asset.path)
    return path if path.is_file() else None


def _build_edit(
    db: Session,
    project_id: str,
    clips: list[dict[str, Any]],
    sequence: dict[str, Any],
    dest: Path,
    *,
    preview: bool,
) -> Path:
    fps = max(int(sequence.get("frameRate") or 24), 1)
    parts: list[Path] = []
    work = dest.parent
    for index, clip in enumerate(clips):
        src = _asset_path(db, project_id, clip.get("assetId"))
        if src is None:
            continue
        start = max(int(clip.get("inPoint") or 0), 0) / fps
        duration = max(int(clip.get("durationFrames") or clip.get("outPoint") or fps), 1) / fps
        if preview:
            duration = min(duration, 3.0)
        part = work / f"clip_{index:02d}.mp4"
        audio_args = ["-c:a", "aac"] if probe_has_audio(src) else ["-an"]
        run_ffmpeg(
            [
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(src),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-pix_fmt",
                "yuv420p",
                *audio_args,
                str(part),
            ]
        )
        parts.append(part)
    if not parts:
        raise RuntimeError("No playable MAGI clips were found for render.")
    if len(parts) == 1:
        dest.write_bytes(parts[0].read_bytes()) if parts[0] != dest else None
        if parts[0] != dest:
            import shutil

            shutil.copy2(parts[0], dest)
        return dest
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dest)])
    return dest


def _maybe_overlay(db: Session, project_id: str, video: Path, dest: Path) -> Path | None:
    """Skip video overlay burn unless a still composition can be rendered safely.

    The Pillow overlay path is image-first. A black full-canvas fallback would
    hide the edit, so this stage is omitted rather than faked.
    """
    return None


def _mix_audio(
    db: Session,
    project_id: str,
    sequence: dict[str, Any],
    finishing: dict[str, Any],
    video: Path,
    dest: Path,
) -> tuple[Path, dict[str, Any]]:
    audio_state = finishing.get("audio") if isinstance(finishing.get("audio"), dict) else {}
    stems: list[tuple[str, Path, float]] = []
    owner = project_id or sequence.get("projectId") or ""
    music = _asset_path(db, owner, audio_state.get("musicAssetId"))
    sfx = _asset_path(db, owner, audio_state.get("sfxAssetId"))
    if music:
        stems.append(("music", music, DEFAULT_MUSIC_GAIN))
    if sfx:
        stems.append(("sfx", sfx, DEFAULT_SFX_GAIN))
    # Dialogue stays on the picture (source video audio). Extra A2/A3 clips are
    # already represented by finishing.music/sfx and must not be stacked at 1.0.

    if not stems:
        return video, {"mixed": False, "stems": []}

    inputs = ["-i", str(video)]
    for _role, path, _gain in stems:
        inputs.extend(["-i", str(path)])
    filters = []
    mix_labels = []
    if probe_has_audio(video):
        filters.append("[0:a]volume=1.0[a0]")
        mix_labels.append("[a0]")
    for index, (_role, _path, gain) in enumerate(stems, start=1):
        label = f"a{index}"
        filters.append(f"[{index}:a]volume={gain:.2f}[{label}]")
        mix_labels.append(f"[{label}]")
    filters.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:normalize=0:dropout_transition=0[aout]")
    run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(dest),
        ]
    )
    return dest, {
        "mixed": True,
        "stems": [{"role": role, "gain": gain} for role, _path, gain in stems],
        "musicAssetId": audio_state.get("musicAssetId"),
        "sfxAssetId": audio_state.get("sfxAssetId"),
    }
