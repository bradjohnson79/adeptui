"""Temporal continuity contracts. Never named ContinuityPacket."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

PACKET_SCHEMA = "temporal-continuity-v1"
FAST_VISION_MODEL_ID = "videochat3-4b"
DEEP_REVIEW_MODEL_ID = "internvideo3-8b-instruct"

PacketAvailability = Literal["ready", "unavailable", "low_confidence"]
ReviewCadence = Literal["automatic", "interval_3", "interval_5", "every_batch"]
ProtectionLevel = Literal["standard", "strong"]
DeepReviewMode = Literal["auto", "off", "on"]
ContinuityDecision = Literal["keep_and_continue", "keep_only", "creator_override"]
Uncertainty = Literal["known", "unknown"]


def _nid(prefix: str = "tcp_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CoDirectorContinuityPolicy(BaseModel):
    """Creator Continuity policy. Distinct from last-frame ContinuityPolicy."""

    enabled: bool = True
    reviewCadence: ReviewCadence = "automatic"
    protection: ProtectionLevel = "strong"
    fastVisionModel: str = FAST_VISION_MODEL_ID
    deepReview: DeepReviewMode = "auto"
    showDebugState: bool = False
    rejectedPacketIds: list[str] = Field(default_factory=list)
    creatorNextBatchNote: str = ""


class PacketSource(BaseModel):
    projectId: str = ""
    sceneId: str = ""
    shotId: Optional[str] = None
    timelineClipId: Optional[str] = None
    batchId: str = ""
    targetBatchId: Optional[str] = None
    modelId: Optional[str] = None
    generatorId: Optional[str] = None
    executionSnapshotId: Optional[str] = None
    bridgeId: Optional[str] = None
    startTime: float = 0.0
    endTime: float = 0.0
    reviewCadence: ReviewCadence = "every_batch"
    perceptionModelId: Optional[str] = None
    deepReviewInvoked: bool = False


class CharacterObservation(BaseModel):
    characterId: Optional[str] = None
    label: str = ""
    crsRevision: Optional[str] = None
    identityConfidence: Optional[float] = None
    identityCertainty: Uncertainty = "unknown"
    screenPosition: Optional[str] = None
    depth: Optional[str] = None
    bodyOrientation: Optional[str] = None
    headOrientation: Optional[str] = None
    gazeTarget: Optional[str] = None
    poseState: Optional[str] = None
    movementDirection: Optional[str] = None
    movementVelocity: Optional[str] = None
    actionState: Optional[str] = None
    actionCompletion: Optional[float] = None
    expression: Optional[str] = None
    dialogueState: Optional[str] = None


class CameraObservation(BaseModel):
    framing: Optional[str] = None
    shotSize: Optional[str] = None
    cameraPosition: Optional[str] = None
    cameraHeight: Optional[str] = None
    cameraOrientation: Optional[str] = None
    movementType: Optional[str] = None
    movementDirection: Optional[str] = None
    movementVelocity: Optional[str] = None
    zoomState: Optional[str] = None
    certainty: Uncertainty = "unknown"


class SceneObservation(BaseModel):
    spatialRelationships: list[str] = Field(default_factory=list)
    majorProps: list[str] = Field(default_factory=list)
    foreground: Optional[str] = None
    midground: Optional[str] = None
    background: Optional[str] = None
    lightingState: Optional[str] = None
    environmentState: Optional[str] = None
    certainty: Uncertainty = "unknown"


class ContinuityScores(BaseModel):
    identity: Uncertainty = "unknown"
    wardrobe: Uncertainty = "unknown"
    hair: Uncertainty = "unknown"
    pose: Uncertainty = "unknown"
    movement: Uncertainty = "unknown"
    gaze: Uncertainty = "unknown"
    blocking: Uncertainty = "unknown"
    camera: Uncertainty = "unknown"
    lighting: Uncertainty = "unknown"
    props: Uncertainty = "unknown"
    environment: Uncertainty = "unknown"


class TimingState(BaseModel):
    completedBeats: list[str] = Field(default_factory=list)
    activeBeats: list[str] = Field(default_factory=list)
    unfinishedBeats: list[str] = Field(default_factory=list)
    estimatedCompletion: list[str] = Field(default_factory=list)


class Assessment(BaseModel):
    intendedState: str = ""
    observedState: str = ""
    differences: list[str] = Field(default_factory=list)
    severity: Literal["none", "minor", "moderate", "major"] = "none"
    confidence: Optional[float] = None
    confidenceCertainty: Uncertainty = "unknown"


class Continuation(BaseModel):
    preserve: list[str] = Field(default_factory=list)
    continue_: list[str] = Field(default_factory=list, alias="continue")
    correct: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    nextBatchDirectives: list[str] = Field(default_factory=list)
    creatorRejected: bool = False

    model_config = {"populate_by_name": True}


class VideoPerceptionObservation(BaseModel):
    """What the vision model reported. Not a Co-Director decision."""

    modelId: str = ""
    timeRange: tuple[float, float] = (0.0, 0.0)
    rawText: str = ""
    characters: list[CharacterObservation] = Field(default_factory=list)
    camera: CameraObservation = Field(default_factory=CameraObservation)
    scene: SceneObservation = Field(default_factory=SceneObservation)
    unfinishedActions: list[str] = Field(default_factory=list)
    completedActions: list[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    parseOk: bool = False



class ImportantEvent(BaseModel):
    """Event observed during full-clip review (not only the tail)."""

    label: str = ""
    approxTimeSec: Optional[float] = None
    phase: Literal["early", "mid", "late", "unknown"] = "unknown"
    detail: str = ""


class VisualAnchor(BaseModel):
    """Stable visual fact to carry into the next R2V shot."""

    kind: str = ""  # character | prop | wardrobe | environment | camera | identity
    label: str = ""
    detail: str = ""
    assetId: Optional[str] = None
    identityId: Optional[str] = None


class ExitState(BaseModel):
    """End-of-shot state used as the handoff digest into N+1."""

    summary: str = ""
    characterStates: list[str] = Field(default_factory=list)
    cameraState: Optional[str] = None
    environmentState: Optional[str] = None


class RollingSceneDigest(BaseModel):
    """Accumulated scene continuity under Co-Director — not a second authority."""

    schemaVersion: str = "rolling-scene-digest-v1"
    preserve: list[str] = Field(default_factory=list)
    continue_: list[str] = Field(default_factory=list, alias="continue")
    avoid: list[str] = Field(default_factory=list)
    importantEvents: list[ImportantEvent] = Field(default_factory=list)
    visualAnchors: list[VisualAnchor] = Field(default_factory=list)
    exitState: ExitState = Field(default_factory=ExitState)
    sourcePacketIds: list[str] = Field(default_factory=list)
    updatedAt: str = Field(default_factory=_now)

    model_config = {"populate_by_name": True}


class TemporalContinuityPacket(BaseModel):
    schemaVersion: str = PACKET_SCHEMA
    packetId: str = Field(default_factory=_nid)
    availability: PacketAvailability = "unavailable"
    reason: Optional[str] = None
    source: PacketSource = Field(default_factory=PacketSource)
    characters: list[CharacterObservation] = Field(default_factory=list)
    camera: CameraObservation = Field(default_factory=CameraObservation)
    scene: SceneObservation = Field(default_factory=SceneObservation)
    continuity: ContinuityScores = Field(default_factory=ContinuityScores)
    timing: TimingState = Field(default_factory=TimingState)
    assessment: Assessment = Field(default_factory=Assessment)
    continuation: Continuation = Field(default_factory=Continuation)
    decision: ContinuityDecision = "keep_and_continue"
    observation: Optional[VideoPerceptionObservation] = None
    creatorMarker: Optional[str] = None
    importantEvents: list[ImportantEvent] = Field(default_factory=list)
    visualAnchors: list[VisualAnchor] = Field(default_factory=list)
    exitState: Optional[ExitState] = None
    rollingSceneDigest: Optional[RollingSceneDigest] = None
    createdAt: str = Field(default_factory=_now)
    extras: dict[str, Any] = Field(default_factory=dict)

    def is_gate_ready(self) -> bool:
        """Only a successful Omni review of the current take releases N+1."""
        return self.availability == "ready"
