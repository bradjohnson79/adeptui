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
