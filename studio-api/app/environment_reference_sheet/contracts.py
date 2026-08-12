"""Versioned contracts for Co-Director Environment Reference Sheets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ERS_SCHEMA_VERSION = 1

ERSStatus = Literal[
    "draft",
    "spatial_pending",
    "views_pending",
    "continuity_review",
    "composition_ready",
    "registered",
    "approved",
    "blocked",
]
ERSReadiness = Literal["ready", "warning", "blocked"]
ERSViewDirection = Literal["north", "east", "south", "west"]
ERSViewStatus = Literal["missing", "planned", "queued", "ready", "approved", "blocked"]
ERSRepairStrategy = Literal["preserve_approved_views", "repair_missing_view", "rebuild_unapproved_views"]
ERSThreeDTruthLabel = Literal["illustrative", "isometric", "derived", "true"]
ERSContinuitySeverity = Literal["info", "warning", "error"]
ERSExportKind = Literal["png", "pdf", "offline_html"]
ERSExportStatus = Literal["not_created", "created", "failed"]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ERSProvenanceRecord(BaseModel):
    createdAt: str = Field(default_factory=utc_now)
    actor: str = "system"
    source: str = "environment_reference_sheet"
    note: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ERSApprovalRequirement(BaseModel):
    approvalId: str = Field(default_factory=lambda: str(uuid4()))
    kind: str
    status: Literal["not-required", "required", "approved", "blocked"] = "not-required"
    reason: str | None = None
    creatorTip: str | None = None
    approvedBy: str | None = None
    approvedAt: str | None = None


class ERSStage(BaseModel):
    stageKey: str
    label: str
    required: bool = True
    status: Literal["pending", "ready", "blocked", "complete", "skipped"] = "pending"
    summary: str | None = None


class EnvironmentProfile(BaseModel):
    environmentName: str
    description: str
    environmentType: str = "environment"
    storyPurpose: str = ""
    visualDNA: list[str] = Field(default_factory=list)
    atmosphere: list[str] = Field(default_factory=list)
    timeOfDay: str = ""
    weather: str = ""
    scale: str = ""
    architecture: str = ""
    materials: list[str] = Field(default_factory=list)
    colorPalette: list[str] = Field(default_factory=list)
    lightingNotes: list[str] = Field(default_factory=list)
    continuityLocks: list[str] = Field(default_factory=list)
    creatorNotes: str | None = None


class SpatialMapReference(BaseModel):
    mapId: str
    mapVersion: str | None = None
    sceneId: str | None = None
    locationId: str | None = None
    northLockDirection: ERSViewDirection = "north"
    referenceBundleSummary: str = ""
    warnings: list[str] = Field(default_factory=list)
    directionalPrompts: dict[str, str] = Field(default_factory=dict)


class DirectionalViewRecord(BaseModel):
    direction: ERSViewDirection
    title: str
    prompt: str
    sourceDirection: str
    imagePipelinePlanId: str | None = None
    candidateGroupId: str | None = None
    selectedCandidateId: str | None = None
    approvedAssetId: str | None = None
    status: ERSViewStatus = "missing"
    continuityNotes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: ERSProvenanceRecord = Field(default_factory=ERSProvenanceRecord)


class OptionalThreeDRecord(BaseModel):
    truthLabel: ERSThreeDTruthLabel
    status: Literal["not_requested", "linked", "blocked"] = "not_requested"
    assetId: str | None = None
    note: str = ""


class ContinuityFinding(BaseModel):
    findingId: str = Field(default_factory=lambda: str(uuid4()))
    severity: ERSContinuitySeverity = "info"
    code: str
    title: str
    message: str
    affectedDirections: list[ERSViewDirection] = Field(default_factory=list)
    recommendedAction: str | None = None


class ContinuityValidationReport(BaseModel):
    status: ERSReadiness = "warning"
    summary: str = ""
    findings: list[ContinuityFinding] = Field(default_factory=list)
    repairStrategy: ERSRepairStrategy = "preserve_approved_views"
    preservedDirections: list[ERSViewDirection] = Field(default_factory=list)
    evaluatedAt: str = Field(default_factory=utc_now)
    note: str | None = None


class ERSCompositionRecord(BaseModel):
    sheetTitle: str
    subtitle: str = ""
    heroSummary: str = ""
    profileHighlights: list[str] = Field(default_factory=list)
    continuitySummary: str = ""
    renderedAssetIds: dict[str, str] = Field(default_factory=dict)
    renderedFiles: dict[str, str] = Field(default_factory=dict)
    lastRenderedAt: str | None = None


class ERSProjectRegistration(BaseModel):
    locationStableId: str | None = None
    locationDisplayName: str | None = None
    libraryFolderPath: str | None = None
    linkedSceneIds: list[str] = Field(default_factory=list)
    projectMemoryNotes: list[str] = Field(default_factory=list)
    registeredAt: str | None = None


class ERSExportRecord(BaseModel):
    exportKind: ERSExportKind
    status: ERSExportStatus = "not_created"
    assetId: str | None = None
    filePath: str | None = None
    archiveName: str | None = None
    message: str = ""
    createdAt: str | None = None


class ERSRevisionLaw(BaseModel):
    preserveApprovedDirections: bool = True
    requireNorthLockBeforeViews: bool = True
    requireApprovalForMutation: bool = True
    revisionNote: str = (
        "Approved directions stay protected during repair unless the creator explicitly authorizes a rebuild."
    )


class ERSCreationPlan(BaseModel):
    summary: str
    creatorPreview: str
    readiness: ERSReadiness = "warning"
    readinessReasons: list[str] = Field(default_factory=list)
    stages: list[ERSStage] = Field(default_factory=list)
    approvalRequirements: list[ERSApprovalRequirement] = Field(default_factory=list)


class EnvironmentReferenceSheet(BaseModel):
    schemaVersion: int = ERS_SCHEMA_VERSION
    sheetId: str = Field(default_factory=lambda: str(uuid4()))
    projectId: str
    sceneId: str | None = None
    name: str
    description: str
    status: ERSStatus = "draft"
    createdAt: str = Field(default_factory=utc_now)
    updatedAt: str = Field(default_factory=utc_now)
    profile: EnvironmentProfile
    spatialMap: SpatialMapReference | None = None
    directionalViews: list[DirectionalViewRecord] = Field(default_factory=list)
    optionalThreeD: OptionalThreeDRecord | None = None
    continuity: ContinuityValidationReport = Field(default_factory=ContinuityValidationReport)
    creationPlan: ERSCreationPlan
    composition: ERSCompositionRecord
    registration: ERSProjectRegistration = Field(default_factory=ERSProjectRegistration)
    exports: list[ERSExportRecord] = Field(default_factory=list)
    revisionLaw: ERSRevisionLaw = Field(default_factory=ERSRevisionLaw)
    provenance: ERSProvenanceRecord = Field(default_factory=ERSProvenanceRecord)
