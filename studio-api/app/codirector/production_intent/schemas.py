"""ProductionIntent + CreativeContext contracts (M41 W6P-2 / W6P-6)."""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


ProductionOperation = Literal[
    "image.generate",
    "image.edit",
    "video.generate",
    "video.three_frame",
    "video.shot_render",
    "video.scene_render",
    "video.timeline_render",
    "video.batch_timeline",
    "video.extend",
    "video.lipsync",
    "voice.generate",
    "music.generate",
    "sfx.generate",
    "subtitle.generate",
    "editor.place",
    "asset.replace",
    "asset.create_variation",
    "job.cancel",
    "job.retry",
]

Modality = Literal["image", "video", "audio", "subtitle", "editorial", "job", "plan"]
SourceSurface = Literal[
    "codirector",
    "director",
    "generate_studio",
    "timeline",
    "specialist",
    "planner",
    "api",
]
ApprovalPolicyState = Literal[
    "not_required",
    "awaiting_approval",
    "approved",
    "rejected",
    "expired",
    "cancelled",
]
RecoveryPolicy = Literal[
    "retry_same",
    "retry_lower_profile",
    "wait_for_runtime",
    "request_missing_input",
    "request_user_approval",
    "manual_review",
    "resume_from_completed_children",
    "blocked_no_safe_fallback",
]
IntentExecutionState = Literal[
    "draft",
    "ready",
    "awaiting_approval",
    "queued",
    "running",
    "validating",
    "completed",
    "blocked",
    "failed",
    "cancelling",
    "cancelled",
    "superseded",
]


class CreativeContext(BaseModel):
    projectIntent: str = ""
    visualLanguage: dict[str, Any] = Field(default_factory=dict)
    cinematography: dict[str, Any] = Field(default_factory=dict)
    characterIdentity: list[dict[str, Any]] = Field(default_factory=list)
    wardrobe: list[dict[str, Any]] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    lighting: dict[str, Any] = Field(default_factory=dict)
    continuity: dict[str, Any] = Field(default_factory=dict)
    approvedReferences: list[dict[str, Any]] = Field(default_factory=list)
    prohibitedChanges: list[str] = Field(default_factory=list)
    outputPurpose: str = ""
    digest: str = ""


class ProductionIntent(BaseModel):
    intentId: str = Field(default_factory=lambda: str(uuid4()))
    projectId: str
    sceneId: Optional[str] = None
    shotId: Optional[str] = None
    requestedBy: str = "user"
    sourceSurface: SourceSurface = "codirector"
    operation: ProductionOperation
    modality: Modality = "video"
    objective: str = ""
    prompt: str = ""
    references: list[dict[str, Any]] = Field(default_factory=list)
    sourceAssets: list[str] = Field(default_factory=list)
    targetPlacement: Optional[dict[str, Any]] = None
    enginePreference: Optional[str] = None
    workflowPreference: Optional[str] = None
    qualityProfile: str = "standard"
    duration: Optional[float] = None
    aspectRatio: Optional[str] = None
    approvalPolicy: ApprovalPolicyState = "not_required"
    costPolicy: dict[str, Any] = Field(default_factory=dict)
    retryPolicy: RecoveryPolicy = "retry_same"
    continuityRequirements: dict[str, Any] = Field(default_factory=dict)
    outputRequirements: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    creativeContext: Optional[CreativeContext] = None
    toolId: Optional[str] = None
    handoffId: Optional[str] = None
    parentIntentId: Optional[str] = None
    planId: Optional[str] = None
    planStepId: Optional[str] = None
    jobId: Optional[str] = None
    workflowId: Optional[str] = None
    workflowKey: Optional[str] = None
    workflowVersion: Optional[str] = None
    certificationRecordId: Optional[str] = None
    executionState: IntentExecutionState = "draft"
    createdAt: str = ""
    updatedAt: str = ""


class SpecialistHandoff(BaseModel):
    handoffId: str = Field(default_factory=lambda: str(uuid4()))
    parentIntentId: Optional[str] = None
    specialistId: str
    taskType: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    expectedOutputs: list[str] = Field(default_factory=list)
    recommendedOperation: Optional[ProductionOperation] = None
    approvalState: ApprovalPolicyState = "not_required"
    executionState: IntentExecutionState = "draft"
    resultRefs: list[str] = Field(default_factory=list)
    projectId: str = ""
    createdAt: str = ""
