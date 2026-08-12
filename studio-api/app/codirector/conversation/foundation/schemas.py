"""Typed contracts for Co-Director foundational intelligence (Part A)."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    INFORM = "INFORM"
    EXPLAIN_PROJECT = "EXPLAIN_PROJECT"
    BRAINSTORM = "BRAINSTORM"
    REQUEST_FEEDBACK = "REQUEST_FEEDBACK"
    REQUEST_PLAN = "REQUEST_PLAN"
    REQUEST_ACTION = "REQUEST_ACTION"
    REQUEST_GENERATION = "REQUEST_GENERATION"
    REQUEST_EDIT = "REQUEST_EDIT"
    REQUEST_RESEARCH = "REQUEST_RESEARCH"
    REQUEST_REVIEW = "REQUEST_REVIEW"
    CORRECT_ASSISTANT = "CORRECT_ASSISTANT"
    EXPRESS_DISSATISFACTION = "EXPRESS_DISSATISFACTION"
    SEEK_REASSURANCE = "SEEK_REASSURANCE"
    SET_PREFERENCE = "SET_PREFERENCE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    PAUSE_ACTION = "PAUSE_ACTION"
    CONTINUE_PREVIOUS_WORK = "CONTINUE_PREVIOUS_WORK"
    UNKNOWN = "UNKNOWN"


class InteractionPosture(str, Enum):
    LISTEN = "LISTEN"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    ASK = "ASK"
    ADVISE = "ADVISE"
    PLAN = "PLAN"
    CREATE = "CREATE"
    REVIEW = "REVIEW"
    EXECUTE = "EXECUTE"
    CLARIFY = "CLARIFY"
    APOLOGIZE_AND_CORRECT = "APOLOGIZE_AND_CORRECT"


class CoDirectorMode(str, Enum):
    LISTENING = "LISTENING"
    DISCOVERY = "DISCOVERY"
    BRAINSTORMING = "BRAINSTORMING"
    DEVELOPMENT = "DEVELOPMENT"
    PLANNING = "PLANNING"
    PRODUCTION = "PRODUCTION"
    REVIEW = "REVIEW"
    CONTINUITY_CHECK = "CONTINUITY_CHECK"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    EXECUTION = "EXECUTION"


class IntentAnalysis(BaseModel):
    primary_intent: IntentType = IntentType.UNKNOWN
    secondary_intents: list[IntentType] = Field(default_factory=list)
    required_postures: list[InteractionPosture] = Field(default_factory=list)
    forbidden_postures: list[InteractionPosture] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    user_goal_summary: str = ""
    evidence_spans: list[str] = Field(default_factory=list)
    should_ask_question: bool = False
    should_use_tools: bool = False
    should_write_memory: bool = False


class DialoguePlan(BaseModel):
    posture: list[InteractionPosture] = Field(default_factory=list)
    response_purpose: str = ""
    required_elements: list[str] = Field(default_factory=list)
    prohibited_elements: list[str] = Field(default_factory=list)
    question_budget: int = 0
    tool_policy: Literal["NONE", "OPTIONAL", "REQUIRED"] = "NONE"
    memory_policy: Literal["NONE", "PROPOSE", "WRITE_CONFIRMED_FACTS"] = "NONE"
    workflow_advance_policy: Literal["HOLD", "SUGGEST", "ADVANCE"] = "HOLD"
    tone_profile: str = "attentive-warm"
    mode: CoDirectorMode = CoDirectorMode.DISCOVERY
    # Companion / advisory attachment (additive; never a parallel speaker)
    advisory: dict = Field(default_factory=dict)
    companion_need: str | None = None
    creative_working_state: str | None = None
    specialist_policy: Literal["NONE", "OPTIONAL_SUBORDINATE", "REQUIRED_SUBORDINATE"] = "NONE"


class ConversationState(BaseModel):
    active_goal: str | None = None
    current_mode: CoDirectorMode = CoDirectorMode.DISCOVERY
    user_intent_summary: str = ""
    pending_questions: list[str] = Field(default_factory=list)
    recent_corrections: list[str] = Field(default_factory=list)
    commitments: list[str] = Field(default_factory=list)
    workflow_hold: bool = False
    preference_explain_before_production: bool = False


class ResponseGroundingCheck(BaseModel):
    directly_addresses_latest_message: bool = True
    reflects_user_goal: bool = True
    contradicts_user_requested_flow: bool = False
    introduces_premature_workflow: bool = False
    asks_unnecessary_question: bool = False
    contains_unsupported_assumption: bool = False
    violates_dialogue_plan: bool = False
    notes: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        if self.violates_dialogue_plan:
            return False
        if self.contradicts_user_requested_flow or self.introduces_premature_workflow:
            return False
        if self.asks_unnecessary_question:
            return False
        if not self.directly_addresses_latest_message or not self.reflects_user_goal:
            return False
        return True


class CoDirectorPersonality(BaseModel):
    """Stable personality profile — expression constraints only (not facts/canon)."""

    warmth: float = 0.62
    curiosity: float = 0.65
    creative_enthusiasm: float = 0.55
    attentiveness: float = 0.7
    compassion: float = 0.55
    directness: float = 0.55
    challenge_level: float = 0.35
    humor: float = 0.25
    formality: float = 0.4
    initiative: float = 0.55
    documentation_drive: float = 0.65
    research_drive: float = 0.45
    user_authorship_respect: float = 0.92
    anti_sycophancy_strength: float = 0.85
    # Backward-compatible aliases used by older guidance
    enthusiasm: float = 0.55
    verbosity: float = 0.45
    production_focus: float = 0.5


# Alias for master-prompt naming
CoDirectorPersonalityProfile = CoDirectorPersonality


class CoDirectorInferenceTrace(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    session_id: str = ""
    selected_provider: str = ""
    selected_model: str = ""
    actual_provider: str = ""
    actual_model: str = ""
    fallback_used: bool = False
    fallback_reason: str | None = None
    system_prompt_version: str = "codirector-foundation-v1"
    conversation_message_count: int = 0
    project_context_token_count: int = 0
    memory_context_token_count: int = 0
    tool_context_token_count: int = 0
    input_token_estimate: int = 0
    output_token_estimate: int = 0
    latency_ms: float = 0.0
    mode: str = ""
    primary_intent: str = ""
    evidence_spans: list[str] = Field(default_factory=list)
    question_budget: int = 0
    workflow_advance_policy: str = ""
