"""Executor for the windowed media retake backend."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..comfy_client import comfy
from ..config import settings
from ..db import Asset, Job, Project, Scene
from ..editor_mix import probe_duration
from ..lipsync_tracks import (
    LipSyncClip,
    LipSyncTracks,
    dumps_lipsync_tracks,
    parse_lipsync_tracks,
)
from ..media_ops import run_ffmpeg
from ..workflows import build_latentsync_workflow
from ..workflows.lipsync_runtime import extract_output_path_from_history, summarize_comfy_failure
from .audio_rebuild import rebuild_audio
from .planner import (
    MediaRetakeDonorError,
    MediaRetakeError,
    WindowPlan,
    pick_donor_span,
    plan_windows,
)

ProgressCallback = Callable[[float, str], Awaitable[None] | None]


def _probe_video(path: Path) -> dict[str, Any]:
    """Return {duration, fps, width, height} via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-show_entries",
        "stream=codec_type,r_frame_rate,width,height",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr[-500:]}")
    data = json.loads(proc.stdout or "{}")
    if not isinstance(data, dict):
        raise RuntimeError(f"ffprobe returned unexpected JSON for {path}")

    fmt = data.get("format") or {}
    duration = float(fmt.get("duration") or 0.0)

    streams = data.get("streams") or []
    video = next((s for s in streams if (s.get("codec_type") or "") == "video"), None)
    if not video:
        raise RuntimeError(f"No video stream found in {path}")

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)

    fps = 0.0
    rate = video.get("r_frame_rate") or ""
    if isinstance(rate, str) and "/" in rate:
        try:
            num, den = rate.split("/")
            fps = float(num) / float(den) if float(den) else 0.0
        except Exception:
            fps = 0.0
    if not fps:
        fps = 24.0

    return {
        "duration": duration,
        "fps": fps,
        "width": width,
        "height": height,
    }


def _resolve_line_path(asset: Asset | None) -> Path:
    if asset is None:
        raise RuntimeError("Replacement line audio asset not found")
    path = Path(asset.path) if asset.path else None
    if path is None or not path.is_file():
        raise RuntimeError(f"Replacement line audio file missing: {asset.path}")
    return path


def _audio_duration_for_asset(asset_id: str, db) -> float:
    asset = db.get(Asset, asset_id)
    if not asset or not asset.path:
        raise RuntimeError(f"Audio asset {asset_id} not found")
    duration = probe_duration(Path(asset.path))
    if duration <= 0:
        raise RuntimeError(f"Could not determine duration of audio asset {asset_id}")
    return duration


def _donor_non_overlapping(
    donor_span: tuple[float, float],
    windows: list[WindowPlan],
) -> None:
    start, end = donor_span
    if start < 0 or end < 0 or start >= end:
        raise ValueError("Donor span must have positive duration and non-negative bounds")
    donor = WindowPlan(
        clip_id="__donor__",
        track_id="",
        slot=0,
        character_id=None,
        character_name=None,
        audio_asset_id="",
        start=start,
        end=end,
    )
    for w in windows:
        if not (donor.end <= w.start or donor.start >= w.end):
            raise MediaRetakeError(
                f"Provided donor span {start:.3f}-{end:.3f} overlaps window {w.clip_id}"
            )


def _update_clip_status(tracks: LipSyncTracks, clip_id: str, status: str) -> None:
    for track in tracks.tracks or []:
        for clip in track.clips or []:
            if clip.id == clip_id:
                clip.status = status
                return


def _face_crop_rect(
    roi: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    """Expand a normalized mouth ROI to a pixel face-crop rect (x, y, w, h).

    LatentSync animates the first detected face only, so each window segment is
    cropped around the bound speaker's face before syncing. The crop is generous
    (mouth box x5 wide / x8 tall, shifted up so the whole face fits) and clamped
    to the frame with even dimensions for h264.
    """
    rx, ry, rw, rh = roi
    cx = rx + rw / 2.0
    cy = ry + rh / 2.0
    crop_w = rw * 5.0
    crop_h = rh * 8.0
    face_cy = cy - 2.0 * rh  # face center sits above the mouth
    x0 = max(0.0, cx - crop_w / 2.0)
    y0 = max(0.0, face_cy - crop_h / 2.0)
    x1 = min(1.0, cx + crop_w / 2.0)
    y1 = min(1.0, face_cy + crop_h / 2.0)

    px = int(round(x0 * width))
    py = int(round(y0 * height))
    pw = int(round((x1 - x0) * width))
    ph = int(round((y1 - y0) * height))
    # Even dimensions + minimum size for the face detector.
    pw = max(256, pw - (pw % 2))
    ph = max(256, ph - (ph % 2))
    px = max(0, min(px, width - pw))
    py = max(0, min(py, height - ph))
    if px % 2:
        px -= 1
    if py % 2:
        py -= 1
    return px, py, pw, ph


def _build_composite_filter(
    crop_x: int,
    crop_y: int,
    crop_w: int,
    crop_h: int,
    fps: float,
    feather: int = 14,
) -> str:
    """Feathered overlay of the synced face crop back onto the full-frame segment.

    Inputs: [0:v] original segment, [1:v] synced crop. A white box at crop size,
    box-blurred into a soft alpha matte, hides the crop boundary.
    """
    return (
        f"[1:v]format=rgba[crop];"
        f"color=c=black:s={crop_w}x{crop_h}:r={fps},format=rgba,"
        f"drawbox=x=0:y=0:w={crop_w}:h={crop_h}:c=white:t=fill,"
        f"format=gray,boxblur={feather}[alpha];"
        f"[crop][alpha]alphamerge[cropa];"
        f"[0:v][cropa]overlay={crop_x}:{crop_y}:format=auto[vout]"
    )


def _build_splice_filter(
    windows: list[WindowPlan],
    scene_duration_sec: float,
    segment_count: int,
) -> tuple[str, str]:
    """Return (filter_complex, output_label) for concatenating master outside spans + segments."""
    sorted_windows = sorted(windows, key=lambda w: (w.start, w.end))

    # Build a single unified list of segments in strict time order.
    segments: list[tuple[str, float, float, int]] = []  # (kind, start, end, window_index)
    cursor = 0.0
    for window_index, w in enumerate(sorted_windows):
        if cursor < w.start:
            segments.append(("outside", cursor, w.start, -1))
        segments.append(("window", w.start, w.end, window_index))
        cursor = max(cursor, w.end)
    if cursor < scene_duration_sec:
        segments.append(("outside", cursor, scene_duration_sec, -1))

    filters: list[str] = []
    labels: list[str] = []

    for seg_index, (kind, start, end, window_index) in enumerate(segments):
        if kind == "outside":
            label = f"[vseg{seg_index}]"
            filters.append(
                f"[0:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS{label}"
            )
        else:
            label = f"[vwin{seg_index}]"
            filters.append(f"[{window_index + 1}:v]setpts=PTS-STARTPTS{label}")
        labels.append(label)

    if len(labels) == 1:
        filters.append(f"{labels[0]}anull[vout]")
        return ";".join(filters), "[vout]"

    concat = "".join(labels)
    filters.append(f"{concat}concat=n={len(labels)}:v=1:a=0[vout]")
    return ";".join(filters), "[vout]"


async def run_media_retake(
    db,
    job: Job,
    project: Project,
    *,
    room_tone_span: tuple[float, float] | None,
    progress_cb: ProgressCallback | None = None,
) -> Path:
    """Run a non-destructive windowed media retake and return the output path."""
    scene = db.get(Scene, job.scene_id) if job.scene_id else None
    if not scene or scene.project_id != project.id:
        raise RuntimeError("Scene not found")

    master = scene.output_path
    if not master or not Path(master).exists():
        raise RuntimeError("Scene has no rendered video — generate the scene first")
    master_path = Path(master)

    tracks = parse_lipsync_tracks(scene.lipsync_tracks_json)
    probe = _probe_video(master_path)
    scene_duration_sec = probe["duration"] or float(scene.duration_sec or 0.0)
    fps = probe["fps"] or float(scene.fps or 24)
    width = probe["width"]
    height = probe["height"]

    def _audio_duration(audio_asset_id: str) -> float:
        return _audio_duration_for_asset(audio_asset_id, db)

    windows = plan_windows(tracks, scene_duration_sec, _audio_duration)
    if not windows:
        raise RuntimeError("No usable lip-sync windows found")

    if room_tone_span is not None:
        donor_span = room_tone_span
    else:
        donor_span = pick_donor_span(windows, scene_duration_sec)
    _donor_non_overlapping(donor_span, windows)

    work_dir = (
        settings.data_dir
        / "projects"
        / project.id
        / "renders"
        / f"_retake_{job.id[:8]}"
    )
    work_dir.mkdir(parents=True, exist_ok=True)

    line_paths: list[Path] = []
    segment_paths: list[Path] = []
    synced_paths: list[Path] = []

    total = len(windows)

    for i, window in enumerate(windows):
        if progress_cb:
            await _maybe_async(progress_cb, (i + 0.2) / total, f"Cutting segment {window.clip_id}")

        seg_path = work_dir / f"seg_{window.clip_id}_{job.id[:8]}.mp4"
        run_ffmpeg(
            [
                "-ss",
                str(window.start),
                "-to",
                str(window.end),
                "-i",
                str(master_path),
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-an",
                str(seg_path),
            ]
        )
        segment_paths.append(seg_path)

        line_asset = db.get(Asset, window.audio_asset_id)
        line_path = _resolve_line_path(line_asset)
        line_paths.append(line_path)

        # Speaker targeting: LatentSync animates the first detected face, so
        # when the track carries a mouth ROI we sync a face crop of the bound
        # speaker and composite it back — never the wrong character's mouth.
        crop_rect: tuple[int, int, int, int] | None = None
        sync_source = seg_path
        if window.roi is not None:
            crop_rect = _face_crop_rect(window.roi, width, height)
            cx, cy, cw, ch = crop_rect
            crop_path = work_dir / f"crop_{window.clip_id}_{job.id[:8]}.mp4"
            run_ffmpeg(
                [
                    "-i",
                    str(seg_path),
                    "-vf",
                    f"crop={cw}:{ch}:{cx}:{cy}",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "16",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(fps),
                    "-an",
                    str(crop_path),
                ]
            )
            sync_source = crop_path

        seg_video_name = await comfy.upload_file_copy(
            sync_source,
            filename=sync_source.name,
            subfolder="studio",
        )
        line_audio_name = await comfy.upload_file_copy(
            line_path,
            filename=line_path.name,
            subfolder="studio",
        )

        if progress_cb:
            await _maybe_async(progress_cb, (i + 0.5) / total, f"LatentSync {window.clip_id}")

        wf = build_latentsync_workflow(
            video_path=str(settings.comfy_input_dir / seg_video_name.replace("/", "\\")),
            audio_path=line_audio_name or "",
            filename_prefix=f"studio/{project.id[:8]}_mr_{window.clip_id}",
        )
        # D_LatentSyncNode can also take a raw audio_file path directly.
        if "2" in wf and isinstance(wf["2"].get("inputs"), dict):
            wf["2"]["inputs"]["audio_file"] = line_audio_name or ""

        prompt_id = await comfy.queue_prompt(wf, workflow_key="lipsync.latentsync")

        entry = await _poll_comfy_for_media_retake(prompt_id, window.clip_id)

        synced_path = extract_output_path_from_history(entry)
        if not synced_path:
            files = comfy.find_output_files(entry)
            if files:
                synced_path = files[0]
        if not synced_path or not synced_path.is_file():
            raise RuntimeError(f"No synced video output for window {window.clip_id}")

        # Normalize the synced segment to the exact window dimensions and length.
        synced_probe = _probe_video(synced_path)
        synced_dur = synced_probe["duration"]
        window_len = window.end - window.start
        norm_path = work_dir / f"norm_{window.clip_id}_{job.id[:8]}.mp4"
        target_w, target_h = width, height
        if crop_rect is not None:
            target_w, target_h = crop_rect[2], crop_rect[3]
        vf = f"scale={target_w}:{target_h},fps={fps}"
        pad_sec = window_len - synced_dur
        if pad_sec > 0.001:
            vf += f",tpad=stop_mode=clone:stop={pad_sec:.6f}"

        run_ffmpeg(
            [
                "-i",
                str(synced_path),
                "-vf",
                vf,
                "-t",
                str(window_len),
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-an",
                str(norm_path),
            ]
        )

        if crop_rect is not None:
            # Composite the synced face crop back onto the original segment.
            cx, cy, cw, ch = crop_rect
            comp_path = work_dir / f"comp_{window.clip_id}_{job.id[:8]}.mp4"
            run_ffmpeg(
                [
                    "-i",
                    str(seg_path),
                    "-i",
                    str(norm_path),
                    "-filter_complex",
                    _build_composite_filter(cx, cy, cw, ch, fps),
                    "-map",
                    "[vout]",
                    "-t",
                    str(window_len),
                    "-c:v",
                    "libx264",
                    "-crf",
                    "16",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(fps),
                    "-an",
                    str(comp_path),
                ]
            )
            synced_paths.append(comp_path)
        else:
            synced_paths.append(norm_path)

        if progress_cb:
            await _maybe_async(progress_cb, (i + 1.0) / total, f"Synced {window.clip_id}")

    # Splice master outside spans and normalized window segments in time order.
    if progress_cb:
        await _maybe_async(progress_cb, 1.0, "Splicing video")
    splice_path = work_dir / f"spliced_{job.id[:8]}.mp4"
    splice_filter, splice_label = _build_splice_filter(
        windows, scene_duration_sec, len(synced_paths)
    )
    splice_args: list[str] = ["-i", str(master_path)]
    for norm_path in synced_paths:
        splice_args.extend(["-i", str(norm_path)])
    splice_args.extend(
        [
            "-filter_complex",
            splice_filter,
            "-map",
            splice_label,
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-an",
            str(splice_path),
        ]
    )
    run_ffmpeg(splice_args)

    # Rebuild audio: room-tone bed + replacement lines + crossfades.
    if progress_cb:
        await _maybe_async(progress_cb, 1.0, "Rebuilding audio")
    rebuilt_wav = work_dir / f"audio_{job.id[:8]}.wav"
    rebuild_audio(
        master_path=master_path,
        line_paths=line_paths,
        windows=windows,
        donor_span=donor_span,
        out_wav=rebuilt_wav,
        sample_rate=32000,
        crossfade_ms=30,
    )

    # Final mux.
    if progress_cb:
        await _maybe_async(progress_cb, 1.0, "Muxing final retake")
    out_path = (
        settings.data_dir
        / "projects"
        / project.id
        / "renders"
        / f"scene_{scene.index}_retake_{uuid.uuid4().hex[:6]}.mp4"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-i",
            str(splice_path),
            "-i",
            str(rebuilt_wav),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "32000",
            "-ac",
            "2",
            str(out_path),
        ]
    )

    # Persist retake output on the scene and mark clips synced.
    scene.lipsync_output_path = str(out_path)
    scene.lipsync_enabled = 1
    for window in windows:
        _update_clip_status(tracks, window.clip_id, "synced")
    scene.lipsync_tracks_json = dumps_lipsync_tracks(tracks)

    # Register library asset for the retake video.
    master_asset = (
        db.query(Asset)
        .filter(Asset.project_id == project.id, Asset.path == str(master_path))
        .first()
    )
    parent_id = master_asset.id if master_asset else None
    provenance = {
        "mediaRetake": True,
        "sourceMaster": master_path.name,
        "windows": [
            {
                "clipId": w.clip_id,
                "trackId": w.track_id,
                "slot": w.slot,
                "start": w.start,
                "end": w.end,
                "characterId": w.character_id,
                "characterName": w.character_name,
                "audioAssetId": w.audio_asset_id,
                "roi": list(w.roi) if w.roi else None,
            }
            for w in windows
        ],
        "donorSpan": {"start": donor_span[0], "end": donor_span[1]},
        "models": {
            "lipsync": "D_LatentSyncNode (ComfyUI_LatentSync)",
            "voiceProvider": "qwen3-tts",
        },
        "jobId": job.id,
    }
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project.id,
        tag=f"scene_{scene.index}_retake",
        kind="video",
        filename=out_path.name,
        path=str(out_path),
        comfy_name="",
        scope="project",
        parent_asset_id=parent_id,
        prompt_meta_json=json.dumps(provenance),
        labels_json=json.dumps(["media-retake", "lipsync", f"scene-{scene.index}"]),
        production_approval="none",
    )
    db.add(asset)
    db.flush()
    try:
        from ..asset_graph import add_edge

        for window in windows:
            audio_asset = db.get(Asset, window.audio_asset_id)
            if audio_asset:
                add_edge(db, asset.id, audio_asset.id, relation="uses_audio")
        if parent_id:
            add_edge(db, asset.id, parent_id, relation="derived_from")
    except Exception:
        # Provenance graph edges are supplementary — the canonical provenance
        # record is asset.prompt_meta_json, committed below regardless. Never
        # hide the failure: log it so edge loss is diagnosable.
        logging.getLogger(__name__).exception("media retake provenance edge write failed")

    db.commit()
    return out_path


async def _maybe_async(fn: ProgressCallback | None, p: float, msg: str) -> None:
    if fn is None:
        return
    result = fn(p, msg)
    if hasattr(result, "__await__"):
        await result


async def _poll_comfy_for_media_retake(prompt_id: str, clip_id: str) -> dict[str, Any]:
    """Poll ComfyUI history every 4s for up to 15 minutes."""
    import asyncio

    timeout = 900.0
    elapsed = 0.0
    interval = 4.0
    while elapsed < timeout:
        history = await comfy.get_history(prompt_id)
        entry = history.get(prompt_id, {}) if isinstance(history, dict) else {}
        status = entry.get("status", {}) if isinstance(entry, dict) else {}
        status_str = (status.get("status_str") or "").lower()
        completed = status.get("completed")

        if completed is True or status_str == "success":
            return entry

        messages = status.get("messages") or []
        joined = json.dumps(messages).lower()
        if (
            status_str == "error"
            or "execution_error" in joined
            or '"error":' in joined
        ) and not (
            completed is True or status_str == "success"
        ):
            summary = summarize_comfy_failure(entry) or "LatentSync failed"
            raise RuntimeError(f"Window {clip_id}: {summary}")

        await asyncio.sleep(interval)
        elapsed += interval

    raise RuntimeError(f"Window {clip_id}: timed out waiting for LatentSync (15m)")
