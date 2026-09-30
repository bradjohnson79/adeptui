"""Small ffmpeg helpers for take duration and last-frame extract.

Ingredients IC-LoRA can append the reference sheet after the requested latent
length. Continuity and Timeline playback must use the requested shot, not that
tail.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ltx_latent_frame_count(duration: float, fps: float = 24.0) -> int:
    """Exact requested frames. Never pad or floor to 8n+1."""
    from .video_runtime.legal_canvas import exact_frame_count

    return exact_frame_count(float(duration), int(fps))


def shot_last_frame_seconds(planned_duration: float, fps: float = 24.0) -> float:
    """Timestamp of the last requested latent frame, not the container EOF."""
    length = ltx_latent_frame_count(planned_duration, fps)
    return max(0.0, (length - 1) / float(fps))


def probe_video_duration(video_path: str | Path) -> float | None:
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        value = float((proc.stdout or "").strip())
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def extract_frame_png(
    video_path: str | Path,
    dest_path: str | Path,
    *,
    at_seconds: float | None = None,
    at_frame: int | None = None,
) -> None:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required to extract continuity last frame")
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if at_frame is not None and int(at_frame) >= 0:
        # Frame select: time-seek on concatenated Ingredients files can snap
        # to the appended sheet keyframe even when the timestamp is still
        # inside the generated shot.
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"select=eq(n\\,{int(at_frame)})",
            "-vsync",
            "vfr",
            "-frames:v",
            "1",
            str(dest),
        ]
    elif at_seconds is not None and float(at_seconds) >= 0:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-ss",
            f"{float(at_seconds):.3f}",
            "-frames:v",
            "1",
            str(dest),
        ]
    else:
        cmd = [
            ffmpeg,
            "-y",
            "-sseof",
            "-0.05",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(dest),
        ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dest.is_file():
        cmd2 = [ffmpeg, "-y", "-i", str(video_path), "-frames:v", "1", str(dest)]
        proc2 = subprocess.run(cmd2, capture_output=True, text=True)
        if proc2.returncode != 0 or not dest.is_file():
            raise RuntimeError(proc.stderr or proc2.stderr or "last-frame extract failed")


def first_non_reference_seconds(
    video_path: str | Path,
    reference_image: str | Path,
    *,
    threshold: float = 1500.0,
    probe_fps: float = 12.0,
    max_seconds: float = 2.0,
) -> float:
    """Return the first timestamp that is no longer the Ingredients sheet."""
    from PIL import Image
    import numpy as np

    ref = Image.open(reference_image).convert("RGB")
    size = (256, 144)
    ref_arr = np.asarray(ref.resize(size), dtype=np.float32)
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        return 0.0
    step = 1.0 / float(probe_fps)
    t = 0.0
    while t <= max_seconds + 1e-6:
        dest = Path(video_path).with_suffix(f".probe_{int(t * 1000)}.png")
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{t:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(dest),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not dest.is_file():
            dest.unlink(missing_ok=True)
            break
        frame = np.asarray(Image.open(dest).convert("RGB").resize(size), dtype=np.float32)
        dest.unlink(missing_ok=True)
        if float(np.mean((frame - ref_arr) ** 2)) >= threshold:
            return max(0.0, t)
        t += step
    return 0.0


def strip_leading_reference_frames(video_path: str | Path, reference_image: str | Path) -> bool:
    start = first_non_reference_seconds(video_path, reference_image)
    if start <= 0.08:
        return False
    path = Path(video_path)
    remain = probe_video_duration(path)
    if remain is None or remain - start < 0.8:
        return False
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required to strip Ingredients sheet frames from the take")
    tmp = path.with_suffix(path.suffix + ".leadtrim.mp4")
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(path),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(tmp),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(proc.stderr or "leading sheet trim failed")
    tmp.replace(path)
    return True


def trim_video_to_seconds(video_path: str | Path, seconds: float) -> bool:
    """In-place trim when the file is longer than the requested shot.

    Returns True when the file was rewritten.
    """
    path = Path(video_path)
    if not path.is_file() or seconds <= 0:
        return False
    current = probe_video_duration(path)
    # Trim when the generated video is meaningfully longer than requested.
    # 0.05s tolerance avoids trimming for tiny encoder duration jitter while
    # still trimming the MiniMax H3 legal-frame excess (e.g., 12.25s → 12.0s,
    # a 0.25s difference from snapping 288 → 294 legal 17k+5 frames).
    if current is None or current <= float(seconds) + 0.05:
        return False
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise RuntimeError("ffmpeg required to trim ingredients output to the requested shot")
    tmp = path.with_suffix(path.suffix + ".shottrim.mp4")
    # Preserve audio: MiniMax H3 generates native audio that must survive
    # the trim. Use -c:a copy to stream-copy audio (no quality loss) and
    # -c:v libx264 for frame-accurate video trimming. The -t flag trims
    # both video and audio to the requested duration.
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(path),
            "-t",
            f"{float(seconds):.3f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            str(tmp),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    # Fallback: if -c:a copy fails (e.g., incompatible codec), re-encode audio
    if proc.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(path),
                "-t",
                f"{float(seconds):.3f}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(tmp),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    if proc.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(proc.stderr or "ingredients output trim failed")
    tmp.replace(path)
    return True
