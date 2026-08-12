"""Frozen foundation contracts for Co-Director Phases 1.5–6.

Preserve-first: aliases and thin extensions over existing conversation /
intelligence / plans / tools schemas. Subagents must not invent competing types.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Re-export preserve-first types for a single import surface.
from ..conversation.schemas import (  # noqa: F401
    ConversationPlan,
    KnowledgeState,
    ProjectDirectorState,
    ProjectIntelligenceSnapshot,
    WikiCandidate,
)
from ..intelligence.schemas import (  # noqa: F401
    ContextPackage,
    IntentClassification,
    SpecialistFinding,
    SynthesisResult,
)
from ..plans.schemas import (  # noqa: F401
    ProductionPlan,
    ProductionPlanBlocker,
    ProductionPlanStep,
)

# Aliases — ProductionTask / ProjectBlocker map to canonical plan types.
ProductionTask = ProductionPlanStep
ProjectBlocker = ProductionPlanBlocker

# ---------------------------------------------------------------------------
# Creative State (alias view over stage/substate)
# ---------------------------------------------------------------------------


class CreativeState(BaseModel):
    """Stage/substate view used by foundation routing."""

    stage: str = "Project Creation"
    substate: Optional[str] = None
    revision: int = 0


# ---------------------------------------------------------------------------
# Phase 1.5 — Creative Knowledge Framework (craft doctrine, not project Wiki)
# ---------------------------------------------------------------------------


class KnowledgeFrame(BaseModel):
    """A single reusable craft principle or pattern inside a KnowledgePack."""

    frameId: str
    title: str
    summary: str
    principles: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    antiPatterns: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)


class KnowledgePack(BaseModel):
    """Versioned craft knowledge unit consulted by every specialist."""

    packId: str
    title: str
    version: str = "1.0"
    domainTags: list[str] = Field(default_factory=list)
    frames: list[KnowledgeFrame] = Field(default_factory=list)
    relatedPackIds: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Specialist envelope (extends SpecialistFinding without replacing it)
# ---------------------------------------------------------------------------


class ContinuityFlag(BaseModel):
    flagId: str
    severity: Literal["info", "warning", "blocking"] = "warning"
    summary: str
    evidenceRefs: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    text: str
    priority: Literal["low", "medium", "high"] = "medium"
    knowledgeRefs: list[str] = Field(default_factory=list)


class SpecialistRequest(BaseModel):
    """Thin request envelope for foundation specialists."""

    specialistId: str
    projectId: str
    userMessage: str
    intent: Optional[str] = None
    context: Optional[ContextPackage] = None
    knowledgeRefs: list[str] = Field(default_factory=list)
    domainProfileIds: list[str] = Field(default_factory=list)
    creativeStage: Optional[str] = None
    creativeSubstate: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpecialistResult(SpecialistFinding):
    """Compatible extension of SpecialistFinding for foundation specialists."""

    findings: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    continuityFlags: list[ContinuityFlag] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    evidenceRefs: list[str] = Field(default_factory=list)
    knowledgeRefs: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Creative Director (pre-synthesis editor-in-chief)
# ---------------------------------------------------------------------------


class CreativeDirectorReview(BaseModel):
    """Critique of a specialist bundle before Synthesis."""

    reviewId: str
    projectId: str
    alignedWithVision: bool = True
    contradictions: list[str] = Field(default_factory=list)
    practicalityNotes: list[str] = Field(default_factory=list)
    complexityWarnings: list[str] = Field(default_factory=list)
    profileFitNotes: list[str] = Field(default_factory=list)
    overloadRisk: Literal["low", "medium", "high"] = "low"
    keepSpecialistIds: list[str] = Field(default_factory=list)
    dropSpecialistIds: list[str] = Field(default_factory=list)
    prioritizedRecommendations: list[str] = Field(default_factory=list)
    maxQuestions: int = 1
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Approvals / activity / receipts (facades over existing systems)
# ---------------------------------------------------------------------------


class ApprovalRequest(BaseModel):
    """Facade over tool proposals / plan approval requirements."""

    approvalId: str
    projectId: str
    kind: Literal["tool_proposal", "plan_requirement", "workflow_step", "other"] = "other"
    title: str
    description: str = ""
    sourceType: str = "foundation"
    sourceId: Optional[str] = None
    requiresCreator: bool = True
    status: Literal["pending", "approved", "rejected", "cancelled"] = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActivityEvent(BaseModel):
    """Backend activity DTO aligned with Co-Director UI activity vocabulary."""

    eventId: str
    projectId: str
    type: str
    stage: Optional[str] = None
    state: Literal["queued", "running", "succeeded", "failed", "cancelled", "info"] = "info"
    title: str
    detail: str = ""
    timestamp: Optional[str] = None
    toolId: Optional[str] = None
    workflowId: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolReceipt(BaseModel):
    """Alias-shaped receipt combining invocation + execution evidence."""

    receiptId: str
    projectId: str
    toolId: str
    status: Literal["proposed", "approved", "executed", "failed", "rejected"] = "proposed"
    idempotencyKey: Optional[str] = None
    summary: str = ""
    error: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Autonomous workflows (Phase 5)
# ---------------------------------------------------------------------------


class WorkflowBudget(BaseModel):
    maxSteps: int = 8
    maxRetries: int = 2
    maxDurationSeconds: int = 120
    allowCostlyGeneration: bool = False
    allowDestructive: bool = False


class StopCondition(BaseModel):
    kind: Literal["max_steps", "failure", "approval_required", "budget", "creator_cancel"]
    detail: str = ""


class WorkflowStep(BaseModel):
    stepId: str
    title: str
    toolId: Optional[str] = None
    state: Literal[
        "not_started",
        "collecting_requirements",
        "blocked",
        "ready",
        "in_progress",
        "awaiting_approval",
        "complete",
        "failed",
        "superseded",
    ] = "not_started"
    requiresApproval: bool = False
    idempotencyKey: Optional[str] = None
    dependsOn: list[str] = Field(default_factory=list)


class AutonomousWorkflow(BaseModel):
    workflowId: str
    projectId: str
    objective: str
    steps: list[WorkflowStep] = Field(default_factory=list)
    allowedTools: list[str] = Field(default_factory=list)
    approvalPolicy: str = "creator_required_for_mutations"
    budget: WorkflowBudget = Field(default_factory=WorkflowBudget)
    stopConditions: list[StopCondition] = Field(default_factory=list)
    currentState: Literal[
        "draft",
        "ready",
        "running",
        "awaiting_approval",
        "stopped",
        "failed",
        "complete",
    ] = "draft"
    receipts: list[ToolReceipt] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Domain profiles (Phase 6)
# ---------------------------------------------------------------------------


class DomainProfile(BaseModel):
    """Production-format profile keyed to projectTypes slugs."""

    profileId: str
    displayName: str
    projectTypeSlugs: list[str] = Field(default_factory=list)
    productionStages: list[str] = Field(default_factory=list)
    specialistPriorities: list[str] = Field(default_factory=list)
    knowledgePackIds: list[str] = Field(default_factory=list)
    commonDeliverables: list[str] = Field(default_factory=list)
    approvalPoints: list[str] = Field(default_factory=list)
    qualityChecks: list[str] = Field(default_factory=list)
    commonRisks: list[str] = Field(default_factory=list)
    terminology: dict[str, str] = Field(default_factory=dict)
    defaultPlanTemplate: list[str] = Field(default_factory=list)
    recommendedWorkflows: list[str] = Field(default_factory=list)


# Collaboration modes (Phase 4)
CollaborationMode = Literal[
    "explore",
    "critique",
    "compare",
    "refine",
    "decide",
    "review",
    "execute",
    "teach",
]


class CreatorPreference(BaseModel):
    preferenceId: str
    projectId: str
    key: str
    value: str
    visible: bool = True
    editable: bool = True
    forgettable: bool = True
    source: Literal["explicit", "inferred"] = "explicit"
