"""M5.2 frozen Voice Environment contracts (Law 16)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

VoiceEnvironmentSource = Literal["manual", "codirector", "scene", "location", "spatial_map"]
VoiceEnvironmentRenderStatus = Literal[
    "queued", "processing", "preview_ready", "completed", "failed"
]
WallaLevel = Literal["subtle", "moderate", "present"]
WallaDistance = Literal["near", "mid", "far"]
WallaBehavior = Literal["steady", "reactive", "intermittent"]


class VoiceEnvironmentTiming(BaseModel):
    """Processing latency contract — required on every preview/render."""

    speechStartOffsetMs: float = 0.0
    processingLatencyMs: float = 0.0
    tailDurationMs: float = 0.0
    dryDurationMs: float = 0.0
    processedDurationMs: float = 0.0


class VoiceEnvironmentProfile(BaseModel):
    id: str
    projectId: str
    characterId: Optional[str] = None
    sceneId: Optional[str] = None
    locationId: Optional[str] = None
    name: str
    spacePreset: str = "small_room"
    customSpacePrompt: Optional[str] = None
    distancePreset: str = "medium_close_up"
    customDistancePrompt: Optional[str] = None
    directionPreset: str = "center"
    customDirectionPrompt: Optional[str] = None
    tonePreset: str = "natural"
    customTonePrompt: Optional[str] = None
    devicePreset: str = "direct"
    customDevicePrompt: Optional[str] = None
    wallaPreset: str = "none"
    wallaLevel: Optional[WallaLevel] = None
    wallaDistance: Optional[WallaDistance] = None
    wallaBehavior: Optional[WallaBehavior] = None
    customWallaPrompt: Optional[str] = None
    source: VoiceEnvironmentSource = "manual"
    createdAt: str = ""
    updatedAt: str = ""


class VoiceEnvironmentRender(BaseModel):
    id: str
    projectId: str
    characterId: str
    performanceRecordId: str
    performanceTakeId: str
    environmentProfileId: str
    dryAudioAssetId: str
    processedAudioAssetId: Optional[str] = None
    roomToneAssetId: Optional[str] = None
    wallaAssetId: Optional[str] = None
    timing: VoiceEnvironmentTiming = Field(default_factory=VoiceEnvironmentTiming)
    status: VoiceEnvironmentRenderStatus = "queued"
    approved: bool = False
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    createdAt: str = ""
    updatedAt: str = ""
    dspPlan: dict[str, Any] = Field(default_factory=dict)


class VoiceEnvironmentRecommendation(BaseModel):
    profileDraft: dict[str, Any] = Field(default_factory=dict)
    spaceLabel: str = ""
    distanceLabel: str = ""
    directionLabel: str = ""
    toneLabel: str = ""
    deviceLabel: str = ""
    wallaLabel: str = ""
    reason: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


class ProfileCreateRequest(BaseModel):
    projectId: str
    characterId: Optional[str] = None
    sceneId: Optional[str] = None
    locationId: Optional[str] = None
    name: str = "Untitled Environment"
    spacePreset: str = "small_room"
    customSpacePrompt: Optional[str] = None
    distancePreset: str = "medium_close_up"
    customDistancePrompt: Optional[str] = None
    directionPreset: str = "center"
    customDirectionPrompt: Optional[str] = None
    tonePreset: str = "natural"
    customTonePrompt: Optional[str] = None
    devicePreset: str = "direct"
    customDevicePrompt: Optional[str] = None
    wallaPreset: str = "none"
    wallaLevel: Optional[WallaLevel] = None
    wallaDistance: Optional[WallaDistance] = None
    wallaBehavior: Optional[WallaBehavior] = None
    customWallaPrompt: Optional[str] = None
    source: VoiceEnvironmentSource = "manual"


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    characterId: Optional[str] = None
    sceneId: Optional[str] = None
    locationId: Optional[str] = None
    spacePreset: Optional[str] = None
    customSpacePrompt: Optional[str] = None
    distancePreset: Optional[str] = None
    customDistancePrompt: Optional[str] = None
    directionPreset: Optional[str] = None
    customDirectionPrompt: Optional[str] = None
    tonePreset: Optional[str] = None
    customTonePrompt: Optional[str] = None
    devicePreset: Optional[str] = None
    customDevicePrompt: Optional[str] = None
    wallaPreset: Optional[str] = None
    wallaLevel: Optional[WallaLevel] = None
    wallaDistance: Optional[WallaDistance] = None
    wallaBehavior: Optional[WallaBehavior] = None
    customWallaPrompt: Optional[str] = None
    source: Optional[VoiceEnvironmentSource] = None


class PreviewRenderRequest(BaseModel):
    projectId: str
    characterId: str
    performanceRecordId: str
    performanceTakeId: str
    environmentProfileId: str
    preview: bool = True


class ApproveRenderRequest(BaseModel):
    approved: bool = True


class ApplyToSceneRequest(BaseModel):
    sceneId: str


class TimelineHandoffRequest(BaseModel):
    sceneId: Optional[str] = None
    useProcessedMix: bool = True


class LipSyncHandoffRequest(BaseModel):
    sceneId: Optional[str] = None
    setSceneAudioAsset: bool = False


class RecommendRequest(BaseModel):
    projectId: str
    characterId: str
    sceneId: Optional[str] = None
    locationId: Optional[str] = None


VOICE_ENVIRONMENT_ERROR_CODES = (
    "VOICE_STUDIO_CHARACTER_REQUIRED",
    "VOICE_IDENTITY_REQUIRED",
    "VOICE_PERFORMANCE_REQUIRED",
    "VOICE_ENVIRONMENT_RUNTIME_NOT_READY",
    "VOICE_ENVIRONMENT_PREVIEW_FAILED",
    "VOICE_ENVIRONMENT_RENDER_FAILED",
    "VOICE_ENVIRONMENT_PROFILE_INVALID",
    "VOICE_ENVIRONMENT_SCENE_NOT_FOUND",
    "VOICE_ENVIRONMENT_SPATIAL_CONTEXT_MISSING",
    "VOICE_ENVIRONMENT_TIMELINE_HANDOFF_FAILED",
    "VOICE_ENVIRONMENT_LIPSYNC_HANDOFF_FAILED",
    "VOICE_ENVIRONMENT_AUDIO_STUDIO_HANDOFF_FAILED",
)
