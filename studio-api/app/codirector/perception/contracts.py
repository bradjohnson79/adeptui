"""Revision B creation-perception contracts.

PerceptionPacket is geometry-only. Furniture lists and spatial prose stay on
EnvironmentVisualCanon. SpatialDraft is a sibling of SpatialMapDocument —
never a production field on the frozen map schema.

Authority ladder (hard law):

    Explicit filmmaker instruction
      > approved CRS / approved Spatial Map slots
      > approved SpatialDraft Accept
      > Co-Director inference
      > raw model detection
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

PACKET_SCHEMA = "creation-perception-v1"
DRAFT_SCHEMA = "spatial-draft-v1"

CapabilityStatus = Literal["unavailable", "testing", "available"]
AuthorityRank = Literal[
    "filmmaker",
    "approved_canon",
    "accepted_draft",
    "inference",
    "raw_detection",
]
EntityKindHint = Literal["character", "prop", "architecture", "unknown"]
OrdinalDepth = Literal["near", "mid", "far", "unknown"]
SlotKind = Literal["character", "prop", "camera"]
FactStatus = Literal["inferred", "accepted", "corrected", "rejected"]
RelationshipPhrase = Literal[
    "ON",
    "UNDER",
    "BEHIND",
    "IN_FRONT_OF",
    "BESIDE",
    "LEFT_OF",
    "RIGHT_OF",
    "INSIDE",
    "OUTSIDE",
    "NEAR",
    "FAR_FROM",
    "ATTACHED_TO",
    "PART_OF",
    "FACING",
]

CHARACTER_COLORS = ("red", "blue", "orange", "green")
PROP_COLORS = ("purple", "brown", "aqua", "gray")
MAX_CHARACTER_SLOTS = 4
MAX_PROP_SLOTS = 4
MAX_CAMERA_SLOTS = 4

PROVIDER_LEAK_KEYS = frozenset(
    {
        "logits",
        "mask_logits",
        "pred_boxes",
        "nms",
        "iou",
        "token_ids",
        "hidden_states",
        "sam_decoder",
        "dino_features",
        "attention",
    }
)


def _nid(prefix: str = "cp_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NormalizedBox(BaseModel):
    """Axis-aligned box in normalized image space [0, 1]."""

    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0

    @field_validator("x0", "y0", "x1", "y1")
    @classmethod
    def _clamp_unit(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


class PerceptionEntity(BaseModel):
    id: str = Field(default_factory=lambda: _nid("ent_"))
    label: str = ""
    kindHint: EntityKindHint = "unknown"
    box: Optional[NormalizedBox] = None
    maskAssetId: str = ""
    confidence: Optional[float] = None
    uncertainty: str = ""
    ordinalDepth: OrdinalDepth = "unknown"


class PairwiseDepth(BaseModel):
    nearerEntityId: str = ""
    fartherEntityId: str = ""
    confidence: Optional[float] = None


class PerceptionDepth(BaseModel):
    """Ordinal depth only. No metric reconstruction."""

    layers: dict[str, OrdinalDepth] = Field(default_factory=dict)
    pairwise: list[PairwiseDepth] = Field(default_factory=list)


class PerceptionProvenance(BaseModel):
    modelIds: list[str] = Field(default_factory=list)
    revisions: dict[str, str] = Field(default_factory=dict)
    hashes: dict[str, str] = Field(default_factory=dict)
    device: str = ""
    leaseEvidence: dict[str, Any] = Field(default_factory=dict)
    worker: str = "stills-perception"


class PerceptionPacket(BaseModel):
    """Provider-independent geometry. No furniture lists. No SAM logits."""

    schemaVersion: str = PACKET_SCHEMA
    packetId: str = Field(default_factory=_nid)
    sourceAssetId: str = ""
    mapId: str = ""
    projectId: str = ""
    availability: CapabilityStatus = "unavailable"
    reason: str = ""
    entities: list[PerceptionEntity] = Field(default_factory=list)
    depth: PerceptionDepth = Field(default_factory=PerceptionDepth)
    pose: dict[str, Any] = Field(default_factory=dict)
    provenance: PerceptionProvenance = Field(default_factory=PerceptionProvenance)
    createdAt: str = Field(default_factory=_now)

    @field_validator("pose")
    @classmethod
    def _pose_empty_or_adept(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            return {}
        leaked = PROVIDER_LEAK_KEYS.intersection(value.keys())
        if leaked:
            raise ValueError(f"provider payload leaked into pose: {sorted(leaked)}")
        return value


def strip_provider_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Drop detector-specific keys before anything leaves the worker."""
    return {key: value for key, value in raw.items() if key not in PROVIDER_LEAK_KEYS}


class ProposedSlotFill(BaseModel):
    id: str = Field(default_factory=lambda: _nid("fill_"))
    kind: SlotKind
    slotIndex: int = 0
    colorKey: str = ""
    label: str = ""
    tag: str = ""
    characterId: str = ""
    propId: str = ""
    characterApproved: bool = False
    normalizedX: Optional[float] = None
    normalizedY: Optional[float] = None
    miniPrompt: str = ""
    orientation: str = ""
    shotSize: str = "auto"
    primarySubject: str = "auto"
    perceptionEntityId: str = ""
    authority: AuthorityRank = "inference"
    factStatus: FactStatus = "inferred"
    notes: str = ""


class UnusedDetection(BaseModel):
    id: str = Field(default_factory=lambda: _nid("unused_"))
    label: str = ""
    kindHint: EntityKindHint = "unknown"
    perceptionEntityId: str = ""
    reason: str = "overflow_or_low_importance"


class ProposedZonePhrase(BaseModel):
    """Glossary only — not SpatialMapDocument.zones."""

    id: str = Field(default_factory=lambda: _nid("zone_"))
    phrase: str = ""
    notes: str = ""
    factStatus: FactStatus = "inferred"


class ProposedRelationship(BaseModel):
    id: str = Field(default_factory=lambda: _nid("rel_"))
    subjectLabel: str = ""
    relation: RelationshipPhrase = "NEAR"
    objectLabel: str = ""
    factStatus: FactStatus = "inferred"
    authority: AuthorityRank = "inference"


class UserCorrection(BaseModel):
    """Once written, inference must not overwrite this fact."""

    id: str = Field(default_factory=lambda: _nid("corr_"))
    factKey: str
    action: Literal["rename", "move", "reject", "accept", "relationship", "zone"] = "rename"
    value: dict[str, Any] = Field(default_factory=dict)
    createdAt: str = Field(default_factory=_now)
    authority: AuthorityRank = "filmmaker"


class SpatialDraft(BaseModel):
    schemaVersion: str = DRAFT_SCHEMA
    draftId: str = Field(default_factory=lambda: _nid("draft_"))
    projectId: str = ""
    mapId: str = ""
    sourceAssetId: str = ""
    reviewLabel: str = "CD Scene Review"
    sceneReviewAvailable: bool = False
    geometryStatus: CapabilityStatus = "unavailable"
    geometryReason: str = ""
    canonAvailability: str = "unavailable"
    canonUnavailableReason: str = ""
    proposedFills: list[ProposedSlotFill] = Field(default_factory=list)
    unusedDetections: list[UnusedDetection] = Field(default_factory=list)
    zonePhrases: list[ProposedZonePhrase] = Field(default_factory=list)
    relationships: list[ProposedRelationship] = Field(default_factory=list)
    userCorrections: list[UserCorrection] = Field(default_factory=list)
    perceptionPacketId: str = ""
    createdAt: str = Field(default_factory=_now)
    updatedAt: str = Field(default_factory=_now)


class AcceptItem(BaseModel):
    fillId: str
    overwrite: bool = False
    label: str = ""


class AcceptRequest(BaseModel):
    items: list[AcceptItem] = Field(default_factory=list)


class AcceptFailure(BaseModel):
    fillId: str = ""
    code: str = ""
    message: str = ""


class AcceptResult(BaseModel):
    ok: bool = False
    documentWritten: bool = False
    acceptedFillIds: list[str] = Field(default_factory=list)
    failures: list[AcceptFailure] = Field(default_factory=list)
    draft: Optional[SpatialDraft] = None


class PerceptionCapability(BaseModel):
    sceneReview: CapabilityStatus = "unavailable"
    sceneReviewReason: str = ""
    geometry: CapabilityStatus = "unavailable"
    geometryReason: str = ""
    autoMask: CapabilityStatus = "unavailable"
    autoMaskReason: str = ""
    chatRequired: bool = False
