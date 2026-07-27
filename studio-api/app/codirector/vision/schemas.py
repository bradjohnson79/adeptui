"""Pydantic schemas for Co-Director M2.5 vision validation (wire + domain)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SESSION_STATUSES = (
    "pending",
    "running",
    "completed",
    "failed",
    "approved",
    "rejected",
)
SessionStatus = Literal["pending", "running", "completed", "failed", "approved", "rejected"]

FindingStatus = Literal["pass", "warn", "fail", "inconclusive", "skipped"]
Severity = Literal["info", "warning", "error", "blocking"]
ScoreBand = Literal["approve", "review", "corrections_required", "reject"]

AssetValidationLifecycle = Literal[
    "not_requested",
    "pending",
    "running",
    "completed",
    "failed",
    "approved",
    "rejected",
]
AssetValidationResult = Literal["unreviewed", "passed", "warnings", "failed", "rejected"]
ProductionApproval = Literal["none", "approved", "rejected"]


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Severity = "warning"
    correctable: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class ValidatorFinding(BaseModel):
    validatorId: str
    status: FindingStatus
    score: float = 0.0
    confidence: float = 0.0
    severity: Severity = "info"
    correctable: bool = True
    blocking: bool = False
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    bindingId: Optional[str] = None
    role: Optional[str] = None


class ValidationReport(BaseModel):
    reportId: str
    sessionId: str
    projectId: str
    overallScore: float
    passed: bool
    band: ScoreBand
    strengths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    weights: dict[str, float] = Field(default_factory=dict)
    findings: list[ValidatorFinding] = Field(default_factory=list)
    blockingFailures: list[str] = Field(default_factory=list)
    provider: str = "local"
    createdAt: str = ""


class ValidationSession(BaseModel):
    sessionId: str
    projectId: str
    assetId: Optional[str] = None
    planId: Optional[str] = None
    sceneId: Optional[str] = None
    referenceAssetId: Optional[str] = None
    provider: str = "local"
    status: SessionStatus = "pending"
    validatorSet: list[str] = Field(default_factory=list)
    reportId: Optional[str] = None
    comparisonId: Optional[str] = None
    errorMessage: Optional[str] = None
    requirements: dict[str, Any] = Field(default_factory=dict)
    createdAt: str = ""
    updatedAt: str = ""


class ValidationApproval(BaseModel):
    approvalId: str
    sessionId: str
    reportId: Optional[str] = None
    projectId: str
    decision: Literal["approved", "rejected", "override_approve", "override_reject"]
    reviewer: str = "user"
    notes: str = ""
    override: bool = False
    createdAt: str = ""


class ValidationComparison(BaseModel):
    comparisonId: str
    sessionId: str
    projectId: str
    referenceAssetId: Optional[str] = None
    generatedAssetId: Optional[str] = None
    referenceMeta: dict[str, Any] = Field(default_factory=dict)
    generatedMeta: dict[str, Any] = Field(default_factory=dict)
    differences: list[dict[str, Any]] = Field(default_factory=list)
    createdAt: str = ""


class CorrectionProposalLink(BaseModel):
    linkId: str
    sessionId: str
    reportId: Optional[str] = None
    projectId: str
    proposalId: str
    kind: str = "vision_correction"
    createdAt: str = ""


class ReferenceSetBindingSpec(BaseModel):
    bindingId: str
    role: str
    influence: str = "moderate"
    assetId: str


class ReferenceSetSpec(BaseModel):
    id: str
    version: int
    bindings: list[ReferenceSetBindingSpec] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    projectId: str
    assetId: Optional[str] = None
    planId: Optional[str] = None
    sceneId: Optional[str] = None
    referenceAssetId: Optional[str] = None
    referenceSet: Optional[ReferenceSetSpec] = None
    provider: Literal["mock", "local"] = "local"
    fixtureProfile: Optional[str] = None
    validators: Optional[list[str]] = None


class ApproveRejectRequest(BaseModel):
    projectId: str
    sessionId: str
    reviewer: str = "user"
    notes: str = ""
    override: bool = False
    # B19 / M3.0d: required when override=true for reject-band approvals.
    overrideReason: str = ""
    linkToBible: bool = True


class CorrectionRequest(BaseModel):
    projectId: str
    sessionId: str
    findingValidatorIds: list[str] = Field(default_factory=list)
    notes: str = ""
    createdBy: str = "user"
