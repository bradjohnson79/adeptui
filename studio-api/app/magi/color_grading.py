"""MAGI Color Grading — FFmpeg filter-based color correction.

Uses FFmpeg's built-in video filters (eq, colorbalance, colorchannelmixer,
curves) to apply color grading. No external LUT files required.

Presets are parameter maps that map to FFmpeg filter chains.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from ..db import Asset, Job
from ..media_ops import run_ffmpeg
from sqlalchemy.orm import Session

# ── Color Presets ──────────────────────────────────────────────────────────

ColorPresetParams = dict[str, float]

COLOR_PRESETS: dict[str, dict[str, Any]] = {
    "none": {
        "label": "None",
        "params": {},
        "description": "No color grading applied.",
    },
    "cinematic_neutral": {
        "label": "Cinematic Neutral",
        "params": {
            "contrast": 0.15,
            "saturation": 0.9,
            "gamma": 0.95,
            "shadows": -0.05,
            "highlights": 0.03,
        },
        "description": "Neutral cinematic grade with subtle contrast.",
    },
    "cinematic_warm": {
        "label": "Warm Cinematic",
        "params": {
            "contrast": 0.18,
            "saturation": 0.95,
            "gamma": 0.92,
            "temperature": 0.08,
            "shadows": -0.06,
            "highlights": 0.04,
        },
        "description": "Warm cinematic look with golden highlights.",
    },
    "cinematic_cool": {
        "label": "Cool Cinematic",
        "params": {
            "contrast": 0.2,
            "saturation": 0.85,
            "gamma": 0.9,
            "temperature": -0.1,
            "shadows": -0.08,
            "highlights": 0.02,
        },
        "description": "Cool blue-tinted cinematic grade.",
    },
    "golden_hour": {
        "label": "Golden Hour",
        "params": {
            "contrast": 0.12,
            "saturation": 1.1,
            "gamma": 0.88,
            "temperature": 0.15,
            "tint": 0.05,
            "shadows": -0.03,
            "highlights": 0.08,
        },
        "description": "Warm golden sunlight aesthetic.",
    },
    "teal_orange": {
        "label": "Teal & Orange",
        "params": {
            "contrast": 0.22,
            "saturation": 0.9,
            "gamma": 0.85,
            "temperature": -0.05,
            "shadows": -0.1,
            "highlights": 0.05,
            "shadow_red": -0.15,
            "shadow_blue": 0.12,
            "highlight_red": 0.08,
            "highlight_blue": -0.05,
        },
        "description": "Modern blockbuster teal shadows / orange skin tones.",
    },
    "film_print": {
        "label": "Film Print",
        "params": {
            "contrast": 0.25,
            "saturation": 0.8,
            "gamma": 0.82,
            "shadows": -0.12,
            "highlights": 0.06,
            "shadow_red": 0.05,
            "shadow_green": -0.03,
            "shadow_blue": -0.05,
            "highlight_red": -0.03,
            "highlight_green": 0.02,
        },
        "description": "Classic film print stock emulation.",
    },
    "vintage": {
        "label": "Vintage",
        "params": {
            "contrast": 0.15,
            "saturation": 0.65,
            "gamma": 0.9,
            "temperature": 0.08,
            "shadows": -0.05,
            "highlight_red": -0.05,
            "highlight_green": -0.02,
            "highlight_blue": 0.08,
        },
        "description": "Warm faded vintage photograph look.",
    },
    "high_contrast": {
        "label": "High Contrast",
        "params": {
            "contrast": 0.4,
            "saturation": 1.05,
            "brightness": -0.03,
            "gamma": 0.8,
            "shadows": -0.15,
            "highlights": 0.1,
        },
        "description": "Punchy high-contrast editorial style.",
    },
    "low_contrast": {
        "label": "Low Contrast",
        "params": {
            "contrast": -0.15,
            "saturation": 0.85,
            "brightness": 0.03,
            "gamma": 1.05,
            "shadows": 0.05,
            "highlights": -0.03,
        },
        "description": "Soft muted low-contrast look.",
    },
    "bleach_bypass": {
        "label": "Bleach Bypass",
        "params": {
            "contrast": 0.35,
            "saturation": 0.5,
            "gamma": 0.78,
            "shadows": -0.18,
            "highlights": 0.08,
            "shadow_red": 0.05,
            "shadow_blue": -0.05,
        },
        "description": "High contrast with desaturated, crushed blacks.",
    },
    "dreamy": {
        "label": "Dreamy",
        "params": {
            "contrast": -0.08,
            "saturation": 0.75,
            "gamma": 1.08,
            "brightness": 0.05,
            "temperature": 0.06,
            "shadows": 0.05,
            "highlights": 0.05,
        },
        "description": "Soft ethereal dreamlike quality.",
    },
    "noir": {
        "label": "Noir",
        "params": {
            "contrast": 0.3,
            "saturation": -1.0,
            "gamma": 0.85,
            "shadows": -0.15,
            "highlights": 0.1,
        },
        "description": "Classic black-and-white film noir.",
    },
    "anime_vibrant": {
        "label": "Anime Vibrant",
        "params": {
            "contrast": 0.1,
            "saturation": 1.3,
            "brightness": 0.02,
            "gamma": 0.95,
            "temperature": 0.03,
        },
        "description": "Vibrant saturated colors for anime/stylized content.",
    },
    "muted_drama": {
        "label": "Muted Drama",
        "params": {
            "contrast": 0.2,
            "saturation": 0.6,
            "gamma": 0.88,
            "shadows": -0.1,
            "highlights": 0.03,
            "shadow_blue": 0.05,
            "highlight_red": -0.03,
        },
        "description": "Subdued dramatic palette with cool shadows.",
    },
    "night_moonlight": {
        "label": "Night / Moonlight",
        "params": {
            "contrast": 0.25,
            "saturation": 0.5,
            "gamma": 0.75,
            "brightness": -0.1,
            "temperature": -0.15,
            "shadows": -0.15,
            "highlights": -0.1,
        },
        "description": "Cool blue night scene with crushed shadows.",
    },
}

ALL_PRESET_IDS: list[str] = list(COLOR_PRESETS.keys())


def describe_grade(params: ColorPresetParams, preset_id: str | None) -> str:
    if preset_id and preset_id in COLOR_PRESETS:
        return str(COLOR_PRESETS[preset_id]["label"])
    if params:
        return "Custom look"
    return "None"


def list_color_presets() -> list[dict[str, Any]]:
    """Return all available color presets with metadata."""
    return [
        {
            "id": preset_id,
            "label": meta["label"],
            "description": meta["description"],
        }
        for preset_id, meta in COLOR_PRESETS.items()
    ]


# ── FFmpeg Filter Compilation ──────────────────────────────────────────────


def _param_to_filter(p: float, param_name: str) -> str | None:
    """Convert a single color parameter to an FFmpeg filter expression fragment."""
    eq_contrast = 1.0 + max(-0.5, min(0.5, p))
    eq_saturation = max(0.0, 1.0 + p)
    eq_gamma = max(0.1, 1.0 + (p * -1))
    eq_brightness = max(-1.0, min(1.0, p))

    if param_name == "contrast":
        return f"eq=contrast={eq_contrast:.3f}"
    if param_name == "saturation":
        return f"eq=saturation={eq_saturation:.3f}"
    if param_name == "gamma":
        return f"eq=gamma={eq_gamma:.3f}"
    if param_name == "brightness":
        return f"eq=brightness={eq_brightness:.3f}"
    if param_name == "temperature":
        r = max(-1.0, min(1.0, p))
        return f"colorbalance=rs={r:.3f}:gs={0}:bs={-r:.3f}"
    if param_name == "tint":
        t = max(-1.0, min(1.0, p))
        return f"colorbalance=gs={t:.3f}"
    if param_name == "shadows":
        s = max(-1.0, min(1.0, p))
        return f"colorbalance=rs={s:.3f}:gs={s:.3f}:bs={s:.3f}"
    if param_name == "highlights":
        h = max(-1.0, min(1.0, p))
        return f"colorbalance=rh={h:.3f}:gh={h:.3f}:bh={h:.3f}"
    if param_name == "shadow_red":
        return f"colorbalance=rs={p:.3f}"
    if param_name == "shadow_green":
        return f"colorbalance=gs={p:.3f}"
    if param_name == "shadow_blue":
        return f"colorbalance=bs={p:.3f}"
    if param_name == "highlight_red":
        return f"colorbalance=rh={p:.3f}"
    if param_name == "highlight_green":
        return f"colorbalance=gh={p:.3f}"
    if param_name == "highlight_blue":
        return f"colorbalance=bh={p:.3f}"
    return None


def compile_filter_string(params: ColorPresetParams) -> str:
    """Compile color parameters into a single FFmpeg filter chain string."""
    filters: list[str] = []
    for param_name, value in sorted(params.items()):
        if value == 0:
            continue
        flt = _param_to_filter(value, param_name)
        if flt:
            filters.append(flt)

    # Merge filters by type
    eq_parts: list[str] = []
    cb_parts: list[str] = []
    for f in filters:
        if f.startswith("eq="):
            eq_parts.append(f[3:])
        elif f.startswith("colorbalance="):
            cb_args = f[13:]
            cb_parts.append(cb_args)

    chain: list[str] = []
    if eq_parts:
        eq_values: dict[str, str] = {}
        for part in eq_parts:
            for kv in part.split(":"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    eq_values[k] = v
        merged = ":".join(f"{k}={v}" for k, v in eq_values.items())
        chain.append(f"eq={merged}")
    if cb_parts:
        merged_cb = ":".join(cb_parts)
        chain.append(f"colorbalance={merged_cb}")

    return ",".join(chain)


# ── Color Grade Application ────────────────────────────────────────────────


def apply_color_grade(
    input_path: str,
    output_path: str,
    params: ColorPresetParams,
    *,
    preview_seconds: float | None = None,
) -> str:
    """Apply color grading to a video/image via FFmpeg.

    Args:
        input_path: Source file path.
        output_path: Destination file path.
        params: Color parameter map.
        preview_seconds: If set, only grade the first N seconds (preview mode).

    Returns:
        The output file path.
    """
    filter_str = compile_filter_string(params)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd_parts: list[str] = []
    if preview_seconds and preview_seconds > 0:
        cmd_parts.extend(["-t", f"{preview_seconds:.1f}"])

    cmd_parts.extend(["-i", str(input_path)])

    if filter_str:
        cmd_parts.extend(["-vf", filter_str])

    from .media import probe_media

    has_audio = False
    try:
        has_audio = bool(probe_media(input_path).get("hasAudio")) and not preview_seconds
    except Exception:
        has_audio = False
    cmd_parts.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a" if has_audio else "-an",
        *(["aac"] if has_audio else []),
        "-y",
        str(out),
    ])

    cmd = ["ffmpeg", *cmd_parts]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"Color grade FFmpeg failed: {(proc.stderr or proc.stdout)[:1000]}")

    return str(out)


def apply_color_grade_to_asset(
    db: Session,
    project_id: str,
    asset_id: str,
    preset_id: str | None,
    params: ColorPresetParams | None,
    *,
    preview: bool = False,
) -> dict[str, Any]:
    """Apply color grading to a Library asset.

    Creates a new graded asset in the Library. Does not modify the original.

    Args:
        db: Database session.
        project_id: Project ID.
        asset_id: Source asset ID.
        preset_id: Optional preset ID to use as base.
        params: Color parameters (overrides preset if preset_id is provided).
        preview: If True, only grade the first 3 seconds (fast preview).

    Returns:
        Dict with output_asset_id, preset_id, params, filter_string.
    """
    # Resolve preset params if provided
    resolved: ColorPresetParams = {}
    if preset_id and preset_id in COLOR_PRESETS:
        resolved = dict(COLOR_PRESETS[preset_id]["params"])
    if params:
        resolved.update(params)

    source = db.get(Asset, asset_id)
    if not source:
        raise ValueError(f"Asset {asset_id} not found")

    source_path = str(source.path) if source.path else None
    if not source_path or not Path(source_path).is_file():
        raise ValueError(f"Asset {asset_id} has no valid file path")

    # Preview: grade first 3 seconds; Full: grade entire asset
    duration = 3.0 if preview else None

    dest_name = f"graded_{uuid.uuid4().hex[:12]}_{Path(source_path).name}"
    from .media import cleanup_dir, new_temp_dir

    work = new_temp_dir("color")
    dest_path = work / dest_name

    filter_str = compile_filter_string(resolved)
    try:
        apply_color_grade(source_path, str(dest_path), resolved, preview_seconds=duration)
    except Exception:
        cleanup_dir(work)
        raise

    from ..generation_tools.lineage import register_derived_asset

    try:
        graded_asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=dest_path,
            kind="image" if Path(source_path).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else "video",
            tag="magi_color",
            parent_asset_id=source.id,
            op="color_grade",
            model=preset_id or "custom",
            prompt_meta={
                "operation": "color_grade",
                "preset": preset_id or "custom",
                "parameters": resolved,
                "filterString": filter_str,
                "sourceAssetId": source.id,
                "preview": preview,
            },
            library_key="video.generated",
        )
        db.commit()
    finally:
        cleanup_dir(work)

    return {
        "ok": True,
        "output_asset_id": graded_asset.id,
        "assetId": graded_asset.id,
        "preset_id": preset_id or "custom",
        "params": resolved,
        "filter_string": filter_str,
        "graded_name": describe_grade(resolved, preset_id),
        "preview": preview,
        "sourcePreserved": True,
    }


def preview_color_grade(
    db: Session,
    project_id: str,
    asset_id: str,
    preset_id: str | None,
    params: ColorPresetParams | None,
) -> dict[str, Any]:
    """Quick preview-grade a clip (first 3 seconds only).

    Returns the graded asset for preview without full processing.
    """
    return apply_color_grade_to_asset(db, project_id, asset_id, preset_id, params, preview=True)
