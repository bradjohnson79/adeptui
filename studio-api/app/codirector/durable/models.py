"""Typed authority objects for one Co-Director turn.

Core decisions use these models. Handler dicts are parsed at the boundary
and are not themselves authority.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TurnMode = Literal["CONVERSATION", "READ", "PROPOSE", "MUTATE", "NAVIGATE"]
SemanticSurface = Literal[
    "TIMELINE",
    "CHARACTER_CREATOR",
    "PROP_CREATOR",
    "ENVIRONMENT_CREATOR",
    "IMAGE_GENERATOR",
    "VOICE_STUDIO",
    "AUDIO_STUDIO",
    "NONE",
]
SemanticConfidence = Literal["high", "medium", "low"]
ExecutionStatus = Literal["not_run", "running", "succeeded", "failed", "rejected"]
MutationStatus = Literal["none", "proposed", "written", "not_written"]
VerificationStatus = Literal["not_applicable", "pending", "verified", "failed", "ambiguous"]


class AuthorityEnvelope(BaseModel):
    """Admission snapshot. Replay uses this record, not later configuration."""

    workflow_id: str
    project_id: str
    scene_id: str | None = None
    turn_mode: TurnMode
    system_prompt_version: str
    system_prompt_hash: str
    provider_id: str
    model_id: str
    exposed_tool_ids: list[str]
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    master_hash_before: str | None = None
    context_snapshot_id: str
    user_text: str
    surface: str | None = None
    selected_character_id: str | None = None


class CoDirectorContext(BaseModel):
    envelope: AuthorityEnvelope
    user_text: str


class ProjectContext(BaseModel):
    project_id: str
    context_snapshot_id: str


class SceneContext(BaseModel):
    project_id: str
    scene_id: str | None = None
    master_hash: str | None = None


class SemanticEntities(BaseModel):
    characters: list[str] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    scenes: list[str] = Field(default_factory=list)


class SemanticConstraints(BaseModel):
    duration: str | None = None
    aspect_ratio: str | None = None
    no_execute: bool = False


class SemanticDecision(BaseModel):
    """The model's reading of the turn. The server still admits the tool."""

    mode: TurnMode = "CONVERSATION"
    surface: SemanticSurface = "NONE"
    action: str = ""
    entities: SemanticEntities = Field(default_factory=SemanticEntities)
    constraints: SemanticConstraints = Field(default_factory=SemanticConstraints)
    confidence: SemanticConfidence = "medium"
    reply: str = ""
    tool_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentDecision(BaseModel):
    """Reasoning output only. It does not authorize a side effect."""

    turn_mode: TurnMode
    reply: str = ""
    tool_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    semantic: SemanticDecision | None = None


class ToolIntent(BaseModel):
    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    turn_mode: TurnMode


class ToolRequest(BaseModel):
    workflow_id: str
    tool_call_id: str
    mutation_id: str
    project_id: str
    scene_id: str | None = None
    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    action: str


class ToolReceipt(BaseModel):
    requested_action: str
    target: str
    tool_id: str
    execution_status: ExecutionStatus
    mutation_status: MutationStatus
    verification_status: VerificationStatus
    master_hash_before: str | None = None
    master_hash_after: str | None = None
    error: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class VerifiedMutationReceipt(ToolReceipt):
    verification_status: Literal["verified"] = "verified"
    mutation_status: Literal["written"] = "written"


class FailureState(BaseModel):
    code: str
    message: str
    workflow_id: str
    tool_id: str | None = None
    mutation_id: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    workflow_id: str
    trace_id: str
    reply: str
    provider_id: str
    model_id: str
    turn_mode: TurnMode
    receipts: list[ToolReceipt] = Field(default_factory=list)
    failure: FailureState | None = None


class ConversationEvent(BaseModel):
    project_id: str
    workflow_id: str
    role: Literal["user", "assistant"]
    content: str


class MutationEvent(BaseModel):
    workflow_id: str
    mutation_id: str
    tool_id: str
    project_id: str
    scene_id: str | None = None
    verified: bool
    master_hash_before: str | None = None
    master_hash_after: str | None = None


class CoDirectorTurn(BaseModel):
    envelope: AuthorityEnvelope
    response: AssistantResponse | None = None
