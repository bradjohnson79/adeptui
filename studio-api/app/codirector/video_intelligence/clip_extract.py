"""ffmpeg temporal clip extract. Reuses the last-frame ffmpeg binary."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFMPEG_MISSING")
    return found


def extract_window(
    video_path: str,
    dest_path: str,
    *,
    start_sec: float,
    duration_sec: float,
) -> str:
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-ss",
        f"{max(0.0, float(start_sec)):.3f}",
        "-i",
        str(video_path),
        "-t",
        f"{max(0.1, float(duration_sec)):.3f}",
        "-c:v",
        "libx264",
        "-an",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or proc.stdout or "clip extract failed")[:500])
    return str(dest)


def extract_review_clip(
    video_path: str,
    dest_path: str,
    *,
    start_sec: float = 0.0,
    duration_sec: float = 3.0,
    width: int = 512,
    fps: int = 2,
) -> str:
    """Short low-res window for VideoChat3. Full-res clips OOM SDPA (~100GB)."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-ss",
        f"{max(0.0, float(start_sec)):.3f}",
        "-i",
        str(video_path),
        "-t",
        f"{max(0.5, float(duration_sec)):.3f}",
        "-vf",
        f"scale={int(width)}:-2,fps={int(fps)}",
        "-c:v",
        "libx264",
        "-an",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not dest.is_file():
        raise RuntimeError((proc.stderr or proc.stdout or "review clip extract failed")[:500])
    return str(dest)


def cleanup_extracted_clip(path: str | None, *, source_path: str | None = None) -> bool:
    """Remove a review/window extract. Never deletes the source approved MP4."""
    if not path:
        return False
    dest = Path(path)
    if source_path and Path(source_path).resolve() == dest.resolve():
        return False
    if dest.suffix.lower() != ".mp4":
        return False
    name = dest.name
    if ".review512." not in name and "_interval_" not in name and "_automatic" not in name:
        # Cadence windows are named {batchId}_{cadence}.mp4 under assets/.../temporal/
        if "temporal" not in dest.parts:
            return False
    try:
        dest.unlink(missing_ok=True)
        return not dest.exists()
    except OSError:
        return False
