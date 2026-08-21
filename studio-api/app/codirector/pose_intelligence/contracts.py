"""Revision C Phase 2 — PoseCraft world-state contracts.

These packets reference WorldStatePacket (world-state-v1). They do not fork
the Revision C schema. JEPA embeddings never appear here.

Authority:

    Explicit creator pose
      > CRS / character canon
      > Approved Spatial Map
      > PoseCraft intended state
      > Observed video / JEPA
      > raw perception

PoseCraft is authoritative for user-selected pose intent.
JEPA never overwrites a creator pose.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ..world_intelligence.contracts import WorldStatePacket

POSE_PACKET_SCHEMA = "pose-world-state-v1"
POSE_SEQUENCE_SCHEMA = "pose-sequence-state-v1"
POSE_CONDITIONING_SCHEMA = "pose-motion-conditioning-v1"
POSE_REVIEW_SCHEMA = "pose-continuity-review-v1"
POSE_ANALYSIS_VERSION = "pose-kinematic-v1"

PoseAvailability = Literal[
    "available", "unavailable", "low_confidence", "degraded", "insufficient_reference"
]
StateKind = Literal["intended", "observed"]
StanceType = Literal[
    "standing", "crouching", "sitting", "kneeling", "prone", "leaning", "unknown"
]
BalanceState = Literal["stable", "unstable", "unsupported", "uncertain"]
SupportLimb = Literal["left_foot", "right_foot", "both", "none", "other", "uncertain"]
ConfidenceLevel = Literal["known", "uncertain", "insufficient_reference"]
ChangeKind = Literal[
    "contact_gained",
    "contact_lost",
    "foot_planted",
    "foot_released",
    "body_rotated",
    "character_translated",
    "object_moved",
    "facing_changed",
    "support_changed",
    "pose_converged",
    "pose_diverged",
    "discontinuity",
]


def _nid(prefix: str = "pws_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Vec3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class LimbConfiguration(BaseModel):
    leftKneeFlex: float = 0.0
    rightKneeFlex: float = 0.0
    leftElbowFlex: float = 0.0
    rightElbowFlex: float = 0.0
    leftHipFlex: float = 0.0
    rightHipFlex: float = 0.0
    spineBend: float = 0.0


class CharacterPoseState(BaseModel):
    characterId: Optional[str] = None
    identityId: Optional[str] = None
    figureId: str = ""
    figureName: str = ""
    archetypeId: str = ""
    poseId: Optional[str] = None
    poseLabel: Optional[str] = None
    poseRevision: int = 0
    bodyOrientation: Vec3 = Field(default_factory=Vec3)
    headOrientation: Vec3 = Field(default_factory=Vec3)
    torsoOrientation: Vec3 = Field(default_factory=Vec3)
    limbConfiguration: LimbConfiguration = Field(default_factory=LimbConfiguration)
    facingDirection: float = 0.0
    centerOfMass: Vec3 = Field(default_factory=Vec3)
    primarySupport: SupportLimb = "uncertain"
    secondarySupport: SupportLimb = "uncertain"
    weightLeft: float = 0.5
    weightRight: float = 0.5
    balance: BalanceState = "uncertain"
    stance: StanceType = "unknown"
    tension: str = ""
    directionalMomentum: str = ""
    momentumConfidence: ConfidenceLevel = "insufficient_reference"


class ContactEdge(BaseModel):
    bodyPart: str = ""
    targetId: str = ""
    targetKind: str = ""
    targetLabel: str = ""
    relation: str = "contact"
    confidence: ConfidenceLevel = "uncertain"
    distanceM: Optional[float] = None


class ContactGraph(BaseModel):
    edges: list[ContactEdge] = Field(default_factory=list)

    def parts_touching(self, body_part: str) -> list[ContactEdge]:
        key = body_part.lower()
        return [edge for edge in self.edges if edge.bodyPart.lower() == key]


class InteractionState(BaseModel):
    groundContact: bool = False
    footContact: list[str] = Field(default_factory=list)
    handContact: list[str] = Field(default_factory=list)
    bodyToObject: list[str] = Field(default_factory=list)
    bodyToCharacter: list[str] = Field(default_factory=list)
    seatedContact: bool = False
    leaningContact: bool = False
    heldObjects: list[str] = Field(default_factory=list)
    objectSupport: list[str] = Field(default_factory=list)
    reachState: str = ""
    gripConfidence: ConfidenceLevel = "uncertain"
    graph: ContactGraph = Field(default_factory=ContactGraph)


class EnvironmentRelationship(BaseModel):
    nearbyGeometry: list[str] = Field(default_factory=list)
    relevantProps: list[str] = Field(default_factory=list)
    floorRelationship: str = ""
    wallRelationship: str = ""
    furnitureRelationship: str = ""
    obstacles: list[str] = Field(default_factory=list)
    spatialConstraints: list[str] = Field(default_factory=list)
    characterLocation: str = ""
    spatialPhrases: list[str] = Field(default_factory=list)


class MotionInterpretation(BaseModel):
    incomingMovement: str = ""
    outgoingMovement: str = ""
    motionDirection: str = ""
    rotationDirection: str = ""
    plantedLimb: str = ""
    movingLimb: str = ""
    transitionState: str = ""
    unfinishedAction: str = ""
    likelyContinuation: str = ""
    discontinuityWarnings: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "insufficient_reference"


class ProductionConstraints(BaseModel):
    preserveContact: list[str] = Field(default_factory=list)
    preserveSupportFoot: str = ""
    preserveFacing: bool = True
    preserveHandObject: list[str] = Field(default_factory=list)
    preservePropPosition: list[str] = Field(default_factory=list)
    preserveScenePlacement: bool = True
    preserveMomentum: bool = False
    forbiddenDiscontinuity: list[str] = Field(default_factory=list)
    continuityRisk: list[str] = Field(default_factory=list)
    stylizationOverride: bool = False
    creatorIntentHonored: bool = True


class PoseChange(BaseModel):
    kind: ChangeKind
    summary: str = ""
    fromValue: str = ""
    toValue: str = ""
    severity: Literal["none", "minor", "moderate", "major"] = "minor"
    confidence: ConfidenceLevel = "uncertain"


class PoseWorldStatePacket(BaseModel):
    """Structured PoseCraft physical/world state.

    Kinematic fields come from the PoseCraft scene graph.
    `world` is the Revision C WorldStatePacket (visual JEPA signal or unavailable).
    """

    schemaVersion: str = POSE_PACKET_SCHEMA
    packetId: str = Field(default_factory=_nid)
    availability: PoseAvailability = "unavailable"
    reason: str = ""
    stateKind: StateKind = "intended"
    projectId: str = ""
    sceneId: str = ""
    snapshotId: Optional[str] = None
    imageAssetId: Optional[str] = None
    analysisVersion: str = POSE_ANALYSIS_VERSION
    createdAt: str = Field(default_factory=_now)
    character: CharacterPoseState = Field(default_factory=CharacterPoseState)
    interaction: InteractionState = Field(default_factory=InteractionState)
    environment: EnvironmentRelationship = Field(default_factory=EnvironmentRelationship)
    motion: MotionInterpretation = Field(default_factory=MotionInterpretation)
    constraints: ProductionConstraints = Field(default_factory=ProductionConstraints)
    warnings: list[str] = Field(default_factory=list)
    creatorFacingSummary: str = ""
    creatorFacingDetails: str = ""
    world: WorldStatePacket = Field(default_factory=WorldStatePacket)
    cacheKey: str = ""
    extras: dict[str, Any] = Field(default_factory=dict)

    def is_actionable(self) -> bool:
        return self.availability in {"available", "degraded", "low_confidence"}

    def honors_creator_intent(self) -> bool:
        return self.constraints.creatorIntentHonored


class PoseTransition(BaseModel):
    fromPoseId: str = ""
    toPoseId: str = ""
    fromPacketId: str = ""
    toPacketId: str = ""
    changes: list[PoseChange] = Field(default_factory=list)
    plantedContacts: list[str] = Field(default_factory=list)
    movingContacts: list[str] = Field(default_factory=list)
    actionProgression: str = ""
    plausibilityWarnings: list[str] = Field(default_factory=list)
    nextStateSuggestion: str = ""
    confidence: ConfidenceLevel = "uncertain"


class PoseSequenceState(BaseModel):
    schemaVersion: str = POSE_SEQUENCE_SCHEMA
    sequenceId: str = Field(default_factory=lambda: _nid("pss_"))
    projectId: str = ""
    orderedPoseIds: list[str] = Field(default_factory=list)
    orderedPacketIds: list[str] = Field(default_factory=list)
    transitions: list[PoseTransition] = Field(default_factory=list)
    actionProgression: str = ""
    momentum: str = ""
    continuityWarnings: list[str] = Field(default_factory=list)
    nextStateSuggestions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "uncertain"
    provenance: str = "posecraft-snapshots"
    createdAt: str = Field(default_factory=_now)


class PoseMotionConditioningPacket(BaseModel):
    """Provider-neutral compiled facts for video adapters. No embeddings."""

    schemaVersion: str = POSE_CONDITIONING_SCHEMA
    packetId: str = Field(default_factory=lambda: _nid("pmc_"))
    projectId: str = ""
    sourcePosePacketId: str = ""
    subjectIdentity: str = ""
    characterId: Optional[str] = None
    poseState: str = ""
    actionState: str = ""
    bodyOrientation: str = ""
    plantedLimbs: list[str] = Field(default_factory=list)
    movingLimbs: list[str] = Field(default_factory=list)
    contactPoints: list[str] = Field(default_factory=list)
    objectInteractions: list[str] = Field(default_factory=list)
    expectedNextMotion: str = ""
    momentum: str = ""
    cameraRelativeDirection: str = ""
    preserveConstraints: list[str] = Field(default_factory=list)
    allowedReleaseConditions: list[str] = Field(default_factory=list)
    prohibitedDiscontinuities: list[str] = Field(default_factory=list)
    styleOverride: str = ""
    confidence: ConfidenceLevel = "uncertain"
    sourceProvenance: str = "posecraft-intended"
    creatorFacingSummary: str = ""
    createdAt: str = Field(default_factory=_now)


class PoseContinuityReview(BaseModel):
    """Intended PoseCraft state vs observed video / world state."""

    schemaVersion: str = POSE_REVIEW_SCHEMA
    reviewId: str = Field(default_factory=lambda: _nid("pcr_"))
    projectId: str = ""
    intended: Optional[PoseWorldStatePacket] = None
    observedWorld: Optional[WorldStatePacket] = None
    observedSummary: str = ""
    changes: list[PoseChange] = Field(default_factory=list)
    continuityRisk: list[str] = Field(default_factory=list)
    nextBatchGuidance: list[str] = Field(default_factory=list)
    authorityNote: str = (
        "Observed video is new evidence. PoseCraft is starting intent. "
        "Do not overwrite newer observed state with stale pose assumptions."
    )
    createdAt: str = Field(default_factory=_now)
