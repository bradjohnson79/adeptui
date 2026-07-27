"""Pydantic models for Co-Director M2.4 intelligence."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

CONTEXT_PACKAGE_VERSION = "context-package-v1"
PRODUCTION_PLAN_VERSION = "production-plan-v1"

ProductionStage = Literal[
    "development",
    "writing",
    "preproduction",
    "production",
    "postproduction",
    "delivery",
    "project_management",
]

IntentKind = Literal[
    "answer_question",
    "develop_concept",
    "write_story",
    "revise_story",
    "create_character",
    "revise_character",
    "design_location",
    "plan_scene",
    "write_scene",
    "revise_dialogue",
    "create_shot_list",
    "create_storyboard",
    "prepare_image_generation",
    "prepare_video_generation",
    "review_asset",
    "review_continuity",
    "assemble_sequence",
    "plan_audio",
    "plan_vfx",
    "manage_production",
    "update_production_bible",
    "execute_project_action",
    "production_intelligence",
    "unknown",
]

AuthorityLevel = Literal["locked", "approved", "draft", "unverified", "inferred"]
SourceType = Literal[
    "production_bible",
    "user_message",
    "approved_decision",
    "locked_canon",
    "scene_data",
    "asset_metadata",
    "inference",
]


class ContextFact(BaseModel):
    key: str
    value: Any
    sourceType: SourceType = "production_bible"
    sourceId: Optional[str] = None
    authority: AuthorityLevel = "approved"
    category: str = "general"


class ProposedToolAction(BaseModel):
    toolId: str
    purpose: str
    requiresApproval: bool = True
    arguments: dict[str, Any] = Field(default_factory=dict)


class BibleReference(BaseModel):
    entityType: str
    entityId: str
    reason: str = ""


class SpecialistFinding(BaseModel):
    specialistId: str
    summary: str
    recommendation: str
    contentDropped: bool = False
    requirements: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    blockingIssues: list[str] = Field(default_factory=list)
    optionalImprovements: list[str] = Field(default_factory=list)
    productionBibleReferences: list[BibleReference] = Field(default_factory=list)
    proposedToolActions: list[ProposedToolAction] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    promptVersion: Optional[str] = None
    modelId: Optional[str] = None
    status: Literal["generated", "validated", "failed"] = "generated"

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class IntentClassification(BaseModel):
    primaryIntent: IntentKind
    secondaryIntents: list[IntentKind] = Field(default_factory=list)
    productionStage: ProductionStage = "production"
    playbookId: Optional[str] = None
    targetSceneId: Optional[str] = None
    targetShotId: Optional[str] = None
    complexity: Literal["simple", "standard", "complex"] = "standard"
    requiresApproval: bool = False
    needsClarification: bool = False
    clarificationQuestion: Optional[str] = None
    isSimpleQuestion: bool = False
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class ContextPackage(BaseModel):
    schemaVersion: str = CONTEXT_PACKAGE_VERSION
    projectId: str
    activeScope: dict[str, Optional[str]] = Field(default_factory=dict)
    facts: list[ContextFact] = Field(default_factory=list)
    omittedCategories: list[str] = Field(default_factory=list)
    tokenEstimate: int = 0
    contextHash: str = ""
    userMessageDelimited: str = ""
    capabilities: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class SynthesisResult(BaseModel):
    responseType: Literal[
        "answer",
        "recommendation",
        "clarification",
        "warning",
        "proposal",
        "plan",
        "error",
    ] = "recommendation"
    userMessage: str
    recommendation: str = ""
    requirements: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    proposedToolActions: list[ProposedToolAction] = Field(default_factory=list)
    structuredRecommendation: dict[str, Any] = Field(default_factory=dict)
    conflictsResolved: list[str] = Field(default_factory=list)
    specialistIdsUsed: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class PlanStep(BaseModel):
    stepId: str
    title: str
    description: str = ""
    toolId: Optional[str] = None
    requiresApproval: bool = True
    capability: Optional[str] = None
    status: Literal["pending", "blocked", "ready", "completed"] = "pending"
    arguments: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductionPlan(BaseModel):
    schemaVersion: str = PRODUCTION_PLAN_VERSION
    planId: str
    projectId: str
    playbookId: Optional[str] = None
    title: str
    summary: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    approvalRequired: bool = True
    visualValidationPending: bool = False
    promptVersions: dict[str, str] = Field(default_factory=dict)
    requestId: Optional[str] = None

    @field_validator("steps")
    @classmethod
    def _require_steps_for_non_trivial(cls, value: list[PlanStep]) -> list[PlanStep]:
        return value
