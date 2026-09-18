"""Adept-side bounded Re-take: generate a marked slice, keep the rest.

Compose reuses extract_window + stitch_videos. Do not invent a second media stack.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..codirector.video_intelligence.clip_extract import extract_window
from ..generation_tools.lineage import register_derived_asset
from ..media_clip import extract_frame_png, probe_video_duration, trim_video_to_seconds
from ..media_ops import stitch_videos
from .scene_stitch import resolve_asset_file

_EPS = 0.05


def compose_range_media(
    *,
    source_path: str | Path,
    generated_path: str | Path,
    dest_path: str | Path,
    start: float,
    length: float,
    source_duration: float | None = None,
) -> dict[str, Any]:
    """Keep [0, start) and [start+length, end). Replace the marked middle."""
    source = Path(source_path)
    generated = Path(generated_path)
    dest = Path(dest_path)
    if not source.is_file():
        return {"ok": False, "error": "SOURCE_VIDEO_MISSING", "message": "The original take file is missing."}
    if not generated.is_file():
        return {"ok": False, "error": "GENERATED_VIDEO_MISSING", "message": "The replacement clip was not written."}

    src_dur = float(source_duration or probe_video_duration(source) or 0.0)
    if src_dur <= 0:
        return {"ok": False, "error": "SOURCE_DURATION_UNKNOWN", "message": "Could not read the original take length."}

    start = max(0.0, float(start))
    length = max(0.1, float(length))
    end = min(src_dur, start + length)
    length = max(0.1, end - start)

    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="retake_range_"))
    pieces: list[Path] = []
    try:
        if start > _EPS:
            before = work / "before.mp4"
            extract_window(str(source), str(before), start_sec=0.0, duration_sec=start)
            pieces.append(before)

        middle = work / "middle.mp4"
        generated_copy = work / "generated.mp4"
        generated_copy.write_bytes(generated.read_bytes())
        trim_video_to_seconds(generated_copy, length)
        if generated_copy.is_file():
            # If the generated clip is still longer than the mark, extract the window.
            gen_dur = probe_video_duration(generated_copy) or 0.0
            if gen_dur > length + 0.25:
                extract_window(str(generated_copy), str(middle), start_sec=0.0, duration_sec=length)
                pieces.append(middle)
            else:
                pieces.append(generated_copy)
        else:
            return {"ok": False, "error": "MIDDLE_TRIM_FAILED", "message": "Could not trim the replacement clip."}

        if end < src_dur - _EPS:
            after = work / "after.mp4"
            extract_window(str(source), str(after), start_sec=end, duration_sec=max(0.1, src_dur - end))
            pieces.append(after)

        if len(pieces) == 1:
            dest.write_bytes(pieces[0].read_bytes())
        else:
            stitch_videos(pieces, dest)
        if not dest.is_file():
            return {"ok": False, "error": "COMPOSE_FAILED", "message": "Could not join the replacement into the take."}
        out_dur = probe_video_duration(dest) or src_dur
        return {"ok": True, "path": str(dest), "duration": out_dur, "pieceCount": len(pieces)}
    except Exception as exc:  # noqa: BLE001 — compose failure must be honest
        return {"ok": False, "error": "COMPOSE_FAILED", "message": str(exc)[:500]}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def apply_range_replacement_to_asset(
    db: Session,
    *,
    project_id: str,
    generated_asset_id: str,
    source_asset_id: str,
    start: float,
    length: float,
    planned_duration: float | None = None,
) -> dict[str, Any]:
    """Register a new Library video: before + replacement + after. Never overwrite the source."""
    source_path = resolve_asset_file(db, project_id, source_asset_id)
    generated_path = resolve_asset_file(db, project_id, generated_asset_id)
    if source_path is None:
        return {"ok": False, "error": "SOURCE_VIDEO_MISSING", "message": "The original take is not in the Library."}
    if generated_path is None:
        return {"ok": False, "error": "GENERATED_VIDEO_MISSING", "message": "The replacement clip is not in the Library."}

    src_dur = probe_video_duration(source_path) or float(planned_duration or 0.0)
    start = max(0.0, float(start))
    length = max(0.1, float(length))
    covers_all = start <= _EPS and (start + length) >= (src_dur - _EPS if src_dur else 0)
    if covers_all or src_dur <= 0:
        return {
            "ok": True,
            "assetId": generated_asset_id,
            "duration": src_dur or length,
            "composed": False,
        }

    dest = source_path.parent / f"retake_range_{uuid.uuid4().hex[:10]}.mp4"
    composed = compose_range_media(
        source_path=source_path,
        generated_path=generated_path,
        dest_path=dest,
        start=start,
        length=length,
        source_duration=src_dur,
    )
    if not composed.get("ok"):
        return composed
    asset = register_derived_asset(
        db,
        project_id=project_id,
        source_path=dest,
        kind="video",
        tag="timeline-retake-range",
        parent_asset_id=source_asset_id,
        op="timeline_range_retake",
        prompt_meta={
            "rangeStart": start,
            "rangeLength": length,
            "sourceAssetId": source_asset_id,
            "generatedAssetId": generated_asset_id,
        },
        filename=dest.name,
    )
    return {
        "ok": True,
        "assetId": asset.id,
        "duration": float(composed.get("duration") or src_dur),
        "composed": True,
        "generatedAssetId": generated_asset_id,
        "sourceAssetId": source_asset_id,
    }


def extract_cut_in_frame_asset(
    db: Session,
    *,
    project_id: str,
    source_asset_id: str,
    at_seconds: float,
) -> dict[str, Any]:
    """Still frame at the cut-in so I2V matches the untouched incoming picture."""
    source_path = resolve_asset_file(db, project_id, source_asset_id)
    if source_path is None:
        return {"ok": False, "error": "SOURCE_VIDEO_MISSING", "message": "The original take is not in the Library."}
    dest = source_path.parent / f"retake_cutin_{uuid.uuid4().hex[:10]}.png"
    try:
        extract_frame_png(source_path, dest, at_seconds=max(0.0, float(at_seconds)))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "RANGE_START_FRAME_FAILED", "message": str(exc)[:400]}
    if not dest.is_file():
        return {"ok": False, "error": "RANGE_START_FRAME_FAILED", "message": "Could not take a still at the cut."}
    asset = register_derived_asset(
        db,
        project_id=project_id,
        source_path=dest,
        kind="image",
        tag="timeline-retake-cut-in",
        parent_asset_id=source_asset_id,
        op="timeline_range_cut_in",
        filename=dest.name,
    )
    return {"ok": True, "assetId": asset.id, "atSeconds": float(at_seconds)}
