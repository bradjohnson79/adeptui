"""Pydantic schemas for Wave 5 continuity API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ContinuityPolicyOut(BaseModel):
    continuityPolicySchemaVersion: int = 1
    projectId: str
    enabled: bool = False
    preflightMode: Literal["off", "warn", "required"] = "off"
    evaluationMode: Literal["manual", "automatic"] = "manual"
    productionMasterRequiresDecision: bool = False
    criticalSeverityBehavior: Literal["warn", "block"] = "warn"
    defaultEvaluatorKey: str = "continuity.rule_based_v1"


class ContinuityPolicyUpdate(BaseModel):
    enabled: bool | None = None
    preflightMode: Literal["off", "warn", "required"] | None = None
    evaluationMode: Literal["manual", "automatic"] | None = None
    productionMasterRequiresDecision: bool | None = None
    criticalSeverityBehavior: Literal["warn", "block"] | None = None
    defaultEvaluatorKey: str | None = None


class VisualIdentityCreate(BaseModel):
    identityType: str = "character"
    canonicalName: str
    displayName: str | None = None
    description: str | None = None
    characterProfileId: str | None = None
    bibleEntityStableId: str | None = None
    createdBy: str = "user"


class VisualIdentityUpdate(BaseModel):
    displayName: str | None = None
    description: str | None = None
    status: str | None = None
    activeVersionId: str | None = None
    productionVersionId: str | None = None
    characterProfileId: str | None = None
    bibleEntityStableId: str | None = None


class IdentityVersionCreate(BaseModel):
    label: str = "Version"
    summary: str | None = None
    traits: dict[str, Any] = Field(default_factory=dict)
    createdBy: str = "user"


class IdentityVersionUpdate(BaseModel):
    """Editing an approved version must create a draft child — never mutate approved in place."""

    label: str | None = None
    summary: str | None = None
    traits: dict[str, Any] | None = None
    createdBy: str = "user"


class IdentityVariantCreate(BaseModel):
    variantType: str = "custom"
    name: str
    description: str | None = None
    traitOverrides: dict[str, Any] = Field(default_factory=dict)
    lockedTraits: list[str] = Field(default_factory=list)
    createdBy: str = "user"


class ReferenceCreate(BaseModel):
    identityId: str
    identityVersionId: str
    assetId: str
    roles: list[str] = Field(default_factory=list)
    variantId: str | None = None
    notes: str | None = None
    createdBy: str = "user"


class ReferenceUpdate(BaseModel):
    roles: list[str] | None = None
    notes: str | None = None
    qualityStatus: str | None = None


class ConstraintCreate(BaseModel):
    identityId: str
    identityVersionId: str
    dimension: str
    policy: str = "prefer"
    severity: str = "minor"
    expectedValue: Any = None
    tolerance: Any = None
    userDescription: str = ""
    variantId: str | None = None
    enabled: bool = True


class BindingRequest(BaseModel):
    identityId: str
    identityVersionId: str | None = None
    variantIds: list[str] = Field(default_factory=list)
    expectedScreenRole: str | None = None
    expectedVisibility: str = "fully_visible"
    expectedView: dict[str, Any] | None = None
    requiredRoles: list[str] = Field(default_factory=list)
    shotType: str | None = None


class PreflightRequest(BaseModel):
    requestId: str | None = None
    bindings: list[BindingRequest] = Field(default_factory=list)
    workflowKey: str | None = None
    workflowSupportsReferences: bool = True
    maxReferences: int = 6
    requireContinuity: bool = False


class EvaluateRequest(BaseModel):
    assetId: str
    packetId: str
    evaluatorKey: str | None = None


class ReviewRequest(BaseModel):
    decision: str
    reason: str = ""
    notes: str = ""
    reviewer: str = "user"
    correctionId: str | None = None


class CorrectionProposeRequest(BaseModel):
    sourceAssetId: str
    packetId: str | None = None
    evaluationId: str | None = None
    issueIds: list[str] = Field(default_factory=list)
    prompt: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    createdBy: str = "user"


class CorrectionEnqueueRequest(BaseModel):
    approvedBy: str = "user"
