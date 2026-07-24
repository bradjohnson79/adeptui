"""Build a static video loop from a still reference sheet."""

from __future__ import annotations

from pathlib import Path

from ..media_ops import run_ffmpeg


def still_to_static_video(
    image_path: Path,
    out_path: Path,
    *,
    fps: int = 24,
    frames: int = 121,
    width: int = 768,
    height: int = 448,
) -> Path:
    """Loop a still image into a video of at least `frames` frames."""
    frames = max(121, int(frames))
    fps = max(1, int(fps))
    duration = frames / fps
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps={fps}",
            "-t",
            f"{duration:.4f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out_path),
        ]
    )
    if not out_path.is_file() or out_path.stat().st_size <= 0:
        raise RuntimeError("Static reference video was not created")
    return out_path
