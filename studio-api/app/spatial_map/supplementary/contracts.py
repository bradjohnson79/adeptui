"""Observed vs inferred spatial-reference contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

SUPPLEMENTARY_PURPOSE = "environment_supplementary_view"
SUPPLEMENTARY_TASK_CLASS = "ENVIRONMENT_SUPPLEMENTARY_VIEW"

EvidenceClass = Literal["OBSERVED", "INFERRED"]
ReferenceSource = Literal["USER", "QWEN_IMAGE_EDIT"]
ViewSlot = Literal["A", "B"]
ViewStatus = Literal["EMPTY", "GENERATING", "VALIDATING", "READY", "FAILED", "REJECTED"]
CameraRole = Literal[
    "REVERSE",
    "LEFT_SIDE",
    "RIGHT_SIDE",
    "REAR",
    "OPPOSITE_CORNER",
    "ELEVATED",
    "ROOM_FACING",
    "CORRIDOR_FACING",
]
GateVerdict = Literal["PASS", "PASS_WITH_LOW_CONFIDENCE", "FAIL", "FAIL_NO_INFORMATION_GAIN"]
FactKind = Literal["OBSERVED", "INFERRED_SUPPORTED", "CONFLICTED", "UNKNOWN"]

CAMERA_ROLES: tuple[CameraRole, ...] = (
    "REVERSE",
    "LEFT_SIDE",
    "RIGHT_SIDE",
    "REAR",
    "OPPOSITE_CORNER",
    "ELEVATED",
    "ROOM_FACING",
    "CORRIDOR_FACING",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nid(prefix: str = "sref_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


class SpatialReferenceRecord(BaseModel):
    id: str = Field(default_factory=_nid)
    slot: ViewSlot | Literal["MASTER"] = "MASTER"
    assetId: str = ""
    referenceRole: str = "PRIMARY_ENVIRONMENT"
    evidenceClass: EvidenceClass = "OBSERVED"
    source: ReferenceSource = "USER"
    cameraRole: CameraRole | None = None
    sourceAssetId: str = ""
    generationEngine: str = ""
    confidence: float = 1.0
    approvedForSpatialReasoning: bool = False
    status: ViewStatus = "READY"
    prompt: str = ""
    promptId: str = ""
    workflowKey: str = ""
    gateVerdict: GateVerdict | None = None
    gateReasons: list[str] = Field(default_factory=list)
    timings: dict[str, Any] = Field(default_factory=dict)
    jobId: str = ""
    notGeometryEvidence: bool = False
    createdAt: str = Field(default_factory=_now)
    updatedAt: str = Field(default_factory=_now)

    @model_validator(mode="after")
    def _observed_authority(self) -> "SpatialReferenceRecord":
        if self.evidenceClass == "OBSERVED":
            if self.source == "QWEN_IMAGE_EDIT":
                raise ValueError("Qwen-generated views cannot be OBSERVED.")
            if self.slot in {"A", "B"}:
                raise ValueError("Supplementary slots cannot be OBSERVED.")
        if self.evidenceClass == "INFERRED" and self.source == "USER":
            raise ValueError("User master cannot be tagged INFERRED.")
        return self


class ConfidenceFact(BaseModel):
    kind: FactKind
    text: str
    sources: list[str] = Field(default_factory=list)


class ConfidenceSummary(BaseModel):
    observed: list[str] = Field(default_factory=list)
    inferredSupported: list[str] = Field(default_factory=list)
    conflicted: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SupplementaryState(BaseModel):
    masterAssetId: str = ""
    viewA: SpatialReferenceRecord | None = None
    viewB: SpatialReferenceRecord | None = None
    selectedRoleA: CameraRole | None = None
    selectedRoleB: CameraRole | None = None
    inFlightSlot: ViewSlot | None = None
    setGateVerdict: GateVerdict | None = None
    setGateReasons: list[str] = Field(default_factory=list)
    confidence: ConfidenceSummary = Field(default_factory=ConfidenceSummary)
    contactSheetAssetId: str = ""
    ownerReviewStripPath: str = ""
    notGeometryEvidence: bool = True
    updatedAt: str = Field(default_factory=_now)


def observed_asset_ids(
    *,
    master_asset_id: str,
    references: list[SpatialReferenceRecord] | None = None,
    source_asset_ids: list[str] | None = None,
) -> list[str]:
    """Observed-only IDs. Inferred Qwen views never appear here."""
    inferred = {
        str(ref.assetId or "").strip()
        for ref in references or []
        if ref.evidenceClass == "INFERRED" and str(ref.assetId or "").strip()
    }
    ids: list[str] = []
    master = (master_asset_id or "").strip()
    if master and master not in inferred:
        ids.append(master)
    for item in source_asset_ids or []:
        value = str(item or "").strip()
        if value and value not in ids and value not in inferred:
            ids.append(value)
    for ref in references or []:
        if ref.evidenceClass != "OBSERVED":
            continue
        value = str(ref.assetId or "").strip()
        if value and value not in ids and value not in inferred:
            ids.append(value)
    return ids


def inferred_cannot_count_as_observed(ref: SpatialReferenceRecord) -> bool:
    return not (ref.evidenceClass == "INFERRED" and ref.slot in {"A", "B"})
