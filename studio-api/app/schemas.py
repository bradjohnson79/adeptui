from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


EngineName = Literal["ltx", "wan", "fal_seedance", "fal_kling", "fal_veo", "fal_runway"]
PresetName = Literal["draft", "quality"]
JobKind = Literal["render_scene", "render_timeline", "lipsync", "stitch", "export"]
JobStatus = Literal["queued", "running", "done", "failed", "cancelled"]


class AssetOut(BaseModel):
    id: str
    project_id: str
    tag: str
    kind: str
    filename: str
    path: str
    comfy_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class SceneIn(BaseModel):
    name: str = "Scene"
    engine: EngineName = "ltx"
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
    camera_note: str = ""
    seed: int = -1


class SceneOut(BaseModel):
    id: str
    project_id: str
    index: int
    name: str = "Scene"
    engine: EngineName = "ltx"
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
    camera_note: str = ""
    seed: int = -1
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
                "camera_note": obj.camera_note,
                "seed": obj.seed,
                "output_path": obj.output_path,
                "lipsync_output_path": obj.lipsync_output_path,
            }
            return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class ProjectCreate(BaseModel):
    name: str = "Untitled Project"
    engine_default: EngineName = "ltx"
    global_prompt: str = ""
    negative_prompt: str = "blurry, low quality, watermark"
    width: int = 1280
    height: int = 720
    fps: int = 24
    seed: int = -1
    preset: PresetName = "quality"
    vram_gb: int = 32


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
    created_at: datetime
    updated_at: datetime
    scenes: list[SceneOut] = Field(default_factory=list)
    assets: list[AssetOut] = Field(default_factory=list)

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
    durations: list[int] = Field(default_factory=list)
    default_duration: int = 5
    supports_end_image: bool = False
    description: str = ""


class EngineOptionOut(BaseModel):
    id: str
    label: str
    group: str


class JobOut(BaseModel):
    id: str
    project_id: str
    scene_id: Optional[str]
    kind: str
    status: str
    progress: float
    message: str
    comfy_prompt_id: Optional[str]
    output_path: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RenderRequest(BaseModel):
    scene_id: Optional[str] = None
    retake: bool = False
    kind: Literal["scene", "timeline"] = "timeline"


class LipSyncRequest(BaseModel):
    scene_id: str
    audio_asset_id: Optional[str] = None


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
    missing_models: list[str] = Field(default_factory=list)
    message: str = ""


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
    engine: Optional[Literal["ltx", "wan", "fal_seedance", "fal_kling", "fal_veo", "fal_runway"]] = None
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

