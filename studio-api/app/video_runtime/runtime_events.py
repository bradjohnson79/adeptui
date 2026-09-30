"""Canonical generator runtime events — local Comfy and hosted providers.

Governing doc: docs/release-gate/universal-preview-cancel/UNIVERSAL_GENERATOR_PREVIEW_CANCEL.md

This module is additive. The certified H3 tap and PreviewBus internals stay unchanged.
A bridge may subscribe to PreviewBus and dual-emit these envelopes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class GeneratorEventType(str, Enum):
    PREPARING = "PREPARING"
    PROGRESS = "PROGRESS"
    PREVIEW_FRAME = "PREVIEW_FRAME"
    PREVIEW_VIDEO = "PREVIEW_VIDEO"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    CANCEL_REJECTED = "CANCEL_REJECTED"
    FAILED = "FAILED"


CREATOR_STAGES = (
    "Preparing",
    "Loading model",
    "Encoding",
    "Generating",
    "Decoding",
    "Saving",
    "Complete",
    "Failed",
    "Cancelled",
    "Queued",
)

_STAGE_MAP = {
    "planning": "Preparing",
    "queued": "Queued",
    "preparing": "Preparing",
    "claimed": "Preparing",
    "loadingmodels": "Loading model",
    "loading model": "Loading model",
    "loading_models": "Loading model",
    "encoding": "Encoding",
    "sampling": "Generating",
    "generating": "Generating",
    "processing": "Generating",
    "running": "Generating",
    "decoding": "Decoding",
    "saving": "Saving",
    "assembling": "Saving",
    "post": "Saving",
    "complete": "Complete",
    "completed": "Complete",
    "cancelling": "Cancelled",
    "cancel_requested": "Cancelled",
    "cancelled": "Cancelled",
    "cancel_failed_runtime_active": "Failed",
    "failed": "Failed",
}

# fal / hosted coarse buckets — never emit as progressPercent
DISHONEST_PROGRESS_BUCKETS = frozenset({0.2, 0.25, 0.55, 0.9})


class PreviewRef(BaseModel):
    url: str
    mimeType: str
    timestamp: str
    sequence: int
    width: Optional[int] = None
    height: Optional[int] = None
    expiresAt: Optional[str] = None
    draft: bool = True


class GeneratorRuntimeEvent(BaseModel):
    executionId: str = ""
    jobId: str
    provider: str
    modelId: str
    eventType: GeneratorEventType
    createdAt: str
    progressPercent: Optional[int] = None
    stage: str = ""
    preview: Optional[PreviewRef] = None
    providerJobId: Optional[str] = None
    outputAssetId: Optional[str] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    cancelReason: Optional[str] = None
    capabilities: Optional[dict[str, Any]] = None


class RuntimeEventEnvelope(BaseModel):
    event: str = "runtime_event"
    runtimeEvent: GeneratorRuntimeEvent
    ts: float = 0.0


def creator_stage(raw: str | None) -> str:
    token = "".join(ch for ch in str(raw or "").lower() if ch.isalnum() or ch in {" ", "_"})
    token = token.replace(" ", "")
    for key, label in _STAGE_MAP.items():
        if token == key.replace(" ", "").replace("_", ""):
            return label
    compact = str(raw or "").strip()
    return compact if compact in CREATOR_STAGES else (compact.title() if compact else "Generating")


def honest_progress_percent(value: Any) -> Optional[int]:
    """Return 0–100 only when the value is a real fraction, not a coarse bucket."""
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return None
    if raw in DISHONEST_PROGRESS_BUCKETS:
        return None
    if 0 <= raw <= 1:
        pct = int(round(raw * 100))
    elif 0 <= raw <= 100:
        pct = int(round(raw))
    else:
        return None
    if pct < 0 or pct > 100:
        return None
    return pct


def normalize_from_preview(
    preview: dict[str, Any],
    *,
    provider: str,
    model_id: str,
    execution_id: str = "",
    created_at: str,
    capabilities: Optional[dict[str, Any]] = None,
) -> GeneratorRuntimeEvent:
    job_id = str(preview.get("jobId") or "").strip()
    if not job_id:
        raise ValueError("GeneratorRuntimeEvent requires jobId")
    media = str(preview.get("mediaType") or "image").lower()
    event_type = (
        GeneratorEventType.PREVIEW_VIDEO if media == "video" else GeneratorEventType.PREVIEW_FRAME
    )
    local_path = str(preview.get("localPath") or preview.get("sourceUrl") or "").strip()
    mime = "video/mp4" if media == "video" else "image/jpeg"
    if local_path.lower().endswith(".png"):
        mime = "image/png"
    return GeneratorRuntimeEvent(
        executionId=execution_id,
        jobId=job_id,
        provider=provider,
        modelId=model_id,
        eventType=event_type,
        createdAt=created_at,
        progressPercent=honest_progress_percent(preview.get("progress")),
        stage=creator_stage(preview.get("stage") or "generating"),
        preview=PreviewRef(
            url=local_path,
            mimeType=mime,
            timestamp=str(preview.get("createdAt") or created_at),
            sequence=int(preview.get("sequenceNumber") or 1),
            width=preview.get("width"),
            height=preview.get("height"),
            draft=True,
        ),
        capabilities=capabilities,
    )


def normalize_from_job_status(
    *,
    job_id: str,
    status: str,
    stage: str = "",
    message: str = "",
    provider: str,
    model_id: str,
    execution_id: str = "",
    created_at: str,
    progress: Any = None,
    provider_job_id: Optional[str] = None,
    output_asset_id: Optional[str] = None,
    error_code: Optional[str] = None,
    cancel_reason: Optional[str] = None,
    capabilities: Optional[dict[str, Any]] = None,
) -> GeneratorRuntimeEvent:
    if not str(job_id or "").strip():
        raise ValueError("GeneratorRuntimeEvent requires jobId")
    token = str(status or "").strip().lower()
    event_type = GeneratorEventType.PROGRESS
    if token in {"queued", "preparing", "claimed"}:
        event_type = GeneratorEventType.PREPARING
    elif token in {"cancelling", "cancel_requested"}:
        event_type = GeneratorEventType.CANCEL_REQUESTED
    elif token in {"cancelled", "canceled"}:
        event_type = GeneratorEventType.CANCELLED
    elif token == "cancel_rejected":
        event_type = GeneratorEventType.CANCEL_REJECTED
    elif token == "cancel_failed_runtime_active":
        event_type = GeneratorEventType.FAILED
        error_code = error_code or "COMFY_CANCEL_NOT_CONFIRMED"
    elif token in {"done", "completed"}:
        event_type = GeneratorEventType.COMPLETED
    elif token == "failed":
        event_type = GeneratorEventType.FAILED
    elif token in {"assembling", "post"}:
        event_type = GeneratorEventType.FINALIZING
    return GeneratorRuntimeEvent(
        executionId=execution_id,
        jobId=job_id,
        provider=provider,
        modelId=model_id,
        eventType=event_type,
        createdAt=created_at,
        progressPercent=honest_progress_percent(progress),
        stage=creator_stage(stage or token),
        providerJobId=provider_job_id,
        outputAssetId=output_asset_id,
        errorCode=error_code,
        errorMessage=message or None,
        cancelReason=cancel_reason,
        capabilities=capabilities,
    )
