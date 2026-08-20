"""MAGI Video Upscaling — Real-ESRGAN-ncnn-Vulkan + FFmpeg fallback.

Primary engine: Real-ESRGAN-ncnn-Vulkan (MIT license).
Fallback engine: FFmpeg software scaling (lanczos/bicubic).

Frame-by-frame upscaling with audio preservation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from ..db import Asset, Project
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _realesrgan_bin() -> str | None:
    """Find the realesrgan-ncnn-vulkan binary."""
    # Check common locations
    candidates = [
        shutil.which("realesrgan-ncnn-vulkan"),
        shutil.which("realesrgan"),
        str(Path.home() / "realesrgan-ncnn-vulkan" / "realesrgan-ncnn-vulkan"),
        str(Path.home() / ".local" / "bin" / "realesrgan-ncnn-vulkan"),
    ]
    # Check in Adept runtime directories
    runtime_base = os.environ.get("ADEPT_RUNTIME_DIR", "")
    if runtime_base:
        candidates.extend([
            str(Path(runtime_base) / "realesrgan-ncnn-vulkan" / "realesrgan-ncnn-vulkan"),
            str(Path(runtime_base) / "bin" / "realesrgan-ncnn-vulkan"),
        ])
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _realesrgan_models_dir() -> Path:
    """Directory containing Real-ESRGAN model files."""
    runtime_base = os.environ.get("ADEPT_RUNTIME_DIR", "")
    if runtime_base:
        models = Path(runtime_base) / "realesrgan-ncnn-vulkan" / "models"
        if models.is_dir():
            return models
    home_models = Path.home() / "realesrgan-ncnn-vulkan" / "models"
    if home_models.is_dir():
        return home_models
    # Fallback: look adjacent to binary
    bin_path = _realesrgan_bin()
    if bin_path:
        adj = Path(bin_path).parent / "models"
        if adj.is_dir():
            return adj
    return Path("./models")


def upscale_frame(
    input_path: str,
    output_path: str,
    engine: str = "ffmpeg-scale",
    model: str = "lanczos",
    target_width: int = 1920,
    target_height: int = 1080,
) -> str:
    """Upscale a single video or image to the target resolution.

    Args:
        input_path: Source file path.
        output_path: Destination file path.
        engine: Upscaling engine ('realesrgan-ncnn-vulkan' or 'ffmpeg-scale').
        model: Model name for the engine.
        target_width: Target width in pixels.
        target_height: Target height in pixels.

    Returns:
        The output file path.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if engine == "realesrgan-ncnn-vulkan":
        bin_path = _realesrgan_bin()
        if not bin_path:
            logger.warning("realesrgan-ncnn-vulkan binary not found, falling back to ffmpeg-scale")
            engine = "ffmpeg-scale"

    if engine == "realesrgan-ncnn-vulkan":
        models_dir = _realesrgan_models_dir()
        cmd = [
            str(bin_path),
            "-i", str(input_path),
            "-o", str(output_path),
            "-s", "4" if "4x" in model else "2",
            "-m", str(models_dir),
        ]
        if "anime" in model:
            cmd.extend(["-n", model])
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0 or not out.is_file():
            raise RuntimeError(f"Real-ESRGAN upscale failed: {(proc.stderr or proc.stdout)[:1000]}")
    else:
        # FFmpeg software scaling
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"scale={target_width}:{target_height}:flags={model}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0 or not out.is_file():
            raise RuntimeError(f"FFmpeg scale failed: {(proc.stderr or proc.stdout)[:1000]}")

    return str(out)


def _parse_resolution(resolution_str: str) -> tuple[int, int]:
    """Parse a resolution string like '1920x1080' or '4K' into (width, height)."""
    resolution_str = resolution_str.strip().upper()
    preset = {
        "480P": (854, 480),
        "720P": (1280, 720),
        "1080P": (1920, 1080),
        "1440P": (2560, 1440),
        "4K": (3840, 2160),
        "8K": (7680, 4320),
    }
    if resolution_str in preset:
        return preset[resolution_str]
    if "x" in resolution_str.lower():
        parts = resolution_str.lower().split("x")
        try:
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
    return (1920, 1080)  # default


def upscale_asset(
    db: Session,
    project_id: str,
    asset_id: str,
    engine: str,
    model: str,
    target_resolution: str,
    *,
    preview: bool = False,
) -> dict[str, Any]:
    """Upscale a Library asset to the target resolution.

    Creates a new upscaled asset in the Library. Does not modify the original.

    Args:
        db: Database session.
        project_id: Project ID.
        asset_id: Source asset ID.
        engine: Upscaling engine.
        model: Model name.
        target_resolution: Target resolution string.
        preview: If True, only upscale a short segment.

    Returns:
        Dict with output_asset_id, engine, model, input_size, output_size.
    """
    source = db.get(Asset, asset_id)
    if not source:
        raise ValueError(f"Asset {asset_id} not found")

    source_path = str(source.path) if source.path else None
    if not source_path or not Path(source_path).is_file():
        raise ValueError(f"Asset {asset_id} has no valid file path")

    target_w, target_h = _parse_resolution(target_resolution)

    # For preview, extract a short segment and upscale that
    if preview:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            preview_path = tmp.name
        # Extract first 3 seconds
        extract_cmd = [
            "ffmpeg", "-y",
            "-t", "3",
            "-i", source_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            preview_path,
        ]
        subprocess.run(extract_cmd, capture_output=True, text=True, timeout=60)
        input_for_upscale = preview_path
    else:
        input_for_upscale = source_path

    dest_name = f"upscaled_{uuid.uuid4().hex[:12]}_{Path(source_path).name}"
    project = db.get(Project, project_id)
    base_dir = Path(project.directory) if project and project.directory else Path(source_path).parent
    dest_path = base_dir / "upscaled" / dest_name

    try:
        upscale_frame(input_for_upscale, str(dest_path), engine, model, target_w, target_h)

        # Get original file info
        input_ext = Path(source_path).suffix.lower()
        kind = "image" if input_ext in (".png", ".jpg", ".jpeg", ".webp") else "video"

        # Register as a Library asset
        upscaled_asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind=kind,
            name=f"{Path(source_path).stem} ({target_resolution})",
            path=str(dest_path),
            mime_type="video/mp4",
            size=dest_path.stat().st_size if dest_path.is_file() else 0,
        )
        db.add(upscaled_asset)
        db.commit()
        db.refresh(upscaled_asset)
    finally:
        if preview and Path(preview_path).is_file():
            Path(preview_path).unlink(missing_ok=True)

    return {
        "ok": True,
        "output_asset_id": upscaled_asset.id,
        "engine": engine,
        "model": model,
        "input_resolution": "source",
        "output_resolution": f"{target_w}x{target_h}",
        "upscaled_name": f"{Path(source_path).stem} ({target_resolution})",
        "preview": preview,
    }


preview_upscale = lambda db, pid, aid, engine, model, resolution: upscale_asset(
    db, pid, aid, engine, model, resolution, preview=True
)
