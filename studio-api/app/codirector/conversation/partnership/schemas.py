"""Typed contracts for hands-on partnership: ownership, journey, artifacts, vision, pitch, marketing."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CollaborationOwnership(str, Enum):
    USER_LEADS = "USER_LEADS"
    CO_CREATE = "CO_CREATE"
    CODIRECTOR_LEADS = "CODIRECTOR_LEADS"
    CODIRECTOR_EXECUTES = "CODIRECTOR_EXECUTES"
    ASK_EACH_TIME = "ASK_EACH_TIME"


class ProductionCollaborationProfile(BaseModel):
    project_id: str = ""
    concept_development: CollaborationOwnership = CollaborationOwnership.CO_CREATE
    research: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    discovery_brief: CollaborationOwnership = CollaborationOwnership.CO_CREATE
    treatment: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    story_outline: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    character_development: CollaborationOwnership = CollaborationOwnership.CO_CREATE
    worldbuilding: CollaborationOwnership = CollaborationOwnership.CO_CREATE
    screenplay: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    revision: CollaborationOwnership = CollaborationOwnership.CO_CREATE
    visual_development: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    storyboarding: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    shot_planning: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    production_planning: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    asset_creation: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    generation_execution: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    editing: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    sound_and_music: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    marketing: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    pitch_package: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    festival_submission: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    release_strategy: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    default_ownership: CollaborationOwnership = CollaborationOwnership.CO_CREATE
    ask_when_unclear: bool = True
    updated_at: str = ""


class CreativeDeliverableStatus(str, Enum):
    PREVIEW = "PREVIEW"
    PROPOSED = "PROPOSED"
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    LOCKED = "LOCKED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class CreativeDeliverable(BaseModel):
    id: str = Field(default_factory=lambda: f"del-{uuid4().hex[:10]}")
    project_id: str = ""
    type: str = "story_template"
    title: str = ""
    ownership_mode: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    current_author: Literal["USER", "CO_DIRECTOR", "SHARED"] = "CO_DIRECTOR"
    status: CreativeDeliverableStatus = CreativeDeliverableStatus.PREVIEW
    content: str = ""
    preview_content: str = ""
    why_now: str = ""
    source_ids: list[str] = Field(default_factory=list)
    approval_required: bool = True
    revision_count: int = 0
    revision_history: list[str] = Field(default_factory=list)
    field_marks: dict[str, str] = Field(default_factory=dict)  # Confirmed|Emerging|Needs decision|Interpretation
    assumptions: list[str] = Field(default_factory=list)


class ArtifactReadiness(str, Enum):
    NOT_READY = "NOT_READY"
    PARTIAL = "PARTIAL"
    READY = "READY"


class ArtifactRecommendedAction(str, Enum):
    WAIT = "WAIT"
    SHOW_PREVIEW = "SHOW_PREVIEW"
    ASK_QUESTION = "ASK_QUESTION"
    PROPOSE_DRAFT = "PROPOSE_DRAFT"
    CREATE_DRAFT = "CREATE_DRAFT"


class ArtifactReadinessAssessment(BaseModel):
    artifact_type: str = ""
    readiness: ArtifactReadiness = ArtifactReadiness.NOT_READY
    why_now: str = ""
    supporting_facts: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    ownership_mode: CollaborationOwnership = CollaborationOwnership.ASK_EACH_TIME
    recommended_action: ArtifactRecommendedAction = ArtifactRecommendedAction.WAIT
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    preview_hook: str = ""


class ProductionJourneyStage(str, Enum):
    RELATIONSHIP_SETUP = "RELATIONSHIP_SETUP"
    INITIAL_IDEA = "INITIAL_IDEA"
    DISCOVERY = "DISCOVERY"
    RESEARCH = "RESEARCH"
    LIVING_BRIEF = "LIVING_BRIEF"
    TREATMENT = "TREATMENT"
    OUTLINE = "OUTLINE"
    CHARACTER_WORLD = "CHARACTER_WORLD"
    SCREENPLAY = "SCREENPLAY"
    REVISION = "REVISION"
    VISUAL_DEVELOPMENT = "VISUAL_DEVELOPMENT"
    PRE_PRODUCTION = "PRE_PRODUCTION"
    PRODUCTION = "PRODUCTION"
    POST_PRODUCTION = "POST_PRODUCTION"
    MARKETING_PREP = "MARKETING_PREP"
    PITCH_PACKAGE = "PITCH_PACKAGE"
    RELEASE = "RELEASE"
    PROMOTION = "PROMOTION"


class ProductionJourneyState(BaseModel):
    project_id: str = ""
    current_stage: str = ProductionJourneyStage.INITIAL_IDEA.value
    completed_stages: list[str] = Field(default_factory=list)
    active_deliverables: list[str] = Field(default_factory=list)
    upcoming_decisions: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    ownership_resolved_for_current_stage: bool = False
    next_recommended_stage: str | None = None
    next_useful_artifact: str | None = None


class QuestionCategory(str, Enum):
    OWNERSHIP = "OWNERSHIP"
    CREATIVE_DIRECTION = "CREATIVE_DIRECTION"
    STORY = "STORY"
    CHARACTER = "CHARACTER"
    VISION = "VISION"
    AUDIENCE = "AUDIENCE"
    DISTRIBUTION = "DISTRIBUTION"
    PRODUCTION = "PRODUCTION"
    MARKETING = "MARKETING"
    PITCH = "PITCH"
    APPROVAL = "APPROVAL"
    DELIVERY = "DELIVERY"


class ContextualQuestionCandidate(BaseModel):
    id: str = Field(default_factory=lambda: f"cq-{uuid4().hex[:10]}")
    project_id: str = ""
    question: str = ""
    category: QuestionCategory = QuestionCategory.STORY
    why_it_matters: str = ""
    required_before_action: bool = False
    information_value: float = 0.5
    interruption_cost: float = 0.5
    urgency: float = 0.3
    can_defer: bool = True
    deferred: bool = False
    source_ids: list[str] = Field(default_factory=list)


class ProjectDestination(str, Enum):
    PERSONAL = "PERSONAL"
    PORTFOLIO = "PORTFOLIO"
    YOUTUBE = "YOUTUBE"
    SOCIAL_SHORT = "SOCIAL_SHORT"
    FILM_FESTIVALS = "FILM_FESTIVALS"
    PROOF_OF_CONCEPT = "PROOF_OF_CONCEPT"
    PRODUCER_PITCH = "PRODUCER_PITCH"
    NETWORK_PITCH = "NETWORK_PITCH"
    STREAMER_PITCH = "STREAMER_PITCH"
    INVESTOR_PITCH = "INVESTOR_PITCH"
    CROWDFUNDING = "CROWDFUNDING"
    INDEPENDENT_COMMERCIAL = "INDEPENDENT_COMMERCIAL"
    THEATRICAL = "THEATRICAL"
    EDUCATIONAL = "EDUCATIONAL"
    CLIENT = "CLIENT"
    COMMUNITY = "COMMUNITY"
    UNDECIDED = "UNDECIDED"
    CUSTOM = "CUSTOM"


class ProjectVisionProfile(BaseModel):
    project_id: str = ""
    primary_destination: ProjectDestination = ProjectDestination.UNDECIDED
    secondary_destinations: list[ProjectDestination] = Field(default_factory=list)
    creator_goal: str = ""
    intended_audience: list[str] = Field(default_factory=list)
    desired_audience_response: list[str] = Field(default_factory=list)
    success_definition: list[str] = Field(default_factory=list)
    target_format: str | None = None
    target_runtime: str | None = None
    target_release_window: str | None = None
    project_scale: Literal["PERSONAL", "MICRO", "INDEPENDENT", "PROFESSIONAL", "STUDIO", "UNDECIDED"] = "UNDECIDED"
    commercial_intent: Literal["NONE", "OPTIONAL", "EXPECTED", "PRIMARY", "UNDECIDED"] = "UNDECIDED"
    creator_confirmed: bool = False
    source_ids: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class PitchType(str, Enum):
    ELEVATOR = "ELEVATOR"
    ONE_PARAGRAPH = "ONE_PARAGRAPH"
    VERBAL = "VERBAL"
    PRODUCER = "PRODUCER"
    NETWORK = "NETWORK"
    STREAMER = "STREAMER"
    INVESTOR = "INVESTOR"
    FESTIVAL = "FESTIVAL"
    CROWDFUNDING = "CROWDFUNDING"
    YOUTUBE = "YOUTUBE"
    PARTNERSHIP = "PARTNERSHIP"


class PitchPackage(BaseModel):
    id: str = Field(default_factory=lambda: f"pitch-{uuid4().hex[:10]}")
    project_id: str = ""
    pitch_type: PitchType = PitchType.ONE_PARAGRAPH
    recipient_type: str = "general"
    objective: str = ""
    logline: str = ""
    short_pitch: str = ""
    long_pitch: str | None = None
    creator_statement: str | None = None
    audience_case: str | None = None
    comparable_works: list[str] = Field(default_factory=list)
    differentiation: list[str] = Field(default_factory=list)
    production_readiness: list[str] = Field(default_factory=list)
    requested_outcome: str = ""
    supporting_assets: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    status: Literal["DRAFT", "REVIEW", "APPROVED"] = "DRAFT"
    why_now: str = ""


class MarketingStrategyProfile(BaseModel):
    project_id: str = ""
    audience_segments: list[str] = Field(default_factory=list)
    positioning_statement: str | None = None
    key_hooks: list[str] = Field(default_factory=list)
    emotional_promise: list[str] = Field(default_factory=list)
    differentiation_points: list[str] = Field(default_factory=list)
    campaign_phases: list[str] = Field(default_factory=list)
    platform_strategies: list[str] = Field(default_factory=list)
    brand_assets_needed: list[str] = Field(default_factory=list)
    promotional_content_ideas: list[str] = Field(default_factory=list)
    calls_to_action: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    status: Literal["EMERGING", "DRAFT", "APPROVED"] = "EMERGING"
    forced: bool = False  # True would violate personal-project protection


class PitchRehearsalDebrief(BaseModel):
    role: str = ""
    what_landed: list[str] = Field(default_factory=list)
    what_was_unclear: list[str] = Field(default_factory=list)
    what_sounded_generic: list[str] = Field(default_factory=list)
    what_needs_evidence: list[str] = Field(default_factory=list)
    what_should_be_shorter: list[str] = Field(default_factory=list)
    what_should_be_emphasized: list[str] = Field(default_factory=list)
    likely_follow_ups: list[str] = Field(default_factory=list)


class PartnershipProjectBundle(BaseModel):
    collaboration: ProductionCollaborationProfile = Field(default_factory=ProductionCollaborationProfile)
    journey: ProductionJourneyState = Field(default_factory=ProductionJourneyState)
    vision: ProjectVisionProfile = Field(default_factory=ProjectVisionProfile)
    marketing: MarketingStrategyProfile = Field(default_factory=MarketingStrategyProfile)
    deliverables: list[CreativeDeliverable] = Field(default_factory=list)
    pitches: list[PitchPackage] = Field(default_factory=list)
    deferred_questions: list[ContextualQuestionCandidate] = Field(default_factory=list)
    last_readiness: list[ArtifactReadinessAssessment] = Field(default_factory=list)
    last_rehearsal: PitchRehearsalDebrief | None = None
    last_preview_id: str | None = None


HANDS_ON_POLICY_VERSION = "codirector-hands-on-partnership-v1"
MAJOR_ARTIFACT_TYPES = {
    "story_template",
    "treatment",
    "outline",
    "screenplay",
    "pitch_summary",
    "pitch_package",
    "marketing_brief",
    "marketing_plan",
    "youtube_launch_plan",
    "festival_checklist",
    "production_plan",
}
