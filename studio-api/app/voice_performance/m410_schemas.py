"""Pydantic schemas for M4.10 voice performance persistence."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .emotion_presets import SUPPORTED_VECTORS, normalize_mix

DirectionMode = Literal["codirector", "manual"]
TakeStatus = Literal["queued", "running", "completed", "failed", "cancelled", "approved", "rejected"]


def validate_emotion_vector(value: dict[str, float] | None) -> dict[str, float]:
    if value is None:
        return {}
    normalized_keys = {str(k).strip().lower(): v for k, v in value.items()}
    bad_keys = [key for key in normalized_keys if key not in SUPPORTED_VECTORS and key != "hate"]
    if bad_keys:
        raise ValueError(f"Unsupported emotion keys: {', '.join(sorted(bad_keys))}")
    try:
        normalized = normalize_mix({str(k): float(v) for k, v in normalized_keys.items()})
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Emotion vector values must be numeric.") from exc
    if value and not normalized:
        raise ValueError("Emotion vector must contain at least one supported non-negative value.")
    return normalized


class RuntimeInstallBody(BaseModel):
    confirm: bool = False
    confirm_download_models: bool = Field(default=False, alias="confirmDownloadModels")

    model_config = {"populate_by_name": True}


class EmotionPresetOut(BaseModel):
    id: str
    name: str
    emotionVector: dict[str, float] = Field(default_factory=dict)
    intensity: str
    delivery: str
    pacing: str
    breath: str
    notes: str
    summary: str


class VoicePerformanceTakeOut(BaseModel):
    id: str
    recordId: str
    takeNumber: int
    label: str
    jobId: Optional[str] = None
    audioAssetId: Optional[str] = None
    durationMs: Optional[int] = None
    status: TakeStatus
    directionSnapshot: dict[str, Any] = Field(default_factory=dict)
    generatedAt: Optional[str] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    createdAt: str = ""
    updatedAt: str = ""


class VoicePerformanceRecordCreate(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    scriptDocumentId: Optional[str] = None
    scriptElementId: Optional[str] = None
    characterId: str
    voiceIdentityId: str
    voiceIdentityVersion: Optional[str] = None
    dialogueText: str
    language: str = "en"
    directionMode: DirectionMode = "codirector"
    performancePlan: dict[str, Any] = Field(default_factory=dict)
    emotionSource: Optional[str] = None
    emotionVector: dict[str, float] = Field(default_factory=dict)
    emotionalReferenceAssetId: Optional[str] = None
    emotionalReferenceStrength: Optional[float] = None
    providerId: str = "index-tts2-local"
    providerVersion: Optional[str] = None
    modelRevision: Optional[str] = None
    approvedTakeId: Optional[str] = None
    manualPlan: dict[str, Any] = Field(default_factory=dict)
    codirectorPlan: dict[str, Any] = Field(default_factory=dict)
    sceneArcId: Optional[str] = None
    timelineLinkage: dict[str, Any] = Field(default_factory=dict)
    lipsyncLinkage: dict[str, Any] = Field(default_factory=dict)
    consentAck: dict[str, Any] = Field(default_factory=dict)

    @field_validator("emotionVector")
    @classmethod
    def _validate_emotion_vector(cls, value: dict[str, float]) -> dict[str, float]:
        return validate_emotion_vector(value)

    @field_validator("emotionalReferenceStrength")
    @classmethod
    def _validate_strength(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return max(0.0, min(1.0, float(value)))


class VoicePerformanceRecordOut(VoicePerformanceRecordCreate):
    id: str
    createdAt: str
    updatedAt: str
    takes: list[VoicePerformanceTakeOut] = Field(default_factory=list)


class CodirectorPlanRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class PerformancePlanPatchBody(BaseModel):
    performancePlan: dict[str, Any]
    mode: Optional[DirectionMode] = None
    emotionSource: Optional[str] = None
    emotionVector: Optional[dict[str, float]] = None

    @field_validator("emotionVector")
    @classmethod
    def _validate_patch_vector(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is None:
            return None
        return validate_emotion_vector(value)


class DirectionModeBody(BaseModel):
    directionMode: DirectionMode
    performancePlan: dict[str, Any] = Field(default_factory=dict)


class GenerateTakesBody(BaseModel):
    count: int = 1
    labels: list[str] = Field(default_factory=list)

    @field_validator("count")
    @classmethod
    def _validate_count(cls, value: int) -> int:
        return max(1, min(8, int(value)))


class ApproveTakeBody(BaseModel):
    approvedBy: str = "owner"


class CompareTakesBody(BaseModel):
    takeIds: list[str] = Field(default_factory=list)


class TimelinePlacementBody(BaseModel):
    trackId: str = "dialogue-main"
    startMs: int = 0
    confirmReplace: bool = False


class LipsyncBody(BaseModel):
    confirm: bool = True
    setSceneAudioAsset: bool = True


class SceneBatchItem(BaseModel):
    sceneId: Optional[str] = None
    scriptDocumentId: Optional[str] = None
    scriptElementId: Optional[str] = None
    characterId: str
    voiceIdentityId: str
    voiceIdentityVersion: Optional[str] = None
    dialogueText: str
    language: str = "en"
    directionMode: DirectionMode = "codirector"
    sceneArcId: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)


class SceneBatchBody(BaseModel):
    projectId: str
    items: list[SceneBatchItem] = Field(default_factory=list)


class RecordListOut(BaseModel):
    projectId: str
    records: list[VoicePerformanceRecordOut] = Field(default_factory=list)


class TakeListOut(BaseModel):
    recordId: str
    approvedTakeId: Optional[str] = None
    takes: list[VoicePerformanceTakeOut] = Field(default_factory=list)


class RuntimeStatusOut(BaseModel):
    ok: bool
    providerId: str
    providerVersion: str
    installed: bool
    ready: bool
    availableOnDisk: bool
    modelRevision: Optional[str] = None
    runtimeRoot: str
    manifestPath: str
    message: str
    mock: bool = False
