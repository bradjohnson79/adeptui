"""Shared MAGI media helpers — probe, disk preflight, temp cleanup."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from ..config import settings
from ..editor_mix import probe_has_audio

TEMP_ROOT_NAME = "magi_tmp"


def magi_temp_root() -> Path:
    root = Path(settings.data_dir) / "runtimes" / TEMP_ROOT_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_temp_dir(prefix: str) -> Path:
    path = magi_temp_root() / f"{prefix}_{uuid.uuid4().hex[:10]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_dir(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def free_disk_bytes(path: Path | None = None) -> int:
    target = path or Path(settings.data_dir)
    try:
        return int(shutil.disk_usage(target).free)
    except OSError:
        return 0


def estimate_frame_tree_bytes(width: int, height: int, frames: int) -> int:
    # Uncompressed-ish PNG frames plus headroom.
    per_frame = max(width * height * 3, 250_000)
    return int(per_frame * max(frames, 1) * 1.35)


def disk_preflight(*, need_bytes: int, label: str = "this MAGI operation") -> None:
    free = free_disk_bytes()
    if free and free < need_bytes:
        gb = need_bytes / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        raise RuntimeError(
            f"Not enough disk space for {label}. About {gb:.1f} GB is needed; "
            f"{free_gb:.1f} GB is free. Free space and try again."
        )


def ffprobe_json(path: str | Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        return {}
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def probe_media(path: str | Path) -> dict[str, Any]:
    info = ffprobe_json(path)
    video = next((s for s in (info.get("streams") or []) if s.get("codec_type") == "video"), None) or {}
    audio = next((s for s in (info.get("streams") or []) if s.get("codec_type") == "audio"), None)
    fmt = info.get("format") or {}
    fps = 24.0
    rate = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "24/1")
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            fps = float(num) / max(float(den), 1.0)
        except (TypeError, ValueError):
            fps = 24.0
    duration = 0.0
    try:
        duration = float(fmt.get("duration") or video.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    frames = 0
    try:
        frames = int(video.get("nb_frames") or 0)
    except (TypeError, ValueError):
        frames = 0
    if frames <= 0 and duration > 0:
        frames = max(1, int(round(duration * fps)))
    return {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": fps,
        "duration": duration,
        "frames": frames,
        "hasAudio": bool(audio) or probe_has_audio(Path(path)),
        "videoCodec": video.get("codec_name"),
        "audioCodec": (audio or {}).get("codec_name"),
        "streamCount": len(info.get("streams") or []),
        "size": int(fmt.get("size") or 0),
    }


def run_ffmpeg(args: list[str], *, timeout: int = 600) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {(proc.stderr or proc.stdout or '')[-1200:]}")
