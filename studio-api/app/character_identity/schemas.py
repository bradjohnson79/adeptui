"""Pydantic schemas for Character Identity (M3.3)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ProfileStatus = Literal["DRAFT", "INCOMPLETE", "READY_FOR_GENERATION", "APPROVED", "LOCKED", "ARCHIVED"]
ApprovalStatus = Literal["draft", "review", "approved", "rejected"]
VoiceSourceMode = Literal["DESIGN", "CLONE", "UPLOAD", "PRESET", "UNASSIGNED"]
VoiceStatus = Literal[
    "DRAFT",
    "VALIDATING",
    "READY",
    "GENERATING",
    "REVIEW",
    "APPROVED",
    "REJECTED",
    "FAILED",
    "ARCHIVED",
]
TraitImportance = Literal["canonical", "optional", "scene_specific", "concealable", "forbidden_remove", "forbidden_invent"]

ProvenanceLabel = Literal[
    "PROPOSED_BY_CHARACTER_CREATOR",
    "USER_CONFIRMED",
    "CANONICAL_FROM_USER_APPROVAL",
    "UNCONFIRMED",
    "CONFLICTING",
]

ReadinessCategory = Literal[
    "VisualIdentity",
    "Personality",
    "Performance",
    "Wardrobe",
    "Props",
    "Voice",
    "Continuity",
    "ProductionReadiness",
]


class SkinProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    skin_tone: str = ""
    undertone: str = ""
    texture: str = ""
    pore_detail: str = ""
    freckles: str = ""
    moles: str = ""
    scars: str = ""
    wrinkles: str = ""
    blemishes: str = ""
    birthmarks: str = ""
    tattoos: str = ""
    makeup: str = ""
    facial_hair_interaction: str = ""
    reflectivity: str = ""
    moisture_or_dryness: str = ""
    age_characteristics: str = ""
    lighting_behavior: str = ""
    closeup_preservation_notes: str = ""


class HairProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    primary_color: str = ""
    secondary_tones: str = ""
    highlights: str = ""
    length: str = ""
    texture: str = ""
    density: str = ""
    hairline: str = ""
    parting: str = ""
    volume: str = ""
    curl_pattern: str = ""
    fringe_or_bangs: str = ""
    facial_hair: str = ""
    movement_behavior: str = ""
    canonical_style: str = ""
    alternate_styles: list[str] = Field(default_factory=list)
    wet_state: str = ""
    damaged_state: str = ""
    continuity_restrictions: str = ""


class PersonalityProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    core_personality: str = ""
    temperament: str = ""
    strengths: str = ""
    flaws: str = ""
    fears: str = ""
    motivations: str = ""
    values: str = ""
    social_style: str = ""
    humor: str = ""
    emotional_regulation: str = ""
    conflict_behavior: str = ""
    speech_style: str = ""
    decision_making_style: str = ""
    public_persona: str = ""
    private_persona: str = ""
    relationship_behavior: str = ""
    contradictions: str = ""
    emotional_triggers: str = ""
    vulnerabilities: str = ""
    character_arc: str = ""
    signature_mannerisms: str = ""
    when_calm: str = ""
    when_threatened: str = ""
    when_angry: str = ""
    when_grieving: str = ""
    around_authority: str = ""
    around_strangers: str = ""
    around_trusted: str = ""
    around_loved: str = ""
    while_lying: str = ""
    when_hiding_vulnerability: str = ""
    after_conflict: str = ""
    under_physical_pressure: str = ""


class PerformanceProfile(BaseModel):
    """Character Performance Bible — how the actor performs (not body kinematics).

    Complements MotionProfile. Feeds Prompt Package / Voice Performance (4.4).
    Legacy motion-adjacent keys retained for backward compatibility.
    """

    model_config = ConfigDict(extra="allow")
    schema_version: int = 1
    # Performance Bible (closed structure)
    speakingCadence: str = ""
    interruptTendencies: str = ""
    thinkingPauses: str = ""
    smileFrequency: str = ""
    eyeBehaviorWhileListening: str = ""
    defaultFacialTension: str = ""
    emotionalEscalationStyle: str = ""
    humorStyle: str = ""
    reactionTiming: str = ""
    silenceBehavior: str = ""
    improvisationBoundaries: str = ""
    signatureMannerisms: list[str] = Field(default_factory=list)
    notes: str = ""
    # Legacy keys (pre–Performance Bible) — do not use for new canon
    posture: str = ""
    gait: str = ""
    dominant_hand: str = ""
    resting_facial_expression: str = ""
    eye_contact_behavior: str = ""
    physical_confidence: str = ""
    personal_space_behavior: str = ""
    gestures: str = ""
    nervous_habits: str = ""
    movement_energy: str = ""
    speaking_rhythm: str = ""
    breathing_behavior: str = ""
    reaction_style: str = ""
    enters_room: str = ""
    sits: str = ""
    stands: str = ""
    presents_authority: str = ""
    presents_fear: str = ""
    presents_warmth: str = ""
    presents_anger: str = ""


# Alias used in docs / Co-Director / Prompt Package consumers
PerformanceBible = PerformanceProfile


class ContinuityRules(BaseModel):
    model_config = ConfigDict(extra="allow")
    locked_features: list[str] = Field(default_factory=list)
    notes: str = ""
    forbid_invention: list[str] = Field(default_factory=list)
    forbid_removal: list[str] = Field(default_factory=list)


class MotionProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int = 1
    defaultStandingPosture: str = ""
    walkingStyle: str = ""
    runningStyle: str = ""
    idleTendencies: str = ""
    handGestures: str = ""
    headMovement: str = ""
    eyeContactBehavior: str = ""
    personalSpace: str = ""
    confidenceLevel: str = ""
    energyLevel: str = ""
    combatStance: str = ""
    sittingPosture: str = ""
    signaturePoses: list[str] = Field(default_factory=list)
    emotionalBodyLanguage: dict[str, str] = Field(default_factory=dict)


class EmotionProfile(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int = 1
    baseline: str = ""
    range: str = ""
    sarcasmBehavior: str = ""
    angerBehavior: str = ""
    vulnerabilityBehavior: str = ""
    intensityLimits: str = ""
    triggers: list[str] = Field(default_factory=list)
    notes: str = ""


class RelationshipDynamics(BaseModel):
    """Per-edge dynamics for Director 2.0 / Co-Director grounded interactions."""

    model_config = ConfigDict(extra="allow")
    communicationStyle: str = ""
    humorStyle: str = ""
    typicalConflictResolution: str = ""
    emotionalOpenness: str = ""
    protectiveness: str = ""
    authorityBalance: str = ""


class RelationshipEdge(BaseModel):
    model_config = ConfigDict(extra="allow")
    targetCharacter: str
    relationship: str = ""
    tone: str = ""
    trust: str = ""
    conflict: str = ""
    physicalAggression: str = ""
    comfortDistance: str = ""
    typicalGreeting: str = ""
    # Relationship Dynamics (richer interaction context)
    communicationStyle: str = ""
    humorStyle: str = ""
    typicalConflictResolution: str = ""
    emotionalOpenness: str = ""
    protectiveness: str = ""
    authorityBalance: str = ""
    dynamics: Optional[RelationshipDynamics] = None
    targetStableId: Optional[str] = None
    bibleRelationshipId: Optional[str] = None


class PromptPackage(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int = 1
    character_version_id: str = ""
    generated_at: str = ""
    canon_version: str = ""
    imagePrompt: str = ""
    videoPrompt: str = ""
    storyboardPrompt: str = ""
    director20Prompt: str = ""
    sceneCraftPrompt: str = ""
    voicePrompt: str = ""
    motionPrompt: str = ""
    performancePrompt: str = ""
    referenceSummary: str = ""


class CharacterProfileCreate(BaseModel):
    name: str
    slug: str = ""
    role: str = ""
    description: str = ""
    visual_description: str = ""
    visual_style: str = ""
    apparent_age: str = ""
    species_or_type: str = "human"
    gender_presentation: str = ""
    cultural_background: str = ""
    height_description: str = ""
    body_type: str = ""


class CharacterProfileUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    visual_description: Optional[str] = None
    visual_style: Optional[str] = None
    apparent_age: Optional[str] = None
    species_or_type: Optional[str] = None
    gender_presentation: Optional[str] = None
    cultural_background: Optional[str] = None
    height_description: Optional[str] = None
    body_type: Optional[str] = None
    active_wardrobe_id: Optional[str] = None
    active_voice_profile_id: Optional[str] = None
    skin: Optional[SkinProfile] = None
    hair: Optional[HairProfile] = None
    personality: Optional[PersonalityProfile] = None
    performance: Optional[PerformanceProfile] = None
    continuity: Optional[ContinuityRules] = None
    motion: Optional[MotionProfile] = None
    emotion: Optional[EmotionProfile] = None
    relationships: Optional[list[RelationshipEdge]] = None


class ReferenceAttach(BaseModel):
    asset_id: str
    reference_role: str
    view_angle: str = ""
    framing: str = ""
    notes: str = ""
    source_type: str = "upload"
    canonical: bool = False
    approval_status: str = "draft"
    character_version_id: Optional[str] = None


class WardrobeCreate(BaseModel):
    name: str
    description: str = ""
    materials: str = ""
    colors: str = ""
    footwear: str = ""
    jewelry: str = ""
    accessories: str = ""
    makeup_state: str = ""
    hair_state: str = ""
    continuity_rules: str = ""


class PropCreate(BaseModel):
    name: str
    prop_type: str = ""
    description: str = ""
    materials: str = ""
    colors: str = ""
    placement: str = ""
    how_worn: str = ""
    hand_assignment: str = ""
    usage_behavior: str = ""
    continuity_rules: str = ""
    library_asset_id: Optional[str] = None


class PropUpdate(BaseModel):
    name: Optional[str] = None
    prop_type: Optional[str] = None
    description: Optional[str] = None
    materials: Optional[str] = None
    colors: Optional[str] = None
    placement: Optional[str] = None
    how_worn: Optional[str] = None
    hand_assignment: Optional[str] = None
    usage_behavior: Optional[str] = None
    continuity_rules: Optional[str] = None
    library_asset_id: Optional[str] = None


class TraitUpsert(BaseModel):
    category: str
    key: str
    value: str
    importance: TraitImportance = "canonical"
    canonical: bool = True
    character_version_id: Optional[str] = None
    provenance: str = "PROPOSED_BY_CHARACTER_CREATOR"


class CategoryReadiness(BaseModel):
    category: ReadinessCategory
    score: float
    ready: bool
    blockers: list[str] = Field(default_factory=list)
    next_action: str = ""
    critical: bool = False


class CoverageReport(BaseModel):
    status: ProfileStatus
    score: float
    required_roles: list[str]
    present_roles: list[str]
    missing_roles: list[str]
    guidance: list[str]
    has_physical_details: bool
    has_personality: bool
    has_performance: bool
    has_wardrobe: bool
    voice_state: VoiceSourceMode
    ready_for_generation: bool
    category_readiness: list[CategoryReadiness] = Field(default_factory=list)
    critical_blockers: list[str] = Field(default_factory=list)
    next_action: str = ""


class VoiceProfileCreate(BaseModel):
    name: str
    source_mode: VoiceSourceMode = "UNASSIGNED"
    provider: str = ""
    model_id: str = ""
    language: str = "en"
    accent: str = ""
    perceived_age: str = ""
    pitch_description: str = ""
    pace_description: str = ""
    tone_description: str = ""
    resonance_description: str = ""
    warmth: str = ""
    breathiness: str = ""
    energy: str = ""
    emotional_range: str = ""
    pronunciation_notes: str = ""
    voice_design_prompt: str = ""
    reference_asset_id: Optional[str] = None
    reference_transcript: str = ""
    character_version_id: Optional[str] = None


class VoiceConsentCreate(BaseModel):
    source_owner_name: str = ""
    performer_name: str = ""
    authority_type: str = "self"
    consent_confirmed: bool = False
    commercial_use_allowed: bool = False
    synthetic_generation_allowed: bool = False
    project_scope: str = "project"
    restriction_notes: str = ""
    confirmed_by: str = ""


class DialogueGenerateRequest(BaseModel):
    text: str
    language: str = "en"
    emotional_direction: str = ""
    performance_instruction: str = ""
    pace: str = ""
    target_duration_sec: Optional[float] = None
    allow_kokoro_fallback: bool = False


class CharacterProfileOut(BaseModel):
    id: str
    project_id: str
    name: str
    slug: str
    role: str
    description: str
    apparent_age: str
    species_or_type: str
    gender_presentation: str
    cultural_background: str
    height_description: str
    body_type: str
    visual_description: str
    visual_style: str
    status: ProfileStatus
    approval_status: ApprovalStatus
    active_version_id: Optional[str]
    active_voice_profile_id: Optional[str]
    active_wardrobe_id: Optional[str]
    skin: dict[str, Any]
    hair: dict[str, Any]
    personality: dict[str, Any]
    performance: dict[str, Any]
    continuity: dict[str, Any]
    motion: dict[str, Any] = Field(default_factory=dict)
    emotion: dict[str, Any] = Field(default_factory=dict)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    prompt_package: dict[str, Any] = Field(default_factory=dict)
    coverage: Optional[CoverageReport] = None
    created_at: str
    updated_at: str
