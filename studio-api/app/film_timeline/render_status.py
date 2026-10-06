"""Creator-facing render status copied from a job status the sync already read.

Local renders keep the fraction Comfy already measured. Hosted API renders
have no sampler count, so their percent follows the provider phase the poll
already observed: queued, in progress, then finalizing. It never reaches 100
until the finished file is saved.
"""

from __future__ import annotations

import math
import time
from typing import Any, Callable

from ..video_runtime.progress_telemetry import CREATOR_PHASE_LABELS, creator_phase_label

_ALLOWED_LABELS = set(CREATOR_PHASE_LABELS.values()) | {"Preparing model", "Generating", "Finalizing", "Decoding"}

# Time the creator can cancel an API video job before the provider is called.
API_PREPARATION_SEC = 10.0


def note_api_render_progress(rec: dict[str, Any], *, message: str, elapsed_sec: float) -> None:
    """Store a hosted-provider percent on the in-memory job the sync already reads.

    Fal reports queue, in-progress, and complete. It does not report a step
    count, so in-progress eases toward 90% and stops there until the file lands.
    """

    msg = str(message or "").lower()
    elapsed = max(0.0, float(elapsed_sec or 0.0))
    if "prepar" in msg:
        frac, phase, api_phase = 0.05, "Preparing model", "preparing"
    elif "download" in msg or "finaliz" in msg:
        frac, phase, api_phase = 0.92, "Finalizing", "generating"
    elif "in progress" in msg or msg.strip() == "generating":
        frac = min(0.90, 0.18 + 0.72 * (1.0 - math.exp(-elapsed / 75.0)))
        phase, api_phase = "Generating", "generating"
    else:
        # Provider has accepted the job. Cancel is no longer offered.
        frac, phase, api_phase = 0.12, "Queued", "generating"
    rec["progress"] = frac
    rec["apiPhase"] = api_phase
    rec["progressTelemetry"] = {
        "progress": frac,
        "progressGrounded": False,
        "phaseLabel": phase,
        "apiPhase": api_phase,
        "elapsedActiveTime": elapsed,
        "progressSource": "api_provider",
    }


def hold_api_preparation(
    rec: dict[str, Any],
    *,
    seconds: float = API_PREPARATION_SEC,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Wait before an API video provider call. False means the creator cancelled."""

    rec["status"] = str(rec.get("status") or "running")
    started = monotonic()
    while True:
        elapsed = max(0.0, monotonic() - started)
        note_api_render_progress(rec, message="preparing", elapsed_sec=elapsed)
        if str(rec.get("status") or "") == "cancelled":
            return False
        if elapsed >= seconds:
            return str(rec.get("status") or "") != "cancelled"
        sleep(min(0.4, max(0.0, seconds - elapsed)))


def begin_api_generation(rec: dict[str, Any]) -> None:
    """Mark the provider call as started. Cancel is no longer offered."""

    rec["apiPhase"] = "generating"
    tel = dict(rec.get("progressTelemetry") or {})
    tel["apiPhase"] = "generating"
    if not tel.get("phaseLabel"):
        tel["phaseLabel"] = "Generating"
    rec["progressTelemetry"] = tel


def creator_render_status(
    *,
    progress: float,
    telemetry: dict[str, Any] | None,
    segment_status: str,
) -> dict[str, Any]:
    """Pass through grounded progress and a creator phase. Never invent a percent."""

    tel = telemetry if isinstance(telemetry, dict) else {}
    grounded = bool(tel.get("progressGrounded"))
    stored = tel.get("progress")
    out: dict[str, Any] = {
        "progressGrounded": grounded,
        "status": str(segment_status or ""),
    }
    phase = str(tel.get("phase") or "").strip()
    label = creator_phase_label(phase) if phase else str(tel.get("phaseLabel") or "").strip()
    if label in _ALLOWED_LABELS:
        out["phaseLabel"] = label
    api_phase = str(tel.get("apiPhase") or "").strip()
    if api_phase in {"preparing", "generating"}:
        out["apiPhase"] = api_phase
    if tel.get("clearProgress"):
        out["progressGrounded"] = False
    elif isinstance(stored, (int, float)) and not isinstance(stored, bool):
        out["progress"] = max(0.0, min(1.0, float(stored)))
    elif grounded:
        out["progress"] = max(0.0, min(1.0, float(progress or 0.0)))
    elapsed = tel.get("elapsedActiveTime")
    if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and float(elapsed) >= 0:
        out["elapsedSec"] = float(elapsed)
    return out
