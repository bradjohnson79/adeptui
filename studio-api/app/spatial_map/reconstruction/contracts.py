"""SpatialReconstructionPacket — intermediate reconstruction artifact.

Not SpatialMapDocument truth. Not PerceptionPacket. Observed / inferred /
unknown stay explicit. Meter numbers without a scale anchor are provisional.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

PACKET_SCHEMA = "spatial-reconstruction-v1"
EvidenceKind = Literal["observed", "inferred", "unknown"]
ScaleMode = Literal["anchored", "provisional"]
EnvironmentKind = Literal[
    "corridor",
    "room",
    "wide_interior",
    "exterior",
    "non_environment",
    "uncertain",
]


def _nid(prefix: str = "sr_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReconstructionCamera(BaseModel):
    orientation: str = "forward"
    heightEstimateM: float | None = None
    vanishingPoint: tuple[float, float] | None = None
    evidence: EvidenceKind = "inferred"
    confidence: float = 0.0


class FeatureRecord(BaseModel):
    id: str = Field(default_factory=lambda: _nid("feat_"))
    type: str = ""
    wall: str = ""
    distanceRatio: float = 0.0
    cellColumn: int | None = None
    cellRow: int | None = None
    evidence: EvidenceKind = "inferred"
    confidence: float = 0.0
    userIntentLabel: str = ""
    notes: str = ""


class UnknownRegion(BaseModel):
    id: str = Field(default_factory=lambda: _nid("unk_"))
    reason: str = ""
    evidence: EvidenceKind = "unknown"
    notes: str = ""


class ScaleRecord(BaseModel):
    """Anchored meters vs relative geometry mapped onto 1 cell = 1 provisional meter."""

    mode: ScaleMode = "provisional"
    evidenceKind: EvidenceKind = "inferred"
    confidence: float = 0.2
    anchorKind: str = ""
    anchorNote: str = ""
    metersPerCell: float = 1.0


class ReconstructionLayout(BaseModel):
    environmentType: EnvironmentKind = "uncertain"
    widthCells: int = 0
    depthCells: int = 0
    widthProvisionalM: float = 0.0
    depthProvisionalM: float = 0.0
    sourceAspect: float = 0.0
    evidence: EvidenceKind = "inferred"
    confidence: float = 0.0


class GeometrySanityResult(BaseModel):
    ok: bool = False
    errors: list[str] = Field(default_factory=list)


class SpatialReconstructionPacket(BaseModel):
    schemaVersion: str = PACKET_SCHEMA
    packetId: str = Field(default_factory=_nid)
    projectId: str = ""
    executionId: str = ""
    mapId: str = ""
    sourceAssetIds: list[str] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    environmentType: EnvironmentKind = "uncertain"
    camera: ReconstructionCamera = Field(default_factory=ReconstructionCamera)
    layout: ReconstructionLayout = Field(default_factory=ReconstructionLayout)
    scale: ScaleRecord = Field(default_factory=ScaleRecord)
    features: list[FeatureRecord] = Field(default_factory=list)
    unknownRegions: list[UnknownRegion] = Field(default_factory=list)
    userIntentSummary: str = ""
    sceneIntent: dict[str, Any] = Field(default_factory=dict)
    perceptionNotes: str = ""
    guideAssetId: str = ""
    depthAssetId: str = ""
    sanity: GeometrySanityResult = Field(default_factory=GeometrySanityResult)
    assignedToMap: bool = False
    createdAt: str = Field(default_factory=_now)
    updatedAt: str = Field(default_factory=_now)
