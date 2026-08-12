"""Typed contracts for Creative Companion & Advisory Intelligence."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CreativeWorkingState(str, Enum):
    FLOWING = "FLOWING"
    EXPLORING = "EXPLORING"
    UNCERTAIN = "UNCERTAIN"
    STUCK = "STUCK"
    OVERWHELMED = "OVERWHELMED"
    FRUSTRATED = "FRUSTRATED"
    DISCOURAGED = "DISCOURAGED"
    FATIGUED = "FATIGUED"
    SEEKING_VALIDATION = "SEEKING_VALIDATION"
    SEEKING_CRITIQUE = "SEEKING_CRITIQUE"
    CELEBRATING_PROGRESS = "CELEBRATING_PROGRESS"
    NEUTRAL = "NEUTRAL"


class CompanionNeed(str, Enum):
    LISTEN = "LISTEN"
    ENCOURAGE = "ENCOURAGE"
    INSPIRE = "INSPIRE"
    REFRAME = "REFRAME"
    UNBLOCK = "UNBLOCK"
    SIMPLIFY = "SIMPLIFY"
    BRAINSTORM = "BRAINSTORM"
    CRITIQUE = "CRITIQUE"
    CELEBRATE = "CELEBRATE"
    RESTORE_CONTEXT = "RESTORE_CONTEXT"
    ADVISE = "ADVISE"
    EXECUTE = "EXECUTE"


class CreativeSupportAssessment(BaseModel):
    working_state: CreativeWorkingState = CreativeWorkingState.NEUTRAL
    support_needed: CompanionNeed = CompanionNeed.LISTEN
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_spans: list[str] = Field(default_factory=list)
    likely_user_goal: str = ""
    suggested_response_strategy: list[str] = Field(default_factory=list)
    should_avoid: list[str] = Field(default_factory=list)
    emotional_commentary_appropriate: bool = False


class PrincipleStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    EMERGING = "EMERGING"
    EXPERIMENTAL = "EXPERIMENTAL"
    DISPUTED = "DISPUTED"
    SUPERSEDED = "SUPERSEDED"
    EXPLORATORY = "EXPLORATORY"
    PROPOSED = "PROPOSED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"


class PrincipleImportance(str, Enum):
    FOUNDATIONAL = "FOUNDATIONAL"
    MAJOR = "MAJOR"
    SUPPORTING = "SUPPORTING"


class StoryPrinciple(BaseModel):
    id: str = Field(default_factory=lambda: f"prin-{uuid4().hex[:10]}")
    project_id: str = ""
    statement: str = ""
    category: str = "general"
    status: PrincipleStatus = PrincipleStatus.EMERGING
    importance: PrincipleImportance = PrincipleImportance.SUPPORTING
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    creator_confirmed: bool = False
    created_at: str = ""
    updated_at: str = ""
    supersedes_id: str | None = None


class StoryStrengthProfile(BaseModel):
    project_id: str = ""
    emotional_core: list[str] = Field(default_factory=list)
    thematic_pillars: list[str] = Field(default_factory=list)
    character_promises: list[str] = Field(default_factory=list)
    relationship_promises: list[str] = Field(default_factory=list)
    world_laws: list[str] = Field(default_factory=list)
    tone_commitments: list[str] = Field(default_factory=list)
    mystery_boundaries: list[str] = Field(default_factory=list)
    audience_promises: list[str] = Field(default_factory=list)
    visual_identity: list[str] = Field(default_factory=list)
    creator_non_negotiables: list[str] = Field(default_factory=list)


class CreatorStrength(BaseModel):
    id: str = Field(default_factory=lambda: f"str-{uuid4().hex[:10]}")
    statement: str = ""
    evidence_source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    project_scope: str | None = None
    confirmed_by_user: bool = False
    status: str = "proposed"


class CreativeMilestone(BaseModel):
    id: str = Field(default_factory=lambda: f"ms-{uuid4().hex[:10]}")
    description: str = ""
    significance: str = ""
    source_ids: list[str] = Field(default_factory=list)
    occurred_at: str = ""
    project_id: str = ""


class ProjectCreativeLens(BaseModel):
    project_id: str = ""
    dominant_genres: list[str] = Field(default_factory=list)
    emotional_tones: list[str] = Field(default_factory=list)
    artistic_priorities: list[str] = Field(default_factory=list)
    narrative_risk_tolerance: str = "moderate"
    ambiguity_preference: str = "balanced"
    pacing_preference: str | None = None
    critique_style: str = "direct-respectful"
    production_priorities: list[str] = Field(default_factory=list)
    aesthetic_commitments: list[str] = Field(default_factory=list)
    status: str = "emerging"
    source_ids: list[str] = Field(default_factory=list)
    creator_confirmed: bool = False


class CreatorCompanionState(BaseModel):
    project_id: str = ""
    current_working_state: CreativeWorkingState = CreativeWorkingState.NEUTRAL
    current_need: CompanionNeed = CompanionNeed.LISTEN
    critique_preference: str | None = None
    encouragement_preference: str | None = None
    initiative_preference: str | None = None
    explain_before_planning: bool = False
    do_not_interrupt_while_narrating: bool = False
    ask_before_changing_canon: bool = True
    preserve_exploratory_as_variants: bool = True
    prefer_focused_suggestions: bool = True
    known_strength_ids: list[str] = Field(default_factory=list)
    recent_milestone_ids: list[str] = Field(default_factory=list)
    deferred_question_ids: list[str] = Field(default_factory=list)
    current_momentum: str = ""
    updated_at: str = ""


class CreativeBlockType(str, Enum):
    CONCEPTUAL = "CONCEPTUAL"
    STRUCTURAL = "STRUCTURAL"
    CHARACTER = "CHARACTER"
    EMOTIONAL = "EMOTIONAL"
    CONTINUITY = "CONTINUITY"
    CHOICE_PARALYSIS = "CHOICE_PARALYSIS"
    PERFECTION_PRESSURE = "PERFECTION_PRESSURE"
    PRODUCTION_OVERLOAD = "PRODUCTION_OVERLOAD"
    TECHNICAL_FRICTION = "TECHNICAL_FRICTION"
    FATIGUE = "FATIGUE"
    UNKNOWN = "UNKNOWN"


class CreativeBlockAssessment(BaseModel):
    block_type: CreativeBlockType = CreativeBlockType.UNKNOWN
    evidence_spans: list[str] = Field(default_factory=list)
    likely_root_problem: str = ""
    relevant_story_strength_ids: list[str] = Field(default_factory=list)
    relevant_return_point_ids: list[str] = Field(default_factory=list)
    intervention_options: list[str] = Field(default_factory=list)
    recommended_first_step: str = ""
    focused_question_required: bool = False
    confidence: float = 0.5


class CreativeReturnPoint(BaseModel):
    id: str = Field(default_factory=lambda: f"rp-{uuid4().hex[:10]}")
    project_id: str = ""
    description: str = ""
    why_it_worked: str = ""
    related_scene_ids: list[str] = Field(default_factory=list)
    related_character_ids: list[str] = Field(default_factory=list)
    related_principle_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    creator_confirmed: bool = False
    status: str = "active"


class StoryProblemSource(str, Enum):
    FOUNDATIONAL_STORY = "FOUNDATIONAL_STORY"
    STRUCTURE = "STRUCTURE"
    PACING = "PACING"
    CHARACTERIZATION = "CHARACTERIZATION"
    DIALOGUE = "DIALOGUE"
    EMOTIONAL_DELIVERY = "EMOTIONAL_DELIVERY"
    INFORMATION_DELIVERY = "INFORMATION_DELIVERY"
    PRESENTATION = "PRESENTATION"
    VISUAL_EXECUTION = "VISUAL_EXECUTION"
    PRODUCTION_SCOPE = "PRODUCTION_SCOPE"
    TECHNICAL_LIMITATION = "TECHNICAL_LIMITATION"
    EDITING = "EDITING"
    PERFORMANCE = "PERFORMANCE"
    SOUND = "SOUND"
    USER_UNCERTAINTY = "USER_UNCERTAINTY"
    UNKNOWN = "UNKNOWN"


class StoryDeviationType(str, Enum):
    NATURAL_EVOLUTION = "NATURAL_EVOLUTION"
    INTENTIONAL_RETCON = "INTENTIONAL_RETCON"
    THEMATIC_REFINEMENT = "THEMATIC_REFINEMENT"
    PRODUCTION_ADAPTATION = "PRODUCTION_ADAPTATION"
    EXPERIMENTAL_VARIANT = "EXPERIMENTAL_VARIANT"
    ACCIDENTAL_DRIFT = "ACCIDENTAL_DRIFT"
    CANON_CONFLICT = "CANON_CONFLICT"
    UNKNOWN = "UNKNOWN"


class AdvisoryStrength(str, Enum):
    OBSERVATION = "OBSERVATION"
    SUGGESTION = "SUGGESTION"
    RECOMMENDATION = "RECOMMENDATION"
    STRONG_RECOMMENDATION = "STRONG_RECOMMENDATION"
    FOUNDATIONAL_WARNING = "FOUNDATIONAL_WARNING"


class AdvisoryEpistemics(BaseModel):
    confidence: float = 0.5
    evidence_quality: str = "limited"
    supporting_source_ids: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    interpretation_status: str = "inferred"
    user_confirmation_needed: bool = False


class StoryDeviationAssessment(BaseModel):
    proposed_change: str = ""
    user_goal_behind_change: str = ""
    affected_principle_ids: list[str] = Field(default_factory=list)
    problem_source: StoryProblemSource = StoryProblemSource.UNKNOWN
    deviation_type: StoryDeviationType = StoryDeviationType.UNKNOWN
    likely_gains: list[str] = Field(default_factory=list)
    likely_losses: list[str] = Field(default_factory=list)
    continuity_effects: list[str] = Field(default_factory=list)
    emotional_effects: list[str] = Field(default_factory=list)
    thematic_effects: list[str] = Field(default_factory=list)
    production_effects: list[str] = Field(default_factory=list)
    story_change_necessary: bool = False
    alternative_adjustments: list[str] = Field(default_factory=list)
    advisory_strength: AdvisoryStrength = AdvisoryStrength.OBSERVATION
    recommendation: str = ""
    epistemics: AdvisoryEpistemics = Field(default_factory=AdvisoryEpistemics)
    triggered: bool = False


class CreativeAdvisoryPlan(BaseModel):
    should_advise: bool = False
    acknowledge_user_logic: bool = True
    identify_story_strength: bool = False
    identify_actual_problem: bool = False
    compare_gains_and_losses: bool = False
    provide_alternative: bool = False
    advisory_strength: AdvisoryStrength = AdvisoryStrength.OBSERVATION
    request_confirmation: bool = False
    preserve_as_variant: bool = False
    canon_write_allowed: bool = False
    accept_after_confirmation: bool = False
    no_relitigation_after_confirmation: bool = True


class AdvisoryDecisionState(str, Enum):
    EXPLORATORY = "EXPLORATORY"
    ASSESSED = "ASSESSED"
    ADVISED = "ADVISED"
    USER_RECONSIDERING = "USER_RECONSIDERING"
    TEST_VARIANT = "TEST_VARIANT"
    USER_CONFIRMED_KEEP_CURRENT = "USER_CONFIRMED_KEEP_CURRENT"
    USER_CONFIRMED_CHANGE = "USER_CONFIRMED_CHANGE"
    CANON_UPDATE_PENDING = "CANON_UPDATE_PENDING"
    CANON_UPDATED = "CANON_UPDATED"
    COLLABORATING_ON_DIRECTION = "COLLABORATING_ON_DIRECTION"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    IDLE = "IDLE"


class CompanionMemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"mem-{uuid4().hex[:10]}")
    project_id: str = ""
    category: str = ""
    content: str = ""
    status: str = "proposed"
    source_type: str = "conversation"
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    creator_confirmed: bool = False
    created_at: str = ""
    updated_at: str = ""
    supersedes_id: str | None = None


class CoDirectorCompanionTrace(BaseModel):
    request_id: str = ""
    project_id: str = ""
    session_id: str = ""
    selected_provider: str = ""
    selected_model: str = ""
    actual_provider: str = ""
    actual_model: str = ""
    fallback_used: bool = False
    cognitive_mode: str = ""
    primary_intent: str = ""
    companion_need: str = ""
    advisory_triggered: bool = False
    advisory_strength: str | None = None
    decision_state: str | None = None
    principles_retrieved: int = 0
    strengths_retrieved: int = 0
    specialist_calls: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    canon_write_attempted: bool = False
    canon_write_completed: bool = False
    grounding_passed: bool = True
    repair_used: bool = False
    latency_ms: float = 0.0


class CompanionProjectBundle(BaseModel):
    """Durable project-scoped companion memory blob."""

    companionState: CreatorCompanionState = Field(default_factory=CreatorCompanionState)
    principles: list[StoryPrinciple] = Field(default_factory=list)
    strengthProfile: StoryStrengthProfile = Field(default_factory=StoryStrengthProfile)
    creatorStrengths: list[CreatorStrength] = Field(default_factory=list)
    milestones: list[CreativeMilestone] = Field(default_factory=list)
    returnPoints: list[CreativeReturnPoint] = Field(default_factory=list)
    creativeLens: ProjectCreativeLens = Field(default_factory=ProjectCreativeLens)
    advisoryDecisionState: AdvisoryDecisionState = AdvisoryDecisionState.IDLE
    lastAdvisoryChange: str | None = None
    exploratoryVariants: list[dict] = Field(default_factory=list)
    memoryRecords: list[CompanionMemoryRecord] = Field(default_factory=list)
