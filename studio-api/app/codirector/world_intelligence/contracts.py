"""Revision C — Co-Director World-State Intelligence contracts.

WorldStatePacket is a provider-independent contract for world-state comparison
signals. V-JEPA provides latent embedding comparisons; the packet normalizes
these into a Co-Director-consumable form.

Authority ladder (hard law):

    Explicit creator correction
      > Approved canon
      > Approved Spatial Map
      > Scene Intent / production facts
      > Co-Director reasoning
      > JEPA world-state signal
      > raw perception

JEPA may never silently overwrite approved production truth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

PACKET_SCHEMA = "world-state-v1"
WORLD_INTELLIGENCE_MODEL_ID = "vjepa2-vitl-fpc64-256"
WORLD_INTELLIGENCE_21_MODEL_ID = "vjepa2.1-vitl-fpc64-384"

# ── Policy / status types ────────────────────────────────────────────────

WorldIntelligencePolicy = Literal["off", "automatic", "review_on_change"]
WorldIntelligenceAvailability = Literal[
    "available", "unavailable", "low_confidence", "insufficient_reference"
]
ConfidenceLevel = Literal["known", "uncertain", "insufficient_reference"]
ComparisonType = Literal[
    "single_image",
    "image_pair",
    "reference_set",
    "ordered_scene_states",
    "temporal_clip",
]
RecommendationKind = Literal[
    "consistent",
    "minor_drift",
    "major_drift",
    "world_preserved",
    "local_change_detected",
    "intentional_change",
    "insufficient_context",
]
AnomalySeverity = Literal["none", "minor", "moderate", "major"]
Uncertainty = Literal["known", "unknown"]


def _nid(prefix: str = "wsp_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Source provenance ─────────────────────────────────────────────────────


class WorldStateSource(BaseModel):
    """Identifies which asset(s) and model produced this packet."""

    projectId: str = ""
    sceneId: str = ""
    shotId: Optional[str] = None
    assetId: Optional[str] = None
    sourceType: ComparisonType = "single_image"
    modelId: str = WORLD_INTELLIGENCE_MODEL_ID
    modelRevision: str = ""
    preprocessingVersion: str = "v1"
    createdAt: str = Field(default_factory=_now)


# ── Embedding reference ───────────────────────────────────────────────────


class EmbeddingReference(BaseModel):
    """Lightweight reference to a stored embedding — never the raw tensor."""

    assetId: str = ""
    contentHash: str = ""
    modelId: str = ""
    modelRevision: str = ""
    preprocessingVersion: str = "v1"
    cacheKey: str = ""


class StateComparison(BaseModel):
    """Individual comparison between two world states."""

    referenceAssetId: str = ""
    observedAssetId: str = ""
    similarity: Optional[float] = None
    anomalyScore: Optional[float] = None
    confidence: ConfidenceLevel = "uncertain"


# ── Scene state summary ───────────────────────────────────────────────────


class SceneStateSummary(BaseModel):
    """High-level world-state description. Not a replacement for Revision B."""

    similarityToReference: Optional[float] = None
    similarityToPrevious: Optional[float] = None
    transitionScore: Optional[float] = None
    anomalyScore: Optional[float] = None
    motionState: Optional[str] = None
    environmentState: Optional[str] = None
    structuralState: Optional[str] = None
    confidence: ConfidenceLevel = "uncertain"


# ── Recommendation ────────────────────────────────────────────────────────


class WorldStateRecommendation(BaseModel):
    """Co-Director advisory from world-state analysis."""

    consistent: bool = True
    caution: list[str] = Field(default_factory=list)
    review_: list[str] = Field(default_factory=list, alias="review")
    preserve: list[str] = Field(default_factory=list)
    severity: AnomalySeverity = "none"
    creatorFacingSummary: str = ""
    creatorFacingDetails: str = ""

    model_config = {"populate_by_name": True}


# ── Intentional change record ─────────────────────────────────────────────


class IntentionalChangeRecord(BaseModel):
    """Record of a creator-confirmed intentional world-state change."""

    fromAssetId: str = ""
    toAssetId: str = ""
    projectId: str = ""
    sceneId: str = ""
    label: str = ""
    acceptedAt: str = Field(default_factory=_now)
    creatorNote: str = ""
    expiresAt: Optional[str] = None


# ── Main packet ───────────────────────────────────────────────────────────


class WorldStatePacket(BaseModel):
    """Provider-independent world-state comparison result.

    This is the primary contract between Revision C and Co-Director.
    It is:
      - serializable (JSON)
      - auditable (provenance + model info)
      - lightweight (no raw embeddings)
      - versioned (schemaVersion)
    """

    schemaVersion: str = PACKET_SCHEMA
    packetId: str = Field(default_factory=_nid)
    availability: WorldIntelligenceAvailability = "unavailable"
    reason: str = ""
    source: WorldStateSource = Field(default_factory=WorldStateSource)
    embedding: EmbeddingReference = Field(default_factory=EmbeddingReference)
    sceneState: SceneStateSummary = Field(default_factory=SceneStateSummary)
    comparisons: list[StateComparison] = Field(default_factory=list)
    recommendation: WorldStateRecommendation = Field(
        default_factory=WorldStateRecommendation
    )
    intentionalChange: Optional[IntentionalChangeRecord] = None
    latencyMs: Optional[float] = None
    vramUsedGb: Optional[float] = None
    extras: dict[str, Any] = Field(default_factory=dict)

    def is_actionable(self) -> bool:
        """True if the packet contains a meaningful world-state signal."""
        return self.availability == "available"

    def requires_review(self) -> bool:
        """True if Co-Director should flag this for creator attention."""
        if not self.is_actionable():
            return False
        return bool(self.recommendation.caution or self.recommendation.review_)


# ── World Intelligence Policy ─────────────────────────────────────────────


class CoDirectorWorldIntelligencePolicy(BaseModel):
    """Creator-facing world intelligence policy for a project/scene."""

    enabled: bool = True
    policy: WorldIntelligencePolicy = "automatic"
    modelId: str = WORLD_INTELLIGENCE_MODEL_ID
    showDiagnostics: bool = False
    rejectedPacketIds: list[str] = Field(default_factory=list)
    intentionalChanges: list[IntentionalChangeRecord] = Field(default_factory=list)

    def is_change_intentional(self, from_asset: str, to_asset: str) -> bool:
        """Check if a specific state transition was marked intentional."""
        for change in self.intentionalChanges:
            if change.fromAssetId == from_asset and change.toAssetId == to_asset:
                return True
        return False


# ── World Reference Anchor ────────────────────────────────────────────────


class WorldReferenceAnchor(BaseModel):
    """An approved world reference that defines valid world state."""

    anchorId: str = Field(default_factory=lambda: _nid("wra_"))
    assetId: str = ""
    projectId: str = ""
    sceneId: str = ""
    label: str = ""
    environmentLabel: str = ""
    approvedAt: str = Field(default_factory=_now)
    embedding: EmbeddingReference = Field(default_factory=EmbeddingReference)
    isActive: bool = True
