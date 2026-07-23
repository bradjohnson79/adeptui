from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Literal, Optional

VramTier = Literal[8, 16, 24, 32]


@dataclass(frozen=True)
class VramProfile:
    """Generation budget tuned for a GPU VRAM class."""

    vram_gb: VramTier
    label: str
    width: int
    height: int
    fps: int
    max_duration_sec: float
    max_frames: int
    steps_draft: int
    steps_quality: int
    image_tool_size: int
    lipsync_size: int
    lipsync_steps: int
    # Soft assist: process video in frame windows on low VRAM (documented for future chunked pipelines)
    assist_chunk_frames: int
    recommended_engine: Literal["ltx", "wan"]
    summary: str
    assists: tuple[str, ...]


PROFILES: dict[VramTier, VramProfile] = {
    8: VramProfile(
        vram_gb=8,
        label="8 GB",
        width=640,
        height=384,
        fps=16,
        max_duration_sec=3.0,
        max_frames=49,
        steps_draft=3,
        steps_quality=4,
        image_tool_size=768,
        lipsync_size=384,
        lipsync_steps=10,
        assist_chunk_frames=25,
        recommended_engine="ltx",
        summary="Safe mode for entry GPUs — lower res, short clips, fewer steps, chunked assist.",
        assists=(
            "640×384 output",
            "Max ~3s / 49 frames",
            "16 fps",
            "Reduced sampler steps",
            "Smaller character-sheet & lip-sync working size",
            "Frame-chunk assist (25) to reduce peak VRAM",
        ),
    ),
    16: VramProfile(
        vram_gb=16,
        label="16 GB",
        width=960,
        height=544,
        fps=20,
        max_duration_sec=5.0,
        max_frames=81,
        steps_draft=4,
        steps_quality=6,
        image_tool_size=896,
        lipsync_size=448,
        lipsync_steps=14,
        assist_chunk_frames=41,
        recommended_engine="ltx",
        summary="Balanced — good for most 5s scenes without aggressive quality settings.",
        assists=(
            "960×544 output",
            "Max ~5s / 81 frames",
            "20 fps",
            "Moderate sampler steps",
            "Medium image-tool size",
            "Frame-chunk assist (41)",
        ),
    ),
    24: VramProfile(
        vram_gb=24,
        label="24 GB",
        width=1280,
        height=720,
        fps=24,
        max_duration_sec=6.0,
        max_frames=121,
        steps_draft=4,
        steps_quality=8,
        image_tool_size=1024,
        lipsync_size=512,
        lipsync_steps=18,
        assist_chunk_frames=0,
        recommended_engine="ltx",
        summary="Full HD comfort zone — default Adept quality path for LTX / WAN.",
        assists=(
            "1280×720 output",
            "Max ~6s / 121 frames",
            "24 fps",
            "Full quality steps",
            "Standard lip-sync working size",
        ),
    ),
    32: VramProfile(
        vram_gb=32,
        label="32+ GB",
        width=1280,
        height=720,
        fps=24,
        max_duration_sec=10.0,
        max_frames=193,
        steps_draft=6,
        steps_quality=10,
        image_tool_size=1024,
        lipsync_size=512,
        lipsync_steps=20,
        assist_chunk_frames=0,
        recommended_engine="ltx",
        summary="High-VRAM headroom — longer clips, more steps, fewer OOM safeguards.",
        assists=(
            "1280×720 (room to push higher manually)",
            "Max ~10s / 193 frames",
            "24 fps",
            "Extra sampler steps for quality",
            "Full lip-sync / image-tool budget",
        ),
    ),
}


@dataclass
class RenderPlan:
    vram_gb: VramTier
    label: str
    width: int
    height: int
    fps: int
    steps: int
    max_frames: int
    max_duration_sec: float
    image_tool_size: int
    lipsync_size: int
    lipsync_steps: int
    assist_chunk_frames: int
    summary: str
    assists: list[str]
    clamped: bool = False
    notes: str = ""


def normalize_vram_tier(value: int | float | str | None) -> VramTier:
    try:
        n = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 32
    if n <= 8:
        return 8
    if n <= 16:
        return 16
    if n <= 24:
        return 24
    return 32


def get_profile(vram_gb: int | None) -> VramProfile:
    return PROFILES[normalize_vram_tier(vram_gb)]


def profile_to_dict(profile: VramProfile) -> dict[str, Any]:
    d = asdict(profile)
    d["assists"] = list(profile.assists)
    return d


def list_profiles() -> list[dict[str, Any]]:
    return [profile_to_dict(PROFILES[k]) for k in (8, 16, 24, 32)]


def resolve_render_plan(project: Any) -> RenderPlan:
    """Combine project draft/quality preset with VRAM profile for safe generation."""
    profile = get_profile(getattr(project, "vram_gb", 32))
    quality = (getattr(project, "preset", "quality") or "quality").lower() == "quality"
    steps = profile.steps_quality if quality else profile.steps_draft

    # Never exceed the VRAM ceiling on ≤24 GB; 32+ allows manual upscaling.
    pw = int(getattr(project, "width", profile.width) or profile.width)
    ph = int(getattr(project, "height", profile.height) or profile.height)
    pfps = int(getattr(project, "fps", profile.fps) or profile.fps)
    if profile.vram_gb >= 32:
        width, height, fps = pw, ph, pfps
        clamped = False
    else:
        width = min(pw, profile.width)
        height = min(ph, profile.height)
        fps = min(pfps, profile.fps)
        clamped = width < pw or height < ph or fps < pfps

    notes = ""
    if clamped:
        notes = f"Clamped to {width}×{height} @{fps}fps for {profile.label} VRAM safety."

    return RenderPlan(
        vram_gb=profile.vram_gb,
        label=profile.label,
        width=width,
        height=height,
        fps=fps,
        steps=max(2, steps),
        max_frames=profile.max_frames,
        max_duration_sec=profile.max_duration_sec,
        image_tool_size=profile.image_tool_size,
        lipsync_size=profile.lipsync_size,
        lipsync_steps=profile.lipsync_steps,
        assist_chunk_frames=profile.assist_chunk_frames,
        summary=profile.summary,
        assists=list(profile.assists),
        clamped=clamped,
        notes=notes,
    )


def apply_profile_to_project(project: Any, vram_gb: int) -> VramProfile:
    """Write VRAM preset dimensions onto the project (user-selected Advanced control)."""
    profile = get_profile(vram_gb)
    project.vram_gb = profile.vram_gb
    project.width = profile.width
    project.height = profile.height
    project.fps = profile.fps
    return profile


def detect_vram_gb() -> Optional[int]:
    """Best-effort NVIDIA VRAM detection via nvidia-smi (MiB → GB tier)."""
    stats = query_gpu_stats()
    if not stats.get("ok") or not stats.get("gpus"):
        return None
    try:
        mib = max(float(g.get("memory_total_mib") or 0) for g in stats["gpus"])
        if mib <= 0:
            return None
        return normalize_vram_tier(int(round(mib / 1024.0)))
    except Exception:
        return None


def _parse_smi_number(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text or text.upper() in {"N/A", "[N/A]", "NAN"}:
        return None
    # Strip units like "45 %", "72 C", "320.12 W"
    text = text.replace("%", "").replace("C", "").replace("W", "").replace("MiB", "").strip()
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def query_gpu_stats() -> dict[str, Any]:
    """
    Live NVIDIA GPU stats via nvidia-smi.
    Returns { ok, message, gpus: [{name, memory_*, temp_c, util_*, power_w, ...}], recommended_tier }
    """
    query = (
        "name,driver_version,memory.total,memory.used,memory.free,"
        "temperature.gpu,utilization.gpu,utilization.memory,power.draw,fan.speed"
    )
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={query}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return {"ok": False, "message": "nvidia-smi not found", "gpus": [], "recommended_tier": None}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "gpus": [], "recommended_tier": None}

    if proc.returncode != 0 or not (proc.stdout or "").strip():
        err = (proc.stderr or proc.stdout or "nvidia-smi failed").strip()
        return {"ok": False, "message": err[:300], "gpus": [], "recommended_tier": None}

    gpus: list[dict[str, Any]] = []
    for idx, line in enumerate(proc.stdout.strip().splitlines()):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 9:
            continue
        mem_total = _parse_smi_number(parts[2])
        mem_used = _parse_smi_number(parts[3])
        mem_free = _parse_smi_number(parts[4])
        temp = _parse_smi_number(parts[5])
        util_gpu = _parse_smi_number(parts[6])
        util_mem = _parse_smi_number(parts[7])
        power = _parse_smi_number(parts[8]) if len(parts) > 8 else None
        fan = _parse_smi_number(parts[9]) if len(parts) > 9 else None
        mem_pct = None
        if mem_total and mem_total > 0 and mem_used is not None:
            mem_pct = round(100.0 * mem_used / mem_total, 1)
        gpus.append(
            {
                "index": idx,
                "name": parts[0],
                "driver_version": parts[1],
                "memory_total_mib": mem_total,
                "memory_used_mib": mem_used,
                "memory_free_mib": mem_free,
                "memory_used_pct": mem_pct,
                "temperature_c": temp,
                "utilization_gpu_pct": util_gpu,
                "utilization_memory_pct": util_mem,
                "power_draw_w": power,
                "fan_speed_pct": fan,
            }
        )

    if not gpus:
        return {"ok": False, "message": "No GPUs reported by nvidia-smi", "gpus": [], "recommended_tier": None}

    primary = max(gpus, key=lambda g: float(g.get("memory_total_mib") or 0))
    total_mib = float(primary.get("memory_total_mib") or 0)
    tier = normalize_vram_tier(int(round(total_mib / 1024.0))) if total_mib else None
    return {
        "ok": True,
        "message": "ok",
        "gpus": gpus,
        "primary_index": primary.get("index", 0),
        "recommended_tier": tier,
    }


def clamp_frames(frames: int, plan: RenderPlan) -> tuple[int, bool]:
    """Keep LTX-friendly 8n+1 pattern while respecting VRAM max_frames."""
    frames = max(9, frames)
    frames = ((frames - 1) // 8) * 8 + 1
    if frames <= plan.max_frames:
        return frames, False
    capped = ((plan.max_frames - 1) // 8) * 8 + 1
    return max(9, capped), True
