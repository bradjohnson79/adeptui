from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


EngineName = Literal[
    "auto",
    "minimax-h3",
    "ltx",
    "wan",
    "hunyuan15",
    "hunyuan13b",
    "fal_seedance",
    "fal_kling",
    "fal_veo",
    "fal_runway",
]
PresetName = Literal["draft", "quality"]
JobKind = Literal[
    "render_scene",
    "render_timeline",
    "editor_mix",
    "lipsync",
    "stitch",
    "export",
]
JobStatus = Literal["queued", "running", "done", "failed", "cancelled"]
ContinuityLock = Literal["locked", "unlocked", "inherit_project", "inherit_previous"]


class ContinuityLocks(BaseModel):
    identity: ContinuityLock = "inherit_project"
    wardrobe: ContinuityLock = "inherit_project"
    environment: ContinuityLock = "inherit_project"
    lighting: ContinuityLock = "inherit_project"
    camera: ContinuityLock = "inherit_project"
    props: ContinuityLock = "inherit_project"
    audio_bed: ContinuityLock = "inherit_project"
    motion_style: ContinuityLock = "inherit_project"


class RenderSafetyFlags(BaseModel):
    unload_after_render: bool = False
    vae_tiling: bool = False
    notes: str = ""


class ExecutionPlanOut(BaseModel):
    vram_gb: int
    label: str
    width: int
    height: int
    fps: int
    steps: int
    max_frames: int
    max_duration_sec: float
    image_tool_size: int
    lipsync_size: int
    lipsync_steps: int
    assist_chunk_frames: int
    summary: str
    assists: list[str] = Field(default_factory=list)
    clamped: bool = False
    notes: str = ""
    live_text: str = ""
    safety: RenderSafetyFlags = Field(default_factory=RenderSafetyFlags)
    aspect_ratio: str = "16:9"
    fps_mode: str = "auto"
    engine_warnings: list[str] = Field(default_factory=list)
    preview_caps: dict[str, Any] = Field(default_factory=dict)


class EngineRecommendOut(BaseModel):
    engineId: str
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    local: bool = True
    vram_tier: int = 32
    profile_engine: str = "ltx"


class TimelineSceneProposal(BaseModel):
    name: str = "Scene"
    prompt: str = ""
    duration_sec: float = 5.0
    engine: Optional[EngineName] = None
    camera_note: str = ""


class TimelineProposalOut(BaseModel):
    summary: str = ""
    scenes: list[TimelineSceneProposal] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TimelineProposeRequest(BaseModel):
    brief: str = ""
    model: Optional[str] = None


class TimelineApplyRequest(BaseModel):
    scenes: list[TimelineSceneProposal] = Field(default_factory=list)
    replace_existing: bool = True
    enqueue_render: bool = False


class AssetOut(BaseModel):
    id: str
    project_id: str
    tag: str
    kind: str
    filename: str
    path: str
    comfy_name: str
    scope: str = "project"
    shared_project_ids_json: str = "[]"
    labels_json: str = "[]"
    prompt_meta_json: str = "{}"
    parent_asset_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SceneIn(BaseModel):
    name: str = "Scene"
    #: Short description of the scene for humans and for Co-Director. Not generation input.
    summary: str = ""
    engine: EngineName = "minimax-h3"
    prompt: str = ""
    duration_sec: float = 5.0
    start_asset_id: Optional[str] = None
    middle_asset_id: Optional[str] = None
    end_asset_id: Optional[str] = None
    audio_asset_id: Optional[str] = None
    lipsync_enabled: bool = False
    lipsync_audio_asset_id: Optional[str] = None
    lipsync_tracks_json: Optional[str] = None
    director_json: Optional[str] = None
    continuity_json: Optional[str] = None
    camera_note: str = ""
    seed: int = -1
    aspect_ratio: str = "16:9"
    width: int = 0
    height: int = 0
    fps_mode: str = "auto"
    fps: int = 0


class SceneOut(BaseModel):
    id: str
    project_id: str
    index: int
    name: str = "Scene"
    summary: str = ""
    engine: EngineName = "minimax-h3"
    prompt: str = ""
    duration_sec: float = 5.0
    start_asset_id: Optional[str] = None
    middle_asset_id: Optional[str] = None
    end_asset_id: Optional[str] = None
    audio_asset_id: Optional[str] = None
    lipsync_enabled: bool = False
    lipsync_audio_asset_id: Optional[str] = None
    lipsync_tracks_json: str = ""
    director_json: str = ""
    continuity_json: str = ""
    camera_note: str = ""
    seed: int = -1
    aspect_ratio: str = "16:9"
    width: int = 0
    height: int = 0
    fps_mode: str = "auto"
    fps: int = 0
    output_path: Optional[str] = None
    lipsync_output_path: Optional[str] = None

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):  # type: ignore[override]
        if hasattr(obj, "lipsync_enabled") and not isinstance(obj, dict):
            data = {
                "id": obj.id,
                "project_id": obj.project_id,
                "index": obj.index,
                "name": obj.name,
                "summary": getattr(obj, "summary", "") or "",
                "engine": obj.engine,
                "prompt": obj.prompt,
                "duration_sec": obj.duration_sec,
                "start_asset_id": obj.start_asset_id,
                "middle_asset_id": obj.middle_asset_id,
                "end_asset_id": obj.end_asset_id,
                "audio_asset_id": obj.audio_asset_id,
                "lipsync_enabled": bool(obj.lipsync_enabled),
                "lipsync_audio_asset_id": obj.lipsync_audio_asset_id,
                "lipsync_tracks_json": getattr(obj, "lipsync_tracks_json", "") or "",
                "director_json": getattr(obj, "director_json", "") or "",
                "continuity_json": getattr(obj, "continuity_json", "") or "",
                "camera_note": obj.camera_note,
                "seed": obj.seed,
                "aspect_ratio": getattr(obj, "aspect_ratio", None) or "16:9",
                "width": int(getattr(obj, "width", 0) or 0),
                "height": int(getattr(obj, "height", 0) or 0),
                "fps_mode": getattr(obj, "fps_mode", None) or "auto",
                "fps": int(getattr(obj, "fps", 0) or 0),
                "output_path": obj.output_path,
                "lipsync_output_path": obj.lipsync_output_path,
            }
            return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class ProjectCreate(BaseModel):
    name: str
    engine_default: EngineName = "minimax-h3"
    global_prompt: str = ""
    negative_prompt: str = "blurry, low quality, watermark"
    width: int = 1280
    height: int = 720
    fps: int = 24
    seed: int = -1
    preset: PresetName = "quality"
    vram_gb: int = 32
    # M3.1a Project Types — when templates_presets_v1 is on, profile drives dims/hierarchy.
    primary_project_type: Optional[str] = None
    project_traits: list[str] = Field(default_factory=list)
    profile_overrides: dict[str, Any] = Field(default_factory=dict)
    # Project-level production preferences
    storyboard_style: Optional[str] = None
    preferred_video_generator: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Project name is required.")
        return trimmed


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    engine_default: Optional[EngineName] = None
    global_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    seed: Optional[int] = None
    preset: Optional[PresetName] = None
    vram_gb: Optional[int] = None
    spatial_map_json: Optional[str] = None
    render_safety_json: Optional[str] = None
    learning_json: Optional[str] = None
    learning_enabled_json: Optional[str] = None
    preview_settings_json: Optional[str] = None
    description: Optional[str] = None
    company: Optional[str] = None
    director_name: Optional[str] = None
    version: Optional[str] = None
    tags_json: Optional[str] = None
    archived: Optional[int] = None
    defaults_json: Optional[str] = None
    settings_json: Optional[str] = None
    primary_project_type: Optional[str] = None
    project_traits_json: Optional[str] = None
    resolved_profile_json: Optional[str] = None
    project_type_version: Optional[int] = None
    storyboard_style: Optional[str] = None
    preferred_video_generator: Optional[str] = None
    apply_vram_profile: bool = False


class ProjectOut(BaseModel):
    id: str
    name: str
    engine_default: str
    global_prompt: str
    negative_prompt: str
    width: int
    height: int
    fps: int
    seed: int
    preset: str
    vram_gb: int = 32
    spatial_map_json: str
    render_safety_json: str = ""
    learning_json: str = ""
    learning_enabled_json: str = ""
    preview_settings_json: str = ""
    description: str = ""
    company: str = ""
    director_name: str = ""
    version: str = "1.0"
    tags_json: str = "[]"
    archived: int = 0
    defaults_json: str = ""
    settings_json: str = ""
    primary_project_type: str = "custom"
    project_traits_json: str = "[]"
    resolved_profile_json: str = "{}"
    project_type_version: int = 1
    created_at: datetime
    updated_at: datetime
    scenes: list[SceneOut] = Field(default_factory=list)
    assets: list[AssetOut] = Field(default_factory=list)
    # Lightweight summary for home library cards (avoids N+1 dashboard calls)
    scene_count: int = 0
    asset_count: int = 0
    render_pct: int = 0
    cover_asset_id: Optional[str] = None
    cover_kind: Optional[str] = None  # "image" | "video" when cover_asset_id is set
    storyboard_style: Optional[str] = None
    preferred_video_generator: Optional[str] = None
    status_label: str = "Active"
    # Project password protection (never include hash)
    password_protected: bool = False
    password_locked: bool = False

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: str
    project_id: str
    scene_id: Optional[str]
    kind: str
    status: str
    progress: float
    message: str
    stage: str = ""
    preview_json: str = ""
    params_json: str = ""
    history_json: str = ""
    comfy_prompt_id: Optional[str]
    output_path: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VramProfileOut(BaseModel):
    vram_gb: int
    label: str
    width: int
    height: int
    fps: int
    max_duration_sec: float
    max_frames: int
    steps_draft: int
    steps_quality: int
    image_tool_size: int
    lipsync_size: int
    lipsync_steps: int
    assist_chunk_frames: int
    recommended_engine: str
    summary: str
    assists: list[str] = Field(default_factory=list)


class VramDetectOut(BaseModel):
    detected_gb: Optional[int] = None
    tier: Optional[int] = None
    message: str = ""


class GpuDeviceOut(BaseModel):
    index: int = 0
    name: str = ""
    driver_version: str = ""
    memory_total_mib: Optional[float] = None
    memory_used_mib: Optional[float] = None
    memory_free_mib: Optional[float] = None
    memory_used_pct: Optional[float] = None
    temperature_c: Optional[float] = None
    utilization_gpu_pct: Optional[float] = None
    utilization_memory_pct: Optional[float] = None
    power_draw_w: Optional[float] = None
    fan_speed_pct: Optional[float] = None


class GpuStatsOut(BaseModel):
    ok: bool
    message: str = ""
    gpus: list[GpuDeviceOut] = Field(default_factory=list)
    primary_index: int = 0
    recommended_tier: Optional[int] = None


class FalKeyStatus(BaseModel):
    configured: bool
    hint: Optional[str] = None
    fingerprint: Optional[str] = None
    # missing | unverified | verified | invalid — result of the last live fal probe.
    state: str = "missing"
    verified: Optional[bool] = None
    verifiedAt: Optional[str] = None
    message: str = ""


class FalKeyUpdate(BaseModel):
    api_key: str = ""


class FalUsageOut(BaseModel):
    ok: bool = False
    configured: bool = False
    username: Optional[str] = None
    balance: Optional[float] = None
    currency: str = "USD"
    period_days: int = 30
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    usage_units: float = 0.0
    usage_unit_label: str = "units"
    spend: float = 0.0
    request_count: int = 0
    top_endpoints: list[dict[str, Any]] = Field(default_factory=list)
    manage_url: str = "https://fal.ai/dashboard/usage"
    billing_url: str = "https://fal.ai/dashboard/billing"
    keys_url: str = "https://fal.ai/dashboard/keys"
    login_url: str = "https://fal.ai/login"
    message: str = ""
    needs_admin_key: bool = False


class FalModelOut(BaseModel):
    engine: str
    label: str
    provider: str
    model_id: str
    mode: str
    media_type: str = "video"
    durations: list[int] = Field(default_factory=list)
    default_duration: int = 5
    supports_end_image: bool = False
    description: str = ""


class EngineOptionOut(BaseModel):
    id: str
    label: str
    group: str


class RenderRequest(BaseModel):
    """POST /api/projects/{id}/render body.

    kind:
      - scene: queue render_scene (requires scene_id)
      - shot: queue render_shot (shot-scoped; requires scene_id)
      - timeline: queue render_timeline (reuse existing scene outputs when present, then stitch)
      - batch_timeline: regenerate all scenes then stitch
      - editor_mix: mux Editor music/sfx/dialogue/ambience onto a primary video
        (optional primary_video_path; else latest timeline / editor video / scene output)
    """

    scene_id: Optional[str] = None
    retake: bool = False
    kind: Literal["scene", "shot", "timeline", "batch_timeline", "editor_mix"] = "timeline"
    reference_method: Optional[str] = None
    sheet_id: Optional[str] = None
    strength_preset: Optional[str] = None
    strength: Optional[float] = None
    ingredients_ic_lora: Optional[bool] = None
    # Shared LoRA registry selection ({loraId, name, strength}); None = baseline.
    lora: Optional[dict] = None
    # M3.0h local-first provenance / paid-fallback gates
    providerPreference: Optional[str] = "local"
    paidFallbackApproved: bool = False
    startFrameModel: Optional[str] = None
    generate_audio: Optional[bool] = None
    # M3.2g Phase 6 — Editor final mix primary video override
    primary_video_path: Optional[str] = None


class LipSyncRequest(BaseModel):
    scene_id: str
    audio_asset_id: Optional[str] = None
    prefer_still_face: bool = False
    face_asset_id: Optional[str] = None
    direct_latentsync: bool = False


class SpatialMapPoint(BaseModel):
    id: str
    kind: Literal["camera", "prop", "wall", "marker"] = "marker"
    x: float
    y: float
    label: str = ""
    asset_id: Optional[str] = None
    rotation: float = 0.0


class SpatialMap(BaseModel):
    width: int = 1000
    height: int = 700
    background_asset_id: Optional[str] = None
    points: list[SpatialMapPoint] = Field(default_factory=list)
    notes: str = ""


class HealthOut(BaseModel):
    ok: bool
    comfy_reachable: bool
    comfy: dict[str, Any] = Field(default_factory=dict)
    #: Human-readable labels for REQUIRED gaps only, kept for existing consumers.
    missing_models: list[str] = Field(default_factory=list)
    #: Setup/Source Manager component ids for the same REQUIRED gaps.
    missing_model_component_ids: list[str] = Field(default_factory=list)
    #: Human-readable labels for optional/generator-specific gaps (e.g. Krea 2).
    missing_optional_models: list[str] = Field(default_factory=list)
    #: Optional/generator-specific component ids; never mixed into missing_model_component_ids.
    missing_optional_model_component_ids: list[str] = Field(default_factory=list)
    comfy_status: str = "unknown"
    comfy_version: Optional[str] = None
    node_catalog_available: bool = False
    reason_code: Optional[str] = None
    recommended_action: Optional[str] = None
    message: str = ""
    #: Operator visibility for M2.4.1 (no secrets).
    operator: dict[str, Any] = Field(default_factory=dict)
    #: Short git SHA of the API process at start. Missing on stale pre-guard processes.
    apiRevision: Optional[str] = None
    #: UTC timestamp when this API process started.
    apiStartedAt: Optional[str] = None
    #: Routes this process must expose. SHA-alone is not currency.
    routeContract: list[str] = Field(default_factory=list)


class TagResolveOut(BaseModel):
    prompt: str
    resolved_tags: dict[str, str]
    missing_tags: list[str]
    attached_asset_ids: list[str]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class AssistantChatRequest(BaseModel):
    messages: list[ChatMessage]
    project_id: Optional[str] = None
    scene_id: Optional[str] = None
    model: Optional[str] = None
    mode: Literal["chat", "prompt", "guide", "setup"] = "chat"


class SetupPromptSegmentOut(BaseModel):
    start: float = 0.0
    length: float = 5.0
    text: str = ""


class SetupSfxClipOut(BaseModel):
    ref: str
    start: float = 0.0
    length: float = 1.0
    label: str = "SFX"


class SceneSetupOut(BaseModel):
    summary: str = ""
    scene_name: Optional[str] = None
    engine: Optional[
        Literal[
            "minimax-h3",
            "ltx",
            "wan",
            "hunyuan15",
            "hunyuan13b",
            "fal_seedance",
            "fal_kling",
            "fal_veo",
            "fal_runway",
        ]
    ] = None
    duration_sec: Optional[float] = None
    media_mode: Optional[Literal["image", "video"]] = None
    global_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    preset: Optional[Literal["draft", "quality"]] = None
    prompt: Optional[str] = None
    prompt_segments: Optional[list[SetupPromptSegmentOut]] = None
    image_slots: Optional[dict[str, Optional[str]]] = None
    audio_ref: Optional[str] = None
    sfx: Optional[list[SetupSfxClipOut]] = None


class AssistantChatResponse(BaseModel):
    reply: str
    model: str
    suggested_prompt: Optional[str] = None
    scene_setup: Optional[SceneSetupOut] = None


class AssistantApplySetupRequest(BaseModel):
    project_id: str
    scene_id: str
    setup: SceneSetupOut


class AssistantApplySetupResponse(BaseModel):
    ok: bool
    applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scene_id: str
    project_id: str


class AssistantHealth(BaseModel):
    ok: bool
    ollama_reachable: bool
    model: str
    available_models: list[str] = Field(default_factory=list)
    message: str = ""


class ImageToolRequest(BaseModel):
    source_asset_id: str
    character_name: str = "character"
    seed: int = -1
    width: int = 1024
    height: int = 1024
    # multi_angle only: optional custom prompts for up to 3 angles
    angle_prompts: list[str] = Field(default_factory=list)
    extra_prompt: str = ""


class ImageToolResultOut(BaseModel):
    job_id: str
    status: str
    message: str = ""

