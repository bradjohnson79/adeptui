"""Adept-owned shot stitch. A stitch failure leaves the segments in place."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset
from ..media_ops import stitch_videos
from .contracts import Segment, Shot
from .store import require_film, save_film

log = logging.getLogger("adept.film_timeline")


def _composition(shot: Shot) -> list[Segment]:
    from .retake import assembled_windows

    return [segment for segment, _start, _end in assembled_windows(shot)]


def _trim_media(src: Path, dest: Path, start: float, end: float | None) -> None:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not available, so the shot segments stay separate.")
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _run(with_audio: bool) -> subprocess.CompletedProcess[str]:
        args = [ffmpeg, "-y", "-ss", f"{max(0.0, start):.3f}"]
        if end is not None:
            args.extend(["-to", f"{max(start, end):.3f}"])
        args.extend(["-i", str(src)])
        if with_audio:
            args.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dest)])
        else:
            args.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dest)])
        return subprocess.run(args, capture_output=True, text=True)

    proc = _run(True)
    if proc.returncode != 0 or not dest.is_file():
        proc = _run(False)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or "The selected range could not be prepared.")[-400:])


def _materialize(segment: Segment, src: Path, work: Path) -> Path:
    start = float(segment.trimInSec or 0)
    end = float(segment.trimOutSec) if segment.trimOutSec is not None else None
    if start <= 0.02 and end is None:
        return src
    dest = work / f"{segment.id}.mp4"
    _trim_media(src, dest, start, end)
    return dest


def stitch_shot(db: Session, project_id: str, scene_id: str, shot_id: str) -> dict:
    film = require_film(db, project_id, scene_id)
    shot = next((item for item in film.shots if item.id == shot_id), None)
    if shot is None:
        return {"ok": False, "error": "SHOT_NOT_FOUND", "message": "That shot is not on this scene."}
    completed = _composition(shot)
    needs_trim = any(float(segment.trimInSec or 0) > 0.02 or segment.trimOutSec is not None for segment in completed)
    if len(completed) < 2 and not needs_trim:
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
    work = Path(settings.data_dir) / "assets" / project_id / "film-stitch" / f"_trim-{shot.id}"
    for segment in completed:
        asset = db.get(Asset, segment.assetId)
        path = Path(asset.path) if asset and asset.path else None
        if path is None or not path.exists():
            shot.state.stitchStatus = "failed"
            shot.state.stitchError = f"Segment {segment.order + 1} has no playable file. The other segments were kept."
            save_film(db, project_id, scene_id, film)
            return {"ok": False, "error": "SOURCE_ASSET_MISSING", "message": shot.state.stitchError, "segmentId": segment.id}
        paths.append(_materialize(segment, path, work))

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


def _splice(shot: Shot, source_id: str, pieces: list[Segment], hold_id: str) -> None:
    ordered = sorted(shot.segments, key=lambda item: item.order)
    merged: list[Segment] = []
    for item in ordered:
        if item.id == hold_id:
            continue
        if item.id == source_id:
            merged.extend(pieces)
            continue
        merged.append(item)
    for index, item in enumerate(merged):
        item.order = index
    shot.segments = merged
    shot.state.segmentIds = [item.id for item in merged]


def commit_prepend(db: Session, project_id: str, scene_id: str, shot: Shot, hold: Segment) -> str | None:
    """Place a finished earlier shot at scene time 0. Existing pieces only shift later.

    Source files, trims, and Re-Take roles are not rewritten. A failed join
    restores the previous composition.
    """

    if not hold.assetId:
        message = "The earlier shot could not be inserted. The scene was kept."
        _fail_hold(shot, hold, message)
        return message
    backup_segments = [item.model_copy(deep=True) for item in shot.segments]
    backup_stitch = (
        shot.state.stitchAssetId,
        shot.state.stitchStatus,
        shot.state.stitchError,
        list(shot.state.stitchSegmentIds or []),
    )
    others = [item for item in shot.segments if item.id != hold.id]
    hold.order = (min((item.order for item in others), default=0) - 1)
    hold.generationMetadata.pop("compositionHold", None)
    try:
        asset_id = _store_composition(db, project_id, shot)
    except Exception as exc:
        log.exception("film-timeline prepend stitch failed shot=%s", shot.id)
        shot.segments = backup_segments
        shot.state.segmentIds = [item.id for item in backup_segments]
        shot.state.stitchAssetId, shot.state.stitchStatus, _ignored, shot.state.stitchSegmentIds = backup_stitch
        message = f"The earlier shot could not be joined, so the scene was kept. {exc}"[:400]
        _fail_hold(shot, hold, message)
        shot.state.stitchError = None if backup_stitch[1] == "ready" else backup_stitch[2]
        return message
    shot.state.stitchAssetId = asset_id
    shot.state.stitchStatus = "ready"
    shot.state.stitchError = None
    shot.state.stitchSegmentIds = [segment.id for segment in _composition(shot)]
    return None


def commit_segmented_retake(db: Session, project_id: str, scene_id: str, shot: Shot, hold: Segment) -> str | None:
    """Insert head, replacement, and tail only after the new file can be stitched.

    A failure leaves the previous segments and the previous stitch pointer.
    The returned string is a creator-facing error. None means the splice is on the shot.
    """

    from .retake import plan_replacement_pieces

    spec = hold.generationMetadata.get("segmentedRetake") if isinstance(hold.generationMetadata.get("segmentedRetake"), dict) else {}
    source = next((item for item in shot.segments if item.id == spec.get("sourceSegmentId")), None)
    if source is None or not hold.assetId:
        _fail_hold(shot, hold, "The replacement could not be inserted. The original picture was kept.")
        return "The replacement could not be inserted. The original picture was kept."
    pieces = plan_replacement_pieces(
        source,
        hold.assetId,
        file_in=float(spec.get("fileIn") or 0),
        file_out=float(spec.get("fileOut") or 0),
        marked=float(spec.get("marked") or hold.durationSec or 0),
        generated_sec=float(spec.get("generatedSec") or hold.durationSec or 0),
        prompt=hold.timedPrompt,
    )
    backup_segments = [item.model_copy(deep=True) for item in shot.segments]
    backup_stitch = (
        shot.state.stitchAssetId,
        shot.state.stitchStatus,
        shot.state.stitchError,
        list(shot.state.stitchSegmentIds or []),
    )
    _splice(shot, source.id, pieces, hold.id)
    try:
        asset_id = _store_composition(db, project_id, shot)
    except Exception as exc:
        log.exception("film-timeline segmented retake stitch failed shot=%s", shot.id)
        shot.segments = backup_segments
        shot.state.segmentIds = [item.id for item in backup_segments]
        shot.state.stitchAssetId, shot.state.stitchStatus, _ignored, shot.state.stitchSegmentIds = backup_stitch
        message = f"The new picture could not be joined, so the original scene was kept. {exc}"[:400]
        _fail_hold(shot, hold, message)
        shot.state.stitchError = None if backup_stitch[1] == "ready" else backup_stitch[2]
        return message
    shot.state.stitchAssetId = asset_id
    shot.state.stitchStatus = "ready"
    shot.state.stitchError = None
    shot.state.stitchSegmentIds = [segment.id for segment in _composition(shot)]
    return None


def _fail_hold(shot: Shot, hold: Segment, message: str) -> None:
    for item in shot.segments:
        if item.id == hold.id:
            item.status = "failed"
            item.error = message
            item.generationMetadata["compositionHold"] = True
            return


def _store_composition(db: Session, project_id: str, shot: Shot) -> str:
    completed = _composition(shot)
    if not completed:
        raise RuntimeError("The scene has no picture to join.")
    if not (shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")):
        raise RuntimeError("ffmpeg is not available, so the shot segments stay separate.")
    paths: list[Path] = []
    work = Path(settings.data_dir) / "assets" / project_id / "film-stitch" / f"_trim-{shot.id}"
    for segment in completed:
        asset = db.get(Asset, segment.assetId)
        path = Path(asset.path) if asset and asset.path else None
        if path is None or not path.exists():
            raise RuntimeError("A piece of this scene has no playable file. The original picture was kept.")
        paths.append(_materialize(segment, path, work))
    out_dir = Path(settings.data_dir) / "assets" / project_id / "film-stitch"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{shot.id}-{uuid4().hex[:8]}.mp4"
    stitch_videos(paths, out_path)
    asset_id = str(uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag="shot-stitch",
            kind="video",
            filename=out_path.name,
            path=str(out_path),
        )
    )
    db.flush()
    return asset_id


def restitch_after_segment(db: Session, project_id: str, scene_id: str, shot: Shot) -> None:
    completed = [segment for segment in shot.segments if segment.status == "completed" and segment.assetId]
    if len(completed) >= 2:
        stitch_shot(db, project_id, scene_id, shot.id)
