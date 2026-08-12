"""Wave 4 canonical production plan schemas."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

PLAN_SCHEMA_VERSION = "4.1.0"

ProductionPlanState = Literal[
    "draft",
    "proposed",
    "awaiting_approval",
    "approved",
    "ready",
    "blocked",
    "paused",
    "in_progress",
    "completed",
    "failed",
    "cancelled",
    "archived",
]

ProductionPlanStepState = Literal[
    "pending",
    "ready",
    "blocked",
    "awaiting_approval",
    "deferred",
    "unsupported",
    "paused",
    "in_progress",
    "completed",
    "failed",
    "skipped",
    "cancelled",
]

StepCategory = Literal[
    "research",
    "script",
    "scene",
    "character",
    "bible",
    "asset",
    "continuity",
    "image",
    "video",
    "audio",
    "director",
    "editor",
    "subtitle",
    "approval",
    "review",
    "system",
]

ExecutionAvailability = Literal[
    "available",
    "deferred",
    "unsupported",
    "unconfigured",
    "permission_required",
]

PlanReadinessLevel = Literal[
    "ready",
    "partially_ready",
    "blocked",
    "deferred",
    "unsupported",
]


class ActorRef(BaseModel):
    actorType: Literal["user", "codirector", "system"] = "codirector"
    actorId: Optional[str] = None


class PlanSource(BaseModel):
    type: Literal["conversation", "manual", "proposal", "director", "system", "intelligence"] = "conversation"
    sourceId: Optional[str] = None


class PlanInputReference(BaseModel):
    kind: str
    id: Optional[str] = None
    label: Optional[str] = None


class PlanExpectedOutput(BaseModel):
    kind: str
    description: str = ""


class PlanOutputReference(BaseModel):
    kind: str
    id: Optional[str] = None
    label: Optional[str] = None


class PlanWarning(BaseModel):
    code: str
    message: str
    section: Optional[str] = None


class StepFailure(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ProductionPlanStep(BaseModel):
    stepId: str
    planId: str = ""
    order: int = 0
    title: str
    description: str = ""
    category: StepCategory = "system"
    state: ProductionPlanStepState = "pending"
    dependsOn: list[str] = Field(default_factory=list)
    blockedBy: list[str] = Field(default_factory=list)
    requiresApproval: bool = True
    approvalRequirementIds: list[str] = Field(default_factory=list)
    requiredCapabilities: list[str] = Field(default_factory=list)
    requiredInputs: list[PlanInputReference] = Field(default_factory=list)
    expectedOutputs: list[PlanExpectedOutput] = Field(default_factory=list)
    assignedSpecialist: Optional[str] = None
    proposedToolId: Optional[str] = None
    # Wave 6P: bind step → ProductionIntent / tool apply arguments
    toolArguments: dict[str, Any] = Field(default_factory=dict)
    sceneId: Optional[str] = None
    shotId: Optional[str] = None
    intentId: Optional[str] = None
    jobId: Optional[str] = None
    executionAvailability: ExecutionAvailability = "deferred"
    createdAt: str = ""
    updatedAt: str = ""
    startedAt: Optional[str] = None
    completedAt: Optional[str] = None
    failedAt: Optional[str] = None
    failure: Optional[StepFailure] = None


class ProductionPlanBlocker(BaseModel):
    blockerId: str
    planId: str = ""
    stepId: Optional[str] = None
    category: str = "system"
    severity: Literal["info", "warning", "blocking"] = "blocking"
    title: str
    description: str = ""
    sourceType: str = "system"
    sourceId: Optional[str] = None
    resolutionType: str = "later_wave"
    recommendedAction: Optional[str] = None
    state: Literal["open", "resolved", "dismissed"] = "open"
    createdAt: str = ""
    resolvedAt: Optional[str] = None


class PlanApprovalRequirement(BaseModel):
    requirementId: str
    planId: str = ""
    stepId: Optional[str] = None
    approvalType: str = "plan_acceptance"
    status: Literal["required", "pending", "approved", "rejected", "expired", "not_applicable"] = "required"
    reason: str = ""
    scope: str = "plan"
    approvedBy: Optional[str] = None
    approvedAt: Optional[str] = None


class CapabilityEntry(BaseModel):
    capabilityId: str
    status: str = "deferred"
    available: bool = False
    reason: Optional[str] = None


class PlanCapabilitySnapshot(BaseModel):
    capturedAt: str = ""
    readiness: PlanReadinessLevel = "deferred"
    capabilities: list[CapabilityEntry] = Field(default_factory=list)


class PlanReadinessReport(BaseModel):
    snapshotReadiness: PlanReadinessLevel = "deferred"
    currentReadiness: PlanReadinessLevel = "deferred"
    changedCapabilities: list[str] = Field(default_factory=list)
    snapshot: PlanCapabilitySnapshot = Field(default_factory=PlanCapabilitySnapshot)
    current: PlanCapabilitySnapshot = Field(default_factory=PlanCapabilitySnapshot)
    requiresRefresh: bool = False


class ProductionPlan(BaseModel):
    schemaVersion: str = PLAN_SCHEMA_VERSION
    planId: str
    projectId: str
    conversationId: Optional[str] = None
    title: str
    objective: str = ""
    description: str = ""
    state: ProductionPlanState = "draft"
    version: int = 1
    createdBy: ActorRef = Field(default_factory=ActorRef)
    source: PlanSource = Field(default_factory=PlanSource)
    activeStepId: Optional[str] = None
    steps: list[ProductionPlanStep] = Field(default_factory=list)
    blockers: list[ProductionPlanBlocker] = Field(default_factory=list)
    approvalRequirements: list[PlanApprovalRequirement] = Field(default_factory=list)
    outputs: list[PlanOutputReference] = Field(default_factory=list)
    warnings: list[PlanWarning] = Field(default_factory=list)
    capabilitySnapshot: PlanCapabilitySnapshot = Field(default_factory=PlanCapabilitySnapshot)
    createdAt: str = ""
    updatedAt: str = ""
    pausedAt: Optional[str] = None
    resumedAt: Optional[str] = None
    cancelledAt: Optional[str] = None
    archivedAt: Optional[str] = None
    completedAt: Optional[str] = None
    revisionReason: Optional[str] = None
    parentVersionId: Optional[str] = None
    playbookId: Optional[str] = None
    requestId: Optional[str] = None
    unapproved: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanValidationIssue(BaseModel):
    code: str
    message: str
    stepId: Optional[str] = None
    path: Optional[str] = None


class PlanValidationResult(BaseModel):
    valid: bool
    status: Literal["valid", "valid_with_warnings", "invalid"]
    errors: list[PlanValidationIssue] = Field(default_factory=list)
    warnings: list[PlanValidationIssue] = Field(default_factory=list)
    readiness: PlanReadinessLevel = "deferred"


class DependencyValidationResult(BaseModel):
    valid: bool
    cycles: list[list[str]] = Field(default_factory=list)
    missingDependencies: list[str] = Field(default_factory=list)
    selfDependencies: list[str] = Field(default_factory=list)
    unreachableSteps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PlanEvent(BaseModel):
    eventId: str
    planId: str
    projectId: str
    planVersion: int
    eventType: str
    actorType: Literal["user", "codirector", "system"] = "system"
    actorId: Optional[str] = None
    requestId: str = ""
    summary: str = ""
    changes: dict[str, Any] = Field(default_factory=dict)
    createdAt: str = ""


class PlanCommandResult(BaseModel):
    plan: ProductionPlan
    event: Optional[PlanEvent] = None
    duplicated: bool = False
    validation: Optional[PlanValidationResult] = None
