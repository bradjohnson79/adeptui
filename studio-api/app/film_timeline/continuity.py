"""Film Timeline continuity. One packet on the segment. ShotState stays the shot authority."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from ..db import Asset
from ..media_clip import extract_frame_png, probe_video_duration
from .contracts import Segment, Shot

log = logging.getLogger("adept.film_timeline")

PACKET_VERSION = 1
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


def invalidate_segment_continuity(shot: Shot, segment_id: str) -> None:
    ordered = sorted(shot.segments, key=lambda item: item.order)
    for index, segment in enumerate(ordered):
        if segment.id != segment_id:
            continue
        packet = segment.generationMetadata.get("continuity")
        if isinstance(packet, dict):
            segment.generationMetadata["retakePreviousContinuity"] = packet
        segment.generationMetadata.pop("continuity", None)
        segment.lastFrameAssetId = None
        if index + 1 < len(ordered):
            nxt = ordered[index + 1]
            seam_packet = nxt.generationMetadata.get("continuity")
            if isinstance(seam_packet, dict):
                seam_packet.pop("seam", None)
                seam_packet["seamStale"] = True
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
    out_dir = Path("data") / "assets" / project_id / "film-continuity"
    out_dir.mkdir(parents=True, exist_ok=True)
    last_at = max(0.0, duration - 0.04)
    last_path = out_dir / f"{segment.id}-last.png"
    extract_frame_png(source, last_path, at_seconds=last_at)
    packet["lastFrameAssetId"] = _store_image(db, project_id, last_path, "continuity-last-frame")
    packet["durationSec"] = round(duration, 3)
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


def omni_review_ready() -> bool:
    try:
        from ..setup.diagnostics import verify_component

        return bool(verify_component("qwen2_5_omni_7b").healthy)
    except Exception:
        log.info("film-timeline omni health unread", exc_info=True)
        return False


def _fill_omni(db: Session, project_id: str, segment: Segment, packet: dict) -> None:
    if not omni_review_ready():
        packet["omni"] = {
            "status": "unavailable",
            "reason": "Qwen2.5-Omni is not installed. Generation continues. Full continuity review is not available.",
        }
        return
    duration = float(packet.get("durationSec") or segment.durationSec or 0)
    start = max(0.0, duration - 1.0)
    try:
        from ..codirector.video_intelligence.media_analyze import analyze_asset

        result = analyze_asset(
            db,
            project_id,
            segment.assetId or "",
            mode="summary",
            question="Describe only this short tail: camera move, light, and subject motion. One short sentence each.",
            range_start_sec=start,
            range_end_sec=duration,
            persist=False,
            timeout_sec=90,
        )
    except Exception as exc:
        log.info("film-timeline omni review skipped segment=%s", segment.id, exc_info=True)
        packet["omni"] = {"status": "unavailable", "reason": str(exc)}
        return
    text = ""
    if isinstance(result, dict):
        text = str(result.get("summary") or result.get("text") or result.get("answer") or "")
    packet["omni"] = {"status": "reviewed", "rangeStartSec": round(start, 3), "rangeEndSec": round(duration, 3)}
    packet["notes"] = _notes_from_text(text)


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
