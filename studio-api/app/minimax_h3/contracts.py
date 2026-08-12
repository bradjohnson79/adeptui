"""Shared contracts for the MiniMax H3 planning surface."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

ThreeFrameStrategy = Literal["segmented-a", "middle-guidance-b", "route-other-c"]
H3SourceSurface = Literal[
    "api",
    "codirector",
    "text-to-video",
    "one-frame",
    "three-frame",
    "timeline",
    "timeline-retake",
    "production-control",
    "library",
    "audio-studio",
    "other",
]
H3Mode = Literal["text-to-video", "one-frame", "first-last", "three-frame", "reference", "edit"]
H3Deployment = Literal["local_weights", "api", "local"]
H3PlanStatus = Literal["draft", "ready", "blocked", "needs_approval", "cancelled", "retry_requested"]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class H3ReferenceAssignment(BaseModel):
    role: str
    assetId: str
    displayName: str
    sourceType: str = "asset"
    notes: str | None = None


class H3TimelineContext(BaseModel):
    sceneId: str | None = None
    shotId: str | None = None
    assemblyPlan: str | None = None
    notes: list[str] = Field(default_factory=list)


class H3AudioPlan(BaseModel):
    assetId: str | None = None
    stereoDetected: bool = False
    channels: int | None = None
    sampleRateHz: int | None = None
    creatorDisclosure: str = "Audio metadata will be preserved only when the source file already includes it."


class H3ThreeFrameInterval(BaseModel):
    intervalId: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    startRole: Literal["start", "middle"]
    endRole: Literal["middle", "end"]
    startAssetId: str
    endAssetId: str
    creatorGoal: str


class H3ThreeFramePlan(BaseModel):
    strategy: ThreeFrameStrategy = "segmented-a"
    nativeSupported: bool = False
    disclosureText: str
    intervals: list[H3ThreeFrameInterval] = Field(default_factory=list)
    assemblyNotes: list[str] = Field(default_factory=list)


class H3FallbackOffer(BaseModel):
    providerId: str = "ltx-local"
    label: str = "LTX 2.3"
    reason: str
    requiresExplicitApproval: bool = True
    preservesInputs: list[str] = Field(default_factory=lambda: ["prompt", "frames", "references"])
    accepted: bool = False
    acceptedBy: str | None = None
    acceptedAt: str | None = None


class H3PreflightResult(BaseModel):
    status: Literal["ready", "blocked", "needs_approval"]
    territory: str
    deployment: H3Deployment
    durationSec: float
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    approvalRequired: bool = False
    fallbackOffer: H3FallbackOffer | None = None
    capability: dict[str, Any] = Field(default_factory=dict)


class AdeptMiniMaxH3Request(BaseModel):
    projectId: str
    prompt: str
    territory: str = ""
    sourceSurface: H3SourceSurface = "api"
    mode: H3Mode = "text-to-video"
    deployment: H3Deployment = "local_weights"
    durationSec: float = Field(default=5.0, ge=0.1, le=60.0)
    referenceAssignments: list[H3ReferenceAssignment] = Field(default_factory=list)
    audioAssetId: str | None = None
    approvalId: str | None = None
    timelineContext: H3TimelineContext | None = None
    creatorNotes: str | None = None
    # Timeline Re-take (Final Systems) — continuity-preserving variation
    retake: bool = False
    sourceTakeId: str | None = None
    deltaInstruction: str | None = None
    originalPrompt: str | None = None

    @field_validator("deployment", mode="before")
    @classmethod
    def _normalize_deployment(cls, value: object) -> object:
        if value == "local":
            return "local_weights"
        return value


class H3GenerationPlan(BaseModel):
    planId: str = Field(default_factory=lambda: str(uuid4()))
    projectId: str
    createdAt: str = Field(default_factory=utc_now)
    updatedAt: str = Field(default_factory=utc_now)
    sourceSurface: H3SourceSurface
    mode: H3Mode
    deployment: H3Deployment
    request: AdeptMiniMaxH3Request
    creatorSummary: str
    creatorDisclosure: str
    referenceAssignments: list[H3ReferenceAssignment] = Field(default_factory=list)
    timelineContext: H3TimelineContext | None = None
    threeFramePlan: H3ThreeFramePlan | None = None
    audioPlan: H3AudioPlan | None = None
    preflight: H3PreflightResult | None = None
    fallbackOffer: H3FallbackOffer | None = None
    status: H3PlanStatus = "draft"
    advancedMetadata: dict[str, Any] = Field(default_factory=dict)
    provenance: list[dict[str, Any]] = Field(default_factory=list)
