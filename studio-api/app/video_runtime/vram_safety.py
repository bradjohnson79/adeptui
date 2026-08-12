"""Live VRAM safety states and explicit safe-configuration proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .compatibility_registry import CompatibilityEntry, get_entry
from .job_model import VramSafetyState


@dataclass
class VramEstimate:
    estimated_gb: float
    available_gb: float | None
    state: VramSafetyState
    recommendations: list[str] = field(default_factory=list)
    safe_config: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimatedGb": self.estimated_gb,
            "availableGb": self.available_gb,
            "state": self.state.value,
            "recommendations": list(self.recommendations),
            "safeConfig": dict(self.safe_config),
            "message": self.message,
            "requiresConsent": self.state
            in {VramSafetyState.TIGHT, VramSafetyState.HIGH_RISK, VramSafetyState.INSUFFICIENT},
        }


def _free_vram_gb() -> float | None:
    try:
        from ..vram_profiles import query_gpu_stats

        stats = query_gpu_stats()
        if not stats.get("ok") or not stats.get("gpus"):
            return None
        free_mib = max(float(g.get("memory_free_mib") or 0) for g in stats["gpus"])
        if free_mib <= 0:
            return None
        return round(free_mib / 1024.0, 2)
    except Exception:  # noqa: BLE001
        return None


def estimate_vram(
    workflow_key: str,
    *,
    width: int | None = None,
    height: int | None = None,
    frames: int | None = None,
    batch: int = 1,
    entry: CompatibilityEntry | None = None,
    available_gb: float | None = None,
) -> VramEstimate:
    entry = entry or get_entry(workflow_key)
    if entry is None:
        return VramEstimate(
            estimated_gb=0.0,
            available_gb=available_gb if available_gb is not None else _free_vram_gb(),
            state=VramSafetyState.UNKNOWN,
            message="No compatibility registry entry; VRAM risk unknown.",
        )

    base = float(entry.recommended_vram_gb or entry.min_vram_gb or 0)
    # Scale soft estimate by resolution/frames relative to 1280x720 / 121 frames.
    w = float(width or 1280)
    h = float(height or 720)
    f = float(frames or 81)
    scale = (w * h / (1280.0 * 720.0)) * (f / 121.0) * max(1, batch)
    estimated = max(entry.min_vram_gb, round(base * max(0.55, min(scale, 2.2)), 2))

    free = available_gb if available_gb is not None else _free_vram_gb()
    recommendations: list[str] = []
    safe_config: dict[str, Any] = {}

    if free is None:
        state = VramSafetyState.UNKNOWN
        message = "Could not read free VRAM; proceeding with registry guidance only."
    elif free < entry.min_vram_gb or free < estimated * 0.85:
        state = VramSafetyState.INSUFFICIENT
        message = "This workflow is estimated to exceed available VRAM."
        recommendations, safe_config = _safe_presets(w, h, f, entry)
    elif free < estimated * 1.05 or free < entry.recommended_vram_gb:
        state = VramSafetyState.HIGH_RISK
        message = "VRAM headroom is high-risk for this configuration."
        recommendations, safe_config = _safe_presets(w, h, f, entry)
    elif free < estimated * 1.25:
        state = VramSafetyState.TIGHT
        message = "VRAM is tight; consider a safer configuration."
        recommendations, safe_config = _safe_presets(w, h, f, entry)
    else:
        state = VramSafetyState.SAFE
        message = "Estimated VRAM risk is low."

    return VramEstimate(
        estimated_gb=estimated,
        available_gb=free,
        state=state,
        recommendations=recommendations,
        safe_config=safe_config,
        message=message,
    )


def _safe_presets(
    width: float, height: float, frames: float, entry: CompatibilityEntry
) -> tuple[list[str], dict[str, Any]]:
    new_w, new_h = int(width), int(height)
    new_f = int(frames)
    recs: list[str] = []
    if width >= 1600 or height >= 900:
        new_w, new_h = 1280, 720
        recs.append(f"Reduce resolution from {int(width)}×{int(height)} to 1280×720")
    elif width > 960:
        new_w, new_h = 960, 544
        recs.append(f"Reduce resolution from {int(width)}×{int(height)} to 960×544")
    if frames > 121:
        new_f = 121
        recs.append(f"Reduce frames from {int(frames)} to 121")
    elif frames > 81:
        new_f = 81
        recs.append(f"Reduce frames from {int(frames)} to 81")
    recs.append("Enable tiled VAE")
    recs.append("Enable sequential model unloading")
    recs.append("Enforce single heavy-local job concurrency")
    return recs, {
        "width": new_w,
        "height": new_h,
        "frames": new_f,
        "tiledVae": True,
        "sequentialUnload": True,
        "singleJobConcurrency": True,
    }


def assert_vram_allows_queue(estimate: VramEstimate, *, allow_with_consent: bool = False) -> None:
    """Block insufficient VRAM unless caller already applied/consented to safe config."""
    if estimate.state == VramSafetyState.INSUFFICIENT and not allow_with_consent:
        from ..capabilities.errors import CapabilityError

        raise CapabilityError(
            code="VRAM_INSUFFICIENT",
            message=estimate.message + " Apply a safe configuration before queueing.",
            details=estimate.to_dict(),
            recoverable=True,
            recommended_action="apply_safe_vram_config",
        )
