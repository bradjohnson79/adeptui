"""Shared Scene Production contracts. Timeline batch is the source of truth after prepare."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


PreparationState = Literal[
    "parsing",
    "resolving_references",
    "validating_generator",
    "compiling_prompt",
    "building_timeline",
    "ready",
    "submitted",
    "queued",
    "generating",
    "completed",
    "failed",
]

ReferenceStatus = Literal["found", "missing", "ambiguous", "wrong_type", "broken"]
VerificationStatus = Literal["found", "global_found", "missing", "broken", "ambiguous", "wrong_type"]
AssetType = Literal["character", "prop", "environment"]


class PreparationEvent(BaseModel):
    type: str
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ProductionReferenceQuery(BaseModel):
    query: str
    expected_type: Optional[AssetType] = None


class ResolvedReference(BaseModel):
    status: ReferenceStatus
    query: str
    expected_type: Optional[AssetType] = None
    asset_id: str = ""
    entity_id: str = ""
    display_name: str = ""
    asset_type: Optional[AssetType] = None
    reference_sheet_id: str = ""
    canonical_tag: str = ""
    identity_tag: str = ""
    bindable_asset_id: str = ""
    notes: str = ""
    candidates: list[str] = Field(default_factory=list)
    verification: VerificationStatus = "missing"
    is_global: bool = False
    approved_sheet: bool = False


class ScaleRelationship(BaseModel):
    subject_a: str
    subject_b: str
    relationship: str = "relative_scale"
    approximate_ratio: str = ""
    subject_a_length: str = ""
    subject_b_length: str = ""
    prompt_language: str = ""


class CameraSpec(BaseModel):
    shot_type: str = ""
    movement: str = ""
    framing: str = ""


class CameraPlan(BaseModel):
    """Semantic camera understanding — never a raw copy of the creator's words."""

    shot_type: str = ""
    movement: str = ""
    framing: str = ""
    target: str = ""
    evolution: str = ""


class DialogueLine(BaseModel):
    """One exact line of dialogue. `line` is verbatim — never paraphrased."""

    speaker: str = ""
    speaker_tag: str = ""
    line: str = ""
    delivery: str = ""
    voice_characteristics: str = ""
    filtering: str = ""
    beat_index: Optional[int] = None


class RevealConstraint(BaseModel):
    """A visibility gate: `subject` stays hidden until a named event/beat."""

    subject: str = ""
    subject_tag: str = ""
    hidden_until: str = ""
    hidden_until_beat: Optional[int] = None
    reveal_order: list[str] = Field(default_factory=list)
    condition: str = ""


class SceneBeat(BaseModel):
    """One ordered on-screen event. Description is Layer B cinematic language."""

    index: int = 0
    kind: str = "action"
    description: str = ""
    subjects: list[str] = Field(default_factory=list)
    camera: str = ""
    hold_seconds: Optional[float] = None
    vfx: str = ""


class TimedBeat(BaseModel):
    start_sec: float = 0.0
    end_sec: float = 0.0
    description: str = ""


class SceneIntentEnvironment(BaseModel):
    name: str = ""
    tag: str = ""
    verified: bool = False
    verification: VerificationStatus = "missing"


class SceneIntentSubject(BaseModel):
    name: str = ""
    tag: str = ""
    role: str = ""
    verified: bool = False
    verification: VerificationStatus = "missing"
    scale: str = ""
    asset_type: Optional[AssetType] = None
    is_global: bool = False


class DirectorSceneIntent(BaseModel):
    """Layer B — director breakdown. Never a copy of the creator's request.

    Universal scene intelligence: arbitrary cinematic scenes, any genre. No
    franchise- or project-specific fields. Runtime metadata (generator,
    duration, aspect, megapixels, batches) lives on SceneProductionSpec only.
    """

    scene_type: str = ""
    purpose: str = ""
    mood: str = ""
    shot_type: str = ""
    environment: SceneIntentEnvironment = Field(default_factory=SceneIntentEnvironment)
    subjects: list[SceneIntentSubject] = Field(default_factory=list)
    scene_beats: list[SceneBeat] = Field(default_factory=list)
    reveals: list[RevealConstraint] = Field(default_factory=list)
    dialogue: list[DialogueLine] = Field(default_factory=list)
    subtitle_policy: str = ""
    exclusions: list[str] = Field(default_factory=list)
    camera_plan: CameraPlan = Field(default_factory=CameraPlan)
    beats: list[str] = Field(default_factory=list)
    timed_beats: list[TimedBeat] = Field(default_factory=list)
    spatial_rules: list[str] = Field(default_factory=list)
    continuity_rules: list[str] = Field(default_factory=list)
    opening_state: str = ""
    vfx_event: str = ""
    entrance: str = ""
    movement: str = ""
    stealth_intent: str = ""
    end_state: str = ""
    scale_summary: str = ""
    action_text: str = ""
    user_request: str = ""
    understanding_source: str = ""


class SceneProductionSpec(BaseModel):
    project_id: str
    production_request_id: str = ""
    scene_id: str = ""
    shot_id: str = ""
    target: Literal["timeline"] = "timeline"
    media_type: Literal["video"] = "video"
    generator_id: str = "minimax-h3"
    duration_seconds: float = 10.0
    aspect_ratio: str = "16:9"
    quality: str = ""
    megapixels: Optional[float] = None
    batch_count: int = 1
    source_user_prompt: str = ""
    scene_intent: str = ""
    director_intent: Optional[DirectorSceneIntent] = None
    camera_intent: str = ""
    continuity_requirements: list[str] = Field(default_factory=list)
    reference_queries: list[ProductionReferenceQuery] = Field(default_factory=list)
    references: list[ResolvedReference] = Field(default_factory=list)
    camera: CameraSpec = Field(default_factory=CameraSpec)
    scale_relationships: list[ScaleRelationship] = Field(default_factory=list)
    compiled_prompt: str = ""
    preparation_state: PreparationState = "parsing"
    follow_up: bool = False


class PreparedSceneResult(BaseModel):
    ok: bool
    spec: SceneProductionSpec
    events: list[PreparationEvent] = Field(default_factory=list)
    compiled_prompt: str = ""
    scene_id: str = ""
    shot_id: str = ""
    scene_index: int = 0
    shot_label: str = ""
    error: str = ""
    error_code: str = ""


class GenerateSceneResult(BaseModel):
    ok: bool
    scene_id: str = ""
    shot_id: str = ""
    job_id: str = ""
    queue_job_id: str = ""
    status: str = ""
    error: str = ""
    error_code: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
