"""Shared GenerationJob DTO — one progress contract for every Co-Director generate.

Modality is an open string so ACE Studio, TTS, upscale, and later tools can
attach without a weekly enum redesign. Prefer the production-intent taxonomy
plus voice / music / sfx / upscale / edit.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


GenerationJobStatus = Literal[
    "queued",
    "preparing",
    "running",
    "completed",
    "failed",
    "cancelled",
]

# Creator-facing stages. Backend/attention/compile names stay in Diagnostics.
CREATOR_STAGES: tuple[str, ...] = (
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


class GenerationJob(BaseModel):
    """Normalization projection over Studio Job + ExecutionPlan."""

    id: str
    executionId: str = ""
    modality: str = "image"
    operation: str = "image.generate"
    provider: str = ""
    model: str = ""
    status: GenerationJobStatus = "queued"
    stage: str = "Preparing"
    progressPercent: Optional[int] = None
    elapsedSec: Optional[float] = None
    queuePosition: Optional[int] = None
    outputAsset: Optional[str] = None
    error: Optional[str] = None
    cancellable: bool = True
    productionRole: str = ""
    intendedVideoProvider: str = ""
    jobScopedOverride: bool = False
    providerLabel: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
