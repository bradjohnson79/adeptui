"""Keyframe still-inpaint applied to a bounded Timeline range.

Native video inpaint is not certified. This keeps the unmarked picture and
time, then overlays the repaired still only where the creator painted.
Compose reuses extract_window + stitch_videos.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..codirector.video_intelligence.clip_extract import extract_window
from ..generation_tools.lineage import register_derived_asset
from ..media_clip import probe_video_duration
from .range_replacement import compose_range_media
from .scene_stitch import resolve_asset_file

_EPS = 0.05


def overlay_repaired_still_on_window(
    *,
    source_path: str | Path,
    repaired_still_path: str | Path,
    mask_path: str | Path,
    dest_path: str | Path,
    start: float,
    length: float,
    source_duration: float | None = None,
) -> dict[str, Any]:
    """Extract [start, start+length), overlay the painted repair, write the window."""
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        return {"ok": False, "error": "FFMPEG_MISSING", "message": "ffmpeg is required to apply this repair."}

    source = Path(source_path)
    still = Path(repaired_still_path)
    mask = Path(mask_path)
    dest = Path(dest_path)
    if not source.is_file():
        return {"ok": False, "error": "SOURCE_VIDEO_MISSING", "message": "The original take file is missing."}
    if not still.is_file():
        return {"ok": False, "error": "REPAIRED_STILL_MISSING", "message": "The repaired picture was not written."}
    if not mask.is_file():
        return {"ok": False, "error": "MASK_MISSING", "message": "The painted mask file is missing."}

    src_dur = float(source_duration or probe_video_duration(source) or 0.0)
    start = max(0.0, float(start))
    length = max(0.1, float(length))
    if src_dur > 0:
        length = max(0.1, min(length, max(0.1, src_dur - start)))

    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="keyframe_repair_"))
    try:
        window = work / "window.mp4"
        extract_window(str(source), str(window), start_sec=start, duration_sec=length)
        if not window.is_file():
            return {"ok": False, "error": "WINDOW_EXTRACT_FAILED", "message": "Could not cut the selected part of the take."}

        # Scale the repaired still and mask to the window, use the mask as alpha,
        # and overlay only that region. Unpainted pixels keep the original motion.
        filter_complex = (
            "[1:v][0:v]scale2ref=flags=bicubic[still][base];"
            "[2:v][base]scale2ref=flags=bicubic[mask][base2];"
            "[still][mask]alphamerge[fg];"
            "[base2][fg]overlay=0:0:format=auto:shortest=1"
        )
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(window),
                "-loop",
                "1",
                "-i",
                str(still),
                "-loop",
                "1",
                "-i",
                str(mask),
                "-filter_complex",
                filter_complex,
                "-t",
                f"{length:.3f}",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(dest),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not dest.is_file():
            return {
                "ok": False,
                "error": "OVERLAY_FAILED",
                "message": (proc.stderr or proc.stdout or "Could not apply the painted repair to this range.")[:500],
            }
        out_dur = probe_video_duration(dest) or length
        return {"ok": True, "path": str(dest), "duration": out_dur}
    except Exception as exc:  # noqa: BLE001 — overlay failure must be honest
        return {"ok": False, "error": "OVERLAY_FAILED", "message": str(exc)[:500]}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def apply_keyframe_repair_to_asset(
    db: Session,
    *,
    project_id: str,
    source_asset_id: str,
    repaired_still_asset_id: str,
    mask_path: str | Path,
    start: float,
    length: float,
    planned_duration: float | None = None,
) -> dict[str, Any]:
    """Register a new Library video: before + painted repair + after. Never overwrite the source."""
    source_path = resolve_asset_file(db, project_id, source_asset_id)
    still_path = resolve_asset_file(db, project_id, repaired_still_asset_id)
    if source_path is None:
        return {"ok": False, "error": "SOURCE_VIDEO_MISSING", "message": "The original take is not in the Library."}
    if still_path is None:
        return {"ok": False, "error": "REPAIRED_STILL_MISSING", "message": "The repaired picture is not in the Library."}

    src_dur = probe_video_duration(source_path) or float(planned_duration or 0.0)
    start = max(0.0, float(start))
    length = max(0.1, float(length))
    work = Path(tempfile.mkdtemp(prefix="keyframe_repair_apply_"))
    try:
        patched = work / "patched.mp4"
        overlay = overlay_repaired_still_on_window(
            source_path=source_path,
            repaired_still_path=still_path,
            mask_path=mask_path,
            dest_path=patched,
            start=start,
            length=length,
            source_duration=src_dur,
        )
        if not overlay.get("ok"):
            return overlay

        dest = source_path.parent / f"keyframe_repair_{uuid.uuid4().hex[:10]}.mp4"
        composed = compose_range_media(
            source_path=source_path,
            generated_path=patched,
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
            tag="timeline-keyframe-repair",
            parent_asset_id=source_asset_id,
            op="timeline_keyframe_repair",
            prompt_meta={
                "rangeStart": start,
                "rangeLength": length,
                "sourceAssetId": source_asset_id,
                "repairedStillAssetId": repaired_still_asset_id,
                "strategy": "keyframe_repair",
            },
            filename=dest.name,
        )
        return {
            "ok": True,
            "assetId": asset.id,
            "duration": float(composed.get("duration") or src_dur),
            "composed": True,
            "sourceAssetId": source_asset_id,
            "repairedStillAssetId": repaired_still_asset_id,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)
