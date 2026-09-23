"""Unified MAGI finishing render (finishing.audio is sole mix authority for this path) — edit → overlays → color → audio → composite → late upscale → encode."""

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
from .authority import finishing_audio_labels
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
            fps = max(int(sequence.get("frameRate") or 24), 1)
            overlaid = _maybe_overlay(db, job.project_id, current, work / "overlay.mp4", fps=fps)
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

        merge_finishing(
            job.project_id,
            {
                "visualResultAssetId": asset.id,
                "render": {"lastJobId": job.id, "profile": profile, "assetId": asset.id},
            },
        )
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


def _count_overlay_elements(composition: dict[str, Any]) -> int:
    """Count burnable overlay elements (text/vector/image/group children)."""

    def walk(els: list[Any]) -> int:
        n = 0
        for el in els or []:
            if not isinstance(el, dict) or el.get("visible") is False:
                continue
            t = el.get("type")
            if t == "group":
                n += walk(list(el.get("children") or []))
            elif t in {"text", "vector", "image"}:
                n += 1
        return n

    return walk(list(composition.get("overlays") or []))


def _overlay_has_fade(el: dict[str, Any]) -> bool:
    """Return True if this element (or any group child) requests a fade."""
    if not isinstance(el, dict):
        return False
    if el.get("animationPreset") == "fade":
        return True
    if el.get("type") == "group":
        return any(_overlay_has_fade(c) for c in el.get("children") or [])
    return False


def _overlay_paint_key(el: dict[str, Any]) -> tuple[int, int]:
    """Combined Objects order: (objectsTrack, zIndex). Objects 2 paints above Objects 1."""
    slot = el.get("objectsTrack") if isinstance(el, dict) else 1
    try:
        slot_i = int(slot or 1)
    except (TypeError, ValueError):
        slot_i = 1
    if slot_i not in (1, 2):
        slot_i = 1
    try:
        z = int((el or {}).get("zIndex") or 0)
    except (TypeError, ValueError):
        z = 0
    return (slot_i, z)


def _maybe_overlay(db: Session, project_id: str, video: Path, dest: Path, *, fps: int = 24) -> Path | None:
    """Burn project overlay compositions into the edit video, or honest no-op/refuse.

    - No compositions / empty overlays ? return None (nothing to burn).
    - Overlays present ? Render each top-level overlay as a timed PNG and FFmpeg
      overlay it with enable='between(t,start,end)'.
    - Groups are burned as a single layer (children are not split).
    - Combined order (objectsTrack, zIndex) is preserved. Viewer guides are never burned.
    - Burn failure with overlays present ? raise (never silent skip while docs/UI
      claim an overlays stage).
    """
    from PIL import Image

    from .composition.render import render_composition_to_png
    from .overlays import store as overlay_store

    comps: list[dict[str, Any]] = []
    for item in overlay_store.list_compositions(project_id):
        cid = item.get("compositionId")
        if not cid:
            continue
        full = overlay_store.get_composition(project_id, str(cid))
        if full and _count_overlay_elements(full) > 0:
            comps.append(full)

    if not comps:
        return None

    # Collect top-level overlays across all project compositions, sorted by zIndex.
    top_overlays: list[tuple[int, int, dict[str, Any]]] = []
    for comp in comps:
        cw = int(comp.get("canvasWidth") or 1920)
        ch = int(comp.get("canvasHeight") or 1080)
        for el in comp.get("overlays") or []:
            if isinstance(el, dict) and el.get("visible") is not False:
                top_overlays.append((cw, ch, el))
    if not top_overlays:
        return None
    top_overlays.sort(key=lambda item: _overlay_paint_key(item[2]))

    probe = probe_media(video)
    width = int(probe.get("width") or 0) or int(comps[0].get("canvasWidth") or 1920)
    height = int(probe.get("height") or 0) or int(comps[0].get("canvasHeight") or 1080)
    if width < 2 or height < 2:
        raise RuntimeError(
            "MAGI final render cannot burn overlays: edit video has invalid dimensions."
        )
    duration = float(probe.get("duration") or 0.0)
    frames = int(probe.get("frames") or 0)
    if duration <= 0 and frames > 0 and fps > 0:
        duration = frames / fps
    if duration <= 0:
        duration = 60.0

    # Resolve image asset paths for render_composition_to_png.
    asset_paths: dict[str, str] = {}

    def _collect_image_assets(els: list[Any]) -> None:
        for child in els:
            if not isinstance(child, dict):
                continue
            if child.get("type") == "image" and child.get("assetId"):
                p = _asset_path(db, project_id, child.get("assetId"))
                if p:
                    asset_paths[str(child["assetId"])] = str(p)
            if child.get("type") == "group":
                _collect_image_assets(child.get("children") or [])

    for _cw, _ch, el in top_overlays:
        _collect_image_assets([el])

    work = dest.parent
    try:
        inputs: list[str] = ["-i", str(video)]
        for index, (_cw, _ch, el) in enumerate(top_overlays):
            render_comp = {
                "schemaVersion": 1,
                "compositionId": f"burn_{index:03d}",
                "projectId": project_id,
                "sourceAssetId": None,
                "canvasWidth": width,
                "canvasHeight": height,
                "designCanvasWidth": _cw,
                "designCanvasHeight": _ch,
                "overlays": [el],
                "safeAreaEnabled": True,
            }
            part_path = work / f"overlay_{index:03d}.png"
            render_composition_to_png(
                source_image_path=None,
                composition=render_comp,
                out_path=part_path,
                asset_paths=asset_paths,
            )
            # A still PNG is t=0 only. fade=st=START would keep it fully
            # transparent for the whole shot. Loop faded plates so timestamps exist.
            if _overlay_has_fade(el):
                inputs.extend(
                    [
                        "-loop",
                        "1",
                        "-framerate",
                        str(max(int(fps), 1)),
                        "-t",
                        f"{duration:.3f}",
                        "-i",
                        str(part_path),
                    ]
                )
            else:
                inputs.extend(["-i", str(part_path)])

        filters: list[str] = []
        current_label = "0:v"
        for index, (_cw, _ch, el) in enumerate(top_overlays):
            input_label = f"{index + 1}:v"
            start_frame = el.get("startFrame")
            end_frame = el.get("endFrame")
            start_t = 0.0
            end_t = duration
            enable_expr = ""
            if start_frame is not None or end_frame is not None:
                start_t = (float(start_frame) if start_frame is not None else 0.0) / fps
                end_t = (float(end_frame) if end_frame is not None else (frames or int(duration * fps))) / fps
                start_t = max(0.0, start_t)
                end_t = min(end_t, duration)
                enable_expr = f":enable='between(t\\,{start_t:.3f}\\,{end_t:.3f})'"

            if _overlay_has_fade(el):
                fade_d = min(0.35, max(0.0, (end_t - start_t) / 2))
                fade_out_st = max(start_t, end_t - fade_d)
                faded_label = f"f{index}"
                filters.append(
                    f"[{input_label}]format=rgba,"
                    f"fade=t=in:st={start_t:.3f}:d={fade_d:.3f}:alpha=1,"
                    f"fade=t=out:st={fade_out_st:.3f}:d={fade_d:.3f}:alpha=1"
                    f"[{faded_label}]"
                )
                input_label = faded_label

            is_last = index == len(top_overlays) - 1
            out_label = "vout" if is_last else f"v{index}"
            filters.append(
                f"[{current_label}][{input_label}]overlay=0:0:format=auto{enable_expr}[{out_label}]"
            )
            current_label = out_label

        audio_args = ["-c:a", "copy"] if probe_has_audio(video) else ["-an"]
        maps = ["-map", f"[{current_label}]"]
        if probe_has_audio(video):
            maps = ["-map", "0:a?"] + maps
        run_ffmpeg(
            [
                *inputs,
                "-filter_complex",
                ";".join(filters),
                *maps,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-pix_fmt",
                "yuv420p",
                *audio_args,
                str(dest),
            ]
        )
        if not dest.is_file():
            raise RuntimeError("Overlay burn produced no output file.")
        return dest
    except Exception as exc:
        raise RuntimeError(
            "MAGI final render cannot burn overlays into the video. "
            f"{exc}. Fix the overlay composition or set includeOverlays=false."
        ) from exc


def _mix_audio(
    db: Session,
    project_id: str,
    sequence: dict[str, Any],
    finishing: dict[str, Any],
    video: Path,
    dest: Path,
) -> tuple[Path, dict[str, Any]]:
    """Mix MAGI finishing.audio stems only.

    Authority: sequence.json finishing.audio (musicAssetId/sfxAssetId).
    Does NOT read Audio Studio mix.json or legacy editor tracks.
    """
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
        return video, {"mixed": False, "stems": [], **finishing_audio_labels()}

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
    meta = {
        "mixed": True,
        "stems": [{"role": role, "gain": gain} for role, _path, gain in stems],
        "musicAssetId": audio_state.get("musicAssetId"),
        "sfxAssetId": audio_state.get("sfxAssetId"),
        **finishing_audio_labels(),
    }
    return dest, meta
