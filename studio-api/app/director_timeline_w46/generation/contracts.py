"""Normalized Timeline video-generation contracts (provider-agnostic)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from ..contracts import _nid, _now

ExecutionType = Literal["local", "api"]
GenerationMode = Literal[
    "text_to_video",
    "image_to_video",
    "start_end_frame",
    "reference",
]
JobLifecycleStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "blocked",
]
DraftPathway = Literal["none", "local_live", "cheap_preview", "native_api_draft"]


class VideoGeneratorCapabilities(BaseModel):
    id: str
    label: str
    executionType: ExecutionType = "local"
    supportsTextToVideo: bool = True
    supportsImageToVideo: bool = False
    supportsStartFrame: bool = False
    supportsEndFrame: bool = False
    supportsMultipleImageReferences: bool = False
    supportsVideoReferences: bool = False
    supportsAudioReferences: bool = False
    maximumReferenceImages: int = 0
    maximumReferenceVideos: int = 0
    maximumReferenceAudio: int = 0
    supportedDurations: list[float] = Field(default_factory=list)
    supportedResolutions: list[str] = Field(default_factory=list)
    supportedAspectRatios: list[str] = Field(default_factory=list)
    supportedFps: list[int] = Field(default_factory=list)
    supportsSeed: bool = True
    supportsNegativePrompt: bool = False
    supportsCameraControls: bool = False
    native_multishot: bool = False
    audio_generation: bool = False
    auto_duration: bool = False
    fast_generation: bool = False
    audio: dict[str, Any] = Field(default_factory=dict)
    executable: bool = True
    notes: str = ""
    draftPathway: DraftPathway = "none"
    supportsQueuedCancel: bool = False
    supportsRunningCancel: bool = False
    finalRequiresNewGeneration: bool = True
    draftResolution: Optional[str] = None
    finalResolution: Optional[str] = None
    supportsImageAndVideoTogether: bool = False


class TimelineGenerationRequest(BaseModel):
    projectId: str
    sceneId: str
    batchBlockId: str
    executionSnapshotId: str
    generatorId: str
    generationMode: GenerationMode = "text_to_video"
    prompt: str = ""
    negativePrompt: Optional[str] = None
    startImageAssetId: Optional[str] = None
    endImageAssetId: Optional[str] = None
    referenceAssetIds: list[str] = Field(default_factory=list)
    videoReferenceAssetId: Optional[str] = None
    videoReferenceTrim: Optional[dict[str, Any]] = None
    duration: float = 5.0
    resolution: Optional[str] = None
    aspectRatio: Optional[str] = None
    seed: Optional[int] = None
    cameraMotion: Optional[str] = None
    providerOptions: dict[str, Any] = Field(default_factory=dict)
    fallbackAllowed: bool = False
    continuityBridgeId: Optional[str] = None
    lastFrameAssetId: Optional[str] = None
    tailAssetId: Optional[str] = None
    continuityStrategy: Optional[str] = None


class ValidationResult(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NormalizedJobSubmission(BaseModel):
    internalJobId: str = Field(default_factory=lambda: _nid("tgen_"))
    providerJobId: Optional[str] = None
    queueJobId: Optional[str] = None
    generatorId: str
    status: JobLifecycleStatus = "queued"
    apiUsed: bool = False
    providerMetadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str = Field(default_factory=_now)


class NormalizedJobStatus(BaseModel):
    internalJobId: str
    providerJobId: Optional[str] = None
    queueJobId: Optional[str] = None
    generatorId: str
    status: JobLifecycleStatus
    progress: float = 0.0
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    apiUsed: bool = False
    providerMetadata: dict[str, Any] = Field(default_factory=dict)


class TimelineGenerationResult(BaseModel):
    internalJobId: str
    providerJobId: Optional[str] = None
    queueJobId: Optional[str] = None
    generatorId: str
    status: JobLifecycleStatus
    progress: float = 1.0
    outputAssetIds: list[str] = Field(default_factory=list)
    duration: Optional[float] = None
    resolution: Optional[str] = None
    apiUsed: bool = False
    providerMetadata: dict[str, Any] = Field(default_factory=dict)
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
