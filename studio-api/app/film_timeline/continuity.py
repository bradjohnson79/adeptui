"""Film Timeline continuity. One packet on the segment. ShotState stays the shot authority."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from ..db import Asset
from ..media_clip import extract_frame_png, probe_video_duration
from .contracts import Segment, Shot

log = logging.getLogger("adept.film_timeline")

PACKET_VERSION = 5
_TAIL_OFFSETS = (1.0, 0.5, 0.04)
_BRIGHTNESS_WARN = 35.0
_CAMERA_WORDS = ("camera", "dolly", "crane", "pan", "tilt", "push-in", "push in", "track", "zoom", "handheld")
_LIGHT_WORDS = ("light", "lighting", "shadow", "exposure", "grade", "color")


def fingerprint(asset_id: str) -> str:
    return f"v{PACKET_VERSION}:{asset_id}"


def cached_packet(segment: Segment) -> dict | None:
    packet = segment.generationMetadata.get("continuity")
    if not isinstance(packet, dict):
        return None
    if packet.get("fingerprint") != fingerprint(segment.assetId or ""):
        return None
    return packet


def notes_for_prompt(prompt: str, notes: dict | None) -> dict:
    """The Timed Prompt wins. Inherited camera or light notes are dropped when the prompt already says so."""

    if not isinstance(notes, dict):
        return {}
    text = (prompt or "").lower()
    kept: dict[str, str] = {}
    camera = str(notes.get("camera") or "").strip()
    light = str(notes.get("light") or "").strip()
    motion = str(notes.get("motion") or "").strip()
    if camera and not any(word in text for word in _CAMERA_WORDS):
        kept["camera"] = camera
    if light and not any(word in text for word in _LIGHT_WORDS):
        kept["light"] = light
    if motion and "motion" not in text and "moving" not in text:
        kept["motion"] = motion
    return kept


def continuation_opening_frame(previous: Segment | None, *, prepend: bool = False, interior_retake: bool = False) -> str:
    """Still that a continuing shot must open on.

    A new shot has no previous segment, so it is not locked. A prepend arrives
    at the picture that already opens the scene. An interior re-take keeps the
    frame marked on that window.
    """

    if previous is None or prepend or interior_retake:
        return ""
    frame = str(previous.lastFrameAssetId or "").strip()
    if frame:
        return frame
    packet = previous.generationMetadata.get("continuity")
    if isinstance(packet, dict):
        return str(packet.get("lastFrameAssetId") or "").strip()
    return ""


def opening_frame_clause(*, seedance_reference: bool = False) -> str:
    """Reinforcement only. The start image or H3 tail clip is the authority, not this sentence."""

    lead = (
        "@Image1 is the visual state at the first moment of this shot. "
        if seedance_reference
        else "The supplied start image is the visual state at the first moment of this shot. "
    )
    return (
        lead
        + "Begin from that pose, crop, camera, lighting, and placement. "
        + "Motion starts there. Do not cut to a different composition."
    )


def continuation_anchor_kind(*, local_h3: bool, supports_start_frame: bool) -> str:
    """How a continuing shot uses the previous ending.

    start_image: the generator's native first-frame input.
    reference_tail: MiniMax H3's ending clip. It is not pasted onto frame 0.
    reference_image: a still reference when the provider has no start-frame input.
    """

    if local_h3:
        return "reference_tail"
    if supports_start_frame:
        return "start_image"
    return "reference_image"


def continuity_clause(prompt: str, previous: Segment | None) -> str:
    if previous is None:
        return ""
    packet = cached_packet(previous) or {}
    notes = notes_for_prompt(prompt, packet.get("notes") if isinstance(packet.get("notes"), dict) else None)
    if not notes:
        return ""
    bits = [notes[key] for key in ("camera", "light", "motion") if notes.get(key)]
    if not bits:
        return ""
    return "Keep what is already on screen: " + "; ".join(bits) + "."


def mark_downstream_continuation_stale(shot: Shot, segment_id: str) -> None:
    """The next shot was continued from this one. Mark only that seam.

    The shot that changed is left alone, and nothing downstream is regenerated.
    """

    ordered = sorted(shot.segments, key=lambda item: item.order)
    for index, segment in enumerate(ordered):
        if segment.id != segment_id:
            continue
        if index + 1 >= len(ordered):
            return
        nxt = ordered[index + 1]
        seam_packet = nxt.generationMetadata.get("continuity")
        if not isinstance(seam_packet, dict):
            seam_packet = {}
            nxt.generationMetadata["continuity"] = seam_packet
        seam_packet["seamStale"] = True
        seam_packet["seam"] = {
            "status": "stale",
            "warning": "The previous shot changed. Continue or Re-Take this part so it starts from the new ending.",
        }
        return


def invalidate_segment_continuity(shot: Shot, segment_id: str) -> None:
    ordered = sorted(shot.segments, key=lambda item: item.order)
    for segment in ordered:
        if segment.id != segment_id:
            continue
        packet = segment.generationMetadata.get("continuity")
        if isinstance(packet, dict):
            segment.generationMetadata["retakePreviousContinuity"] = packet
        segment.generationMetadata.pop("continuity", None)
        segment.lastFrameAssetId = None
        mark_downstream_continuation_stale(shot, segment_id)
        return


def restore_retake_continuity(segment: Segment) -> None:
    previous = segment.generationMetadata.pop("retakePreviousContinuity", None)
    if isinstance(previous, dict):
        segment.generationMetadata["continuity"] = previous
        frame = previous.get("lastFrameAssetId")
        if isinstance(frame, str) and frame:
            segment.lastFrameAssetId = frame


def ensure_segment_continuity(db: Session, project_id: str, scene_id: str, shot: Shot, segment: Segment) -> dict:
    """Extract and cache this segment's packet. Failures stay on the packet and do not fail the shot."""

    if segment.status != "completed" or not segment.assetId:
        return {}
    cached = cached_packet(segment)
    if cached is not None:
        return cached
    packet: dict = {
        "version": PACKET_VERSION,
        "fingerprint": fingerprint(segment.assetId),
        "assetId": segment.assetId,
        "sceneId": scene_id,
        "tailFrameAssetIds": [],
        "notes": {},
        "omni": {"status": "unavailable", "reason": "not_run"},
        "seam": None,
    }
    try:
        _fill_frames(db, project_id, segment, packet)
        # Frame extraction inserts Asset rows, which opens a SQLite write
        # transaction. Release it before the Omni tail review (which may run for
        # tens of seconds): the UI auto-syncs every 4s and its save_film commit
        # must not hit "database is locked" for the whole analysis (F1 root cause).
        db.commit()
        _fill_omni(db, project_id, segment, packet)
        _fill_seam(db, shot, segment, packet)
    except Exception as exc:
        log.exception("film-timeline continuity failed segment=%s", segment.id)
        packet["error"] = str(exc)
    segment.generationMetadata["continuity"] = packet
    if packet.get("lastFrameAssetId"):
        segment.lastFrameAssetId = str(packet["lastFrameAssetId"])
    return packet


def _video_path(db: Session, asset_id: str) -> Path | None:
    asset = db.get(Asset, asset_id)
    if asset is None or not asset.path:
        return None
    path = Path(asset.path)
    return path if path.exists() else None


def _probe_frame_count(source: Path) -> int | None:
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(source),
        ],
        capture_output=True,
        text=True,
    )
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0 or not raw.isdigit():
        return None
    count = int(raw)
    return count if count > 0 else None


def extract_continuity_tail(
    source: Path,
    dest: Path,
    *,
    frame_count: int,
    fps: int = 24,
    end_frame: int | None = None,
) -> dict:
    """Write a temporary tail.

    The default ends on the source's last frame. A Re-Take passes end_frame
    so the tail ends on the mark-in frame instead. The canonical file is not
    modified. The frame count is already on the provider grid, so the
    reference node does not drop the ending.
    """

    started = time.perf_counter()
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to prepare the continuation tail.")
    total = _probe_frame_count(source)
    if total is None or total < 5:
        raise RuntimeError("The finished video has no readable frames for a continuation tail.")
    end_exclusive = total if end_frame is None else min(total, max(1, int(end_frame) + 1))
    count = min(int(frame_count), end_exclusive)
    count = count - ((count - 5) % 17)
    if count < 5:
        count = 5
    if count > end_exclusive:
        raise RuntimeError("The marked start does not have enough picture for a continuation tail.")
    start = max(0, end_exclusive - count)
    dest.parent.mkdir(parents=True, exist_ok=True)
    start_sec = start / float(fps)
    end_sec = (start + count) / float(fps)
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vf",
            f"trim=start_frame={start}:end_frame={start + count},setpts=PTS-STARTPTS",
            "-af",
            f"atrim=start={start_sec:.6f}:end={end_sec:.6f},asetpts=PTS-STARTPTS",
            "-frames:v",
            str(count),
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or "The continuation tail could not be prepared.")[-500:])
    produced = _probe_frame_count(dest)
    elapsed = round(time.perf_counter() - started, 3)
    if produced != count:
        raise RuntimeError(
            f"The continuation tail has {produced} frames. It needs {count} so the ending is kept."
        )
    return {
        "frames": count,
        "startFrame": start,
        "sourceFrames": total,
        "elapsedSec": elapsed,
        "path": str(dest),
    }


def extract_continuity_opening(
    source: Path,
    dest: Path,
    *,
    frame_count: int,
    fps: int = 24,
    start_frame: int = 0,
) -> dict:
    """Write the opening of a clip. The file itself is not modified.

    Prepend uses this window as the state the new shot must arrive at.
    It is not the ending tail Continue sends.
    """

    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to prepare the opening.")
    total = _probe_frame_count(source)
    if total is None or total < 5:
        raise RuntimeError("The finished video has no readable frames for an opening.")
    start = max(0, min(int(start_frame), total - 1))
    count = min(int(frame_count), total - start)
    count = count - ((count - 5) % 17)
    if count < 5:
        raise RuntimeError("The opening of this scene is too short to use as the arrival picture.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    start_sec = start / float(fps)
    end_sec = (start + count) / float(fps)
    video = [
        "-vf",
        f"trim=start_frame={start}:end_frame={start + count},setpts=PTS-STARTPTS",
        "-frames:v",
        str(count),
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
    ]
    audio = ["-af", f"atrim=start={start_sec:.6f}:end={end_sec:.6f},asetpts=PTS-STARTPTS", "-c:a", "aac"]
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", str(source), *video, *audio, str(dest)],
        capture_output=True,
        text=True,
    )
    has_audio = proc.returncode == 0 and dest.is_file()
    if not has_audio:
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", str(source), *video, "-an", str(dest)],
            capture_output=True,
            text=True,
        )
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or "The opening could not be prepared.")[-500:])
    produced = _probe_frame_count(dest)
    if produced != count:
        raise RuntimeError(f"The opening has {produced} frames. It needs {count}.")
    return {
        "frames": count,
        "startFrame": start,
        "endSec": end_sec,
        "startSec": start_sec,
        "audio": has_audio,
        "path": str(dest),
    }


def store_continuity_tail(db: Session, project_id: str, path: Path) -> str:
    """Execution-context asset. This does not replace the finished segment file."""

    asset_id = str(uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag="continuity-tail",
            kind="video",
            filename=path.name,
            path=str(path),
        )
    )
    db.flush()
    return asset_id


def _store_image(db: Session, project_id: str, path: Path, tag: str) -> str:
    asset_id = str(uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag=tag,
            kind="image",
            filename=path.name,
            path=str(path),
        )
    )
    db.flush()
    return asset_id


def _fill_frames(db: Session, project_id: str, segment: Segment, packet: dict) -> None:
    source = _video_path(db, segment.assetId or "")
    if source is None:
        packet["error"] = "The finished video has no file, so its last frame was not saved."
        return
    duration = probe_video_duration(source) or float(segment.durationSec or 0)
    if duration <= 0:
        packet["error"] = "The finished video has no readable length."
        return
    out_dir = source.parent / "film-continuity"
    out_dir.mkdir(parents=True, exist_ok=True)
    last_path = out_dir / f"{segment.id}-last.png"
    total_frames = _probe_frame_count(source)
    if total_frames:
        extract_frame_png(source, last_path, at_frame=total_frames - 1)
    else:
        extract_frame_png(source, last_path, at_seconds=max(0.0, duration - 0.04))
    packet["lastFrameAssetId"] = _store_image(db, project_id, last_path.resolve(), "continuity-last-frame")
    packet["durationSec"] = round(duration, 3)
    last_at = duration
    tail: list[str] = []
    for offset in _TAIL_OFFSETS:
        at = duration - offset
        if at <= 0.05 or abs(at - last_at) < 0.03:
            continue
        frame_path = out_dir / f"{segment.id}-tail-{int(offset * 1000)}.png"
        extract_frame_png(source, frame_path, at_seconds=at)
        tail.append(_store_image(db, project_id, frame_path, "continuity-tail"))
    packet["tailFrameAssetIds"] = tail
    head_path = out_dir / f"{segment.id}-head.png"
    extract_frame_png(source, head_path, at_seconds=min(0.04, max(0.0, duration / 2)))
    packet["headFrameAssetId"] = _store_image(db, project_id, head_path, "continuity-head")


def store_frame_at(db: Session, project_id: str, asset_id: str, at_seconds: float, tag: str) -> str:
    source = _video_path(db, asset_id)
    if source is None:
        return ""
    dest = source.parent / "film-continuity" / f"{tag}-{uuid4().hex[:8]}.png"
    extract_frame_png(source, dest, at_seconds=max(0.0, float(at_seconds)))
    return _store_image(db, project_id, dest, tag)


def opening_arrival_note(db: Session, project_id: str, asset_id: str, start_sec: float) -> str:
    """Describe the opening a previous shot must arrive at. Continue's packet is not involved."""

    fallback = "At the end of this new shot, arrive at the picture that already opens the scene."
    if not asset_id or not omni_review_ready():
        return fallback
    start = max(0.0, float(start_sec))
    try:
        from ..codirector.video_intelligence.media_analyze import analyze_asset

        result = analyze_asset(
            db,
            project_id,
            asset_id,
            mode="summary",
            question=(
                "Describe only the opening of this picture, not what happens later. "
                "One short line: who is visible, where they are, their pose, which way they face, "
                "any props, the place, the camera angle and distance, the motion already underway, and the light."
            ),
            range_start_sec=start,
            range_end_sec=start + 1.5,
            persist=False,
            force=True,
            timeout_sec=25,
        )
    except Exception:
        log.info("film-timeline prepend opening note skipped", exc_info=True)
        return fallback
    text, unavailable = _omni_boundary_text(result)
    if unavailable or not text:
        return fallback
    return f"At the end of this new shot, arrive at this opening: {text}"


def exit_handback_note(db: Session, project_id: str, asset_id: str, end_sec: float) -> str:
    """Describe the picture a Re-Take must return to. Continue's packet is not involved."""

    fallback = "At the end of this new action, return to the picture that already follows this range."
    if not asset_id or not omni_review_ready():
        return fallback
    start = max(0.0, float(end_sec) - 1.5)
    try:
        from ..codirector.video_intelligence.media_analyze import analyze_asset

        result = analyze_asset(
            db,
            project_id,
            asset_id,
            mode="summary",
            question=(
                "Describe only this moment, not earlier action. "
                "One short line: who is visible, where they are, which way they face, "
                "their pose, the place, and the light."
            ),
            range_start_sec=start,
            range_end_sec=float(end_sec),
            persist=False,
            force=True,
            timeout_sec=25,
        )
    except Exception:
        log.info("film-timeline retake exit note skipped", exc_info=True)
        return fallback
    text, unavailable = _omni_boundary_text(result)
    if unavailable or not text:
        return fallback
    return f"At the end of this new action, return to this picture: {text}"


def omni_review_ready() -> bool:
    try:
        from ..setup.diagnostics import verify_component

        return bool(verify_component("qwen2_5_omni_7b").healthy)
    except Exception:
        log.info("film-timeline omni health unread", exc_info=True)
        return False


def _omni_boundary_text(result: object) -> tuple[str, str | None]:
    """Read a Media Intelligence packet. It is a model, not a dict.

    The worker often answers the ending question as prose. That prose lands in
    raw text when it is not a parsed summary. Use it. Returns the ending note
    and, when perception did not run, the reason.
    """

    if isinstance(result, dict):
        availability = result.get("availability")
        reason = result.get("reason")
        text = str(result.get("summary") or result.get("text") or result.get("answer") or "")
        if not text:
            evidence = result.get("modelEvidence") or {}
            qwen = evidence.get("qwenOmni") if isinstance(evidence, dict) else None
            if isinstance(qwen, dict):
                text = str(qwen.get("rawText") or "")
    else:
        availability = getattr(result, "availability", None)
        reason = getattr(result, "reason", None)
        text = str(getattr(result, "summary", "") or "")
        if not text:
            evidence = getattr(result, "modelEvidence", None)
            qwen = getattr(evidence, "qwenOmni", None)
            text = str(getattr(qwen, "rawText", "") or "")
    if availability in {"unavailable", "failed", "error"}:
        return "", str(reason or availability)
    return " ".join(text.split())[:500], None


def _fill_omni(db: Session, project_id: str, segment: Segment, packet: dict) -> None:
    if not omni_review_ready():
        packet["omni"] = {
            "status": "unavailable",
            "reason": "Qwen2.5-Omni is not installed. Generation continues. Full continuity review is not available.",
        }
        return
    duration = float(packet.get("durationSec") or segment.durationSec or 0)
    start = max(0.0, duration - 2.0)
    try:
        from ..codirector.video_intelligence.media_analyze import analyze_asset

        result = analyze_asset(
            db,
            project_id,
            segment.assetId or "",
            mode="summary",
            question=(
                "Describe only the final moment of this clip, not the earlier action. "
                "One short line each: who is visible, where they are, which way they face, "
                "their pose, anything they hold, the place, the camera side, the camera distance, "
                "the movement, the action underway, and the light. "
                "If a person is in frame at the end, say they are present."
            ),
            range_start_sec=start,
            range_end_sec=duration,
            persist=False,
            force=True,
            timeout_sec=90,
        )
    except Exception as exc:
        log.info("film-timeline omni review skipped segment=%s", segment.id, exc_info=True)
        packet["omni"] = {"status": "unavailable", "reason": str(exc)}
        return
    text, unavailable = _omni_boundary_text(result)
    if unavailable:
        packet["omni"] = {"status": "unavailable", "reason": unavailable}
        return
    packet["omni"] = {"status": "reviewed", "rangeStartSec": round(start, 3), "rangeEndSec": round(duration, 3)}
    packet["notes"] = _notes_from_text(text)
    packet["boundary"] = text


def _notes_from_text(text: str) -> dict:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return {}
    return {"motion": cleaned[:280]}


def _fill_seam(db: Session, shot: Shot, segment: Segment, packet: dict) -> None:
    ordered = sorted(shot.segments, key=lambda item: item.order)
    previous = None
    for item in ordered:
        if item.id == segment.id:
            break
        if item.status == "completed" and item.assetId:
            previous = item
    if previous is None:
        return
    prior = cached_packet(previous) or previous.generationMetadata.get("continuity")
    if not isinstance(prior, dict):
        return
    last_id = str(prior.get("lastFrameAssetId") or previous.lastFrameAssetId or "")
    head_id = str(packet.get("headFrameAssetId") or "")
    last_path = _video_path(db, last_id)
    head_path = _video_path(db, head_id)
    if last_path is None or head_path is None:
        packet["seam"] = {"status": "unmeasured"}
        return
    last_y = _yavg(last_path)
    head_y = _yavg(head_path)
    if last_y is None or head_y is None:
        packet["seam"] = {"status": "unmeasured"}
        return
    delta = abs(last_y - head_y)
    warning = delta >= _BRIGHTNESS_WARN
    packet["seam"] = {
        "status": "warn" if warning else "ok",
        "brightnessDelta": round(delta, 2),
        "warning": "The join between these parts looks uneven. Both parts were kept." if warning else None,
    }


def _video_dimensions(source: Path) -> tuple[int, int]:
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required to lock the opening frame.")
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(source),
        ],
        capture_output=True,
        text=True,
    )
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0 or "x" not in raw:
        raise RuntimeError("The finished video has no readable frame size.")
    width_s, height_s = raw.split("x", 1)
    width, height = int(width_s), int(height_s)
    if width < 2 or height < 2:
        raise RuntimeError("The finished video has no readable frame size.")
    return width, height


def lock_opening_to_frame(video: Path, frame: Path) -> None:
    """Replace frame 0 with the previous shot's last still. Audio and length stay."""

    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to lock the opening frame.")
    if not video.is_file() or not frame.is_file():
        raise RuntimeError("The continuation video or its opening still is missing.")
    width, height = _video_dimensions(video)
    dest = video.with_name(f"{video.stem}.opening-lock{video.suffix}")
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video),
            "-i",
            str(frame),
            "-filter_complex",
            (
                f"[1:v]scale={width}:{height}:flags=neighbor:force_original_aspect_ratio=disable,setsar=1[still];"
                "[0:v][still]overlay=0:0:enable='eq(n\\,0)'[v]"
            ),
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-crf",
            "12",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size < 32:
        dest.unlink(missing_ok=True)
        raise RuntimeError((proc.stderr or "The opening frame could not be locked.")[-500:])
    os.replace(dest, video)


def apply_opening_lock(db: Session, video_asset_id: str, frame_asset_id: str) -> bool:
    """Write the previous last frame over frame 0 of a continuing shot. Failures keep the video."""

    video = _video_path(db, video_asset_id)
    frame_row = db.get(Asset, frame_asset_id)
    frame = Path(frame_row.path) if frame_row is not None and frame_row.path else None
    if video is None or frame is None or not frame.is_file():
        log.info(
            "film-timeline opening lock skipped video=%s frame=%s",
            video_asset_id,
            frame_asset_id,
        )
        return False
    try:
        lock_opening_to_frame(video, frame)
    except Exception:
        log.exception("film-timeline opening lock failed video=%s frame=%s", video_asset_id, frame_asset_id)
        return False
    log.info("film-timeline opening locked video=%s frame=%s", video_asset_id, frame_asset_id)
    return True


def _yavg(path: Path) -> float | None:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        return None
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path), "-vf", "signalstats", "-frames:v", "1", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    match = re.search(r"YAVG:\s*([0-9.]+)", (proc.stderr or "") + (proc.stdout or ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None
