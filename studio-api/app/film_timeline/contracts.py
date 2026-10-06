"""Film Timeline persistence model.

One document per scene. Provider continuation handles live on the segment
that produced them. They are not a second Timeline authority.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

TrackType = Literal["video", "audio", "sfx"]
SegmentStatus = Literal[
    "empty",
    "queued",
    "generating",
    "processing",
    "downloading",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
]
ReferenceType = Literal[
    "character",
    "prop",
    "environment",
    "first_frame",
    "storyboard",
    "image",
    "video",
    "audio",
    "other",
]
CompositionRole = Literal["generated", "source", "retake"]
SegmentOrigin = Literal["generated", "library"]


def _nid(prefix: str) -> str:
    return f"{prefix}{uuid4().hex[:12]}"


class ReferenceAsset(BaseModel):
    id: str = Field(default_factory=lambda: _nid("ref_"))
    type: ReferenceType = "other"
    assetId: str = ""
    label: str = ""
    tag: str = ""
    role: str = ""
    source: str = ""
    inherited: bool = False


class Segment(BaseModel):
    id: str = Field(default_factory=lambda: _nid("seg_"))
    order: int = 0
    durationSec: float = 10.0
    requestedDurationSec: float = 10.0
    status: SegmentStatus = "empty"
    timedPrompt: str = ""
    generatorId: Optional[str] = None
    assetId: Optional[str] = None
    error: Optional[str] = None
    continuationStrategy: Optional[str] = None
    firstFrameAssetId: Optional[str] = None
    lastFrameAssetId: Optional[str] = None
    # Visible range inside assetId. trimOutSec null means the piece uses durationSec from trimInSec.
    trimInSec: float = 0.0
    trimOutSec: Optional[float] = None
    compositionRole: CompositionRole = "generated"
    sourceSegmentId: Optional[str] = None
    origin: SegmentOrigin = "generated"
    # Stable creator identity. Assigned once at creation. Not track position.
    shotNumber: int = 0
    # Provider job dump and continuation handle. Not a Timeline owner.
    generationMetadata: dict[str, Any] = Field(default_factory=dict)


class ShotState(BaseModel):
    """The only persistent continuity authority for one shot."""

    shotId: str = ""
    sceneId: str = ""
    modelId: Optional[str] = None
    firstFrameAssetId: Optional[str] = None
    references: list[ReferenceAsset] = Field(default_factory=list)
    promptHistory: list[str] = Field(default_factory=list)
    segmentIds: list[str] = Field(default_factory=list)
    priorSegmentId: Optional[str] = None
    observations: list[str] = Field(default_factory=list)
    stitchAssetId: Optional[str] = None
    stitchStatus: str = "none"
    stitchError: Optional[str] = None
    # Segment ids the current stitch actually covers, in order. B-F2: a stitch
    # whose included set != the completed set is stale, whatever set 'ready'.
    stitchSegmentIds: list[str] = Field(default_factory=list)
    # Model-facing transform of the human Timed Prompt. Never replaces it.
    modelPrompt: str = ""
    # Model-specific output settings (H3 megapixels, LTX quality, etc.)
    resolvedGeneration: dict[str, Any] = Field(default_factory=dict)
    # Spoken language for this shot. Not inferred from generated audio.
    spokenLanguage: str = "en"
    spokenLanguageCustom: str = ""
    # Who speaks. Native Model lets the video generator speak. Character Voice
    # uses the character's saved voice. The voice binding itself stays on the character.
    dialogueAuthority: str = "native_model"

    @model_validator(mode="after")
    def _spoken_language_authority(self):
        from .spoken_language import normalize

        spoken = normalize(self.spokenLanguage, self.spokenLanguageCustom)
        self.spokenLanguage = spoken.code
        self.spokenLanguageCustom = spoken.custom
        from .dialogue_authority import normalize_mode

        self.dialogueAuthority = normalize_mode(self.dialogueAuthority)
        return self


class Shot(BaseModel):
    id: str = Field(default_factory=lambda: _nid("shot_"))
    sceneId: str = ""
    name: str = "Shot 01"
    order: int = 0
    durationSec: float = 10.0
    timedPrompt: str = ""
    status: str = "draft"
    state: ShotState = Field(default_factory=ShotState)
    segments: list[Segment] = Field(default_factory=list)
    # Durations the current Generate request still owes, in order.
    generationPlan: list[float] = Field(default_factory=list)


class MediaClip(BaseModel):
    id: str = Field(default_factory=lambda: _nid("clip_"))
    trackType: TrackType = "audio"
    role: str = ""
    assetId: str = ""

    @model_validator(mode="before")
    @classmethod
    def _audio_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        track = str(data.get("trackType") or "")
        if track in {"voice", "dialogue", "narration", "music", "ambience"}:
            data = dict(data)
            data["role"] = str(data.get("role") or track)
            data["trackType"] = "audio"
        return data
    label: str = ""
    startSec: float = 0.0
    durationSec: float = 0.0
    trimInSec: float = 0.0
    trimOutSec: Optional[float] = None
    volume: float = 1.0
    fadeInSec: float = 0.0
    fadeOutSec: float = 0.0
    muted: bool = False
    shotId: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingPlacement(BaseModel):
    """Audio that could not be routed without a lane choice."""

    id: str = Field(default_factory=lambda: _nid("pend_"))
    assetId: str = ""
    label: str = ""
    reason: str = "ambiguous_audio"


class FilmTimeline(BaseModel):
    version: int = 1
    projectId: str = ""
    sceneId: str = ""
    name: str = "Scene"
    generatorId: Optional[str] = None
    references: list[ReferenceAsset] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)
    audio: list[MediaClip] = Field(default_factory=list)
    sfx: list[MediaClip] = Field(default_factory=list)
    videoClips: list[MediaClip] = Field(default_factory=list)
    publishedAssetId: Optional[str] = None
    # Stitch asset that the published picture was copied from. Send to MAGI
    # stays closed when the current ready stitch is a different id.
    publishedSourceAssetId: Optional[str] = None
    publishVersion: int = 0
    upscaledAssetId: Optional[str] = None
    # High-water mark for shotNumber. Never decreases, so a deleted number is not reused.
    highestShotNumber: int = 0

    @model_validator(mode="before")
    @classmethod
    def _fold_legacy_lanes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        audio = [item for item in (data.get("audio") or []) if isinstance(item, dict)]
        for lane, role in (("voice", "voice"), ("music", "music"), ("ambience", "ambience")):
            for item in data.get(lane) or []:
                if not isinstance(item, dict):
                    continue
                clip = dict(item)
                clip["trackType"] = "audio"
                clip["role"] = str(clip.get("role") or role)
                audio.append(clip)
        data["audio"] = audio
        for lane in ("voice", "music", "ambience"):
            data.pop(lane, None)
        return data
    pendingPlacements: list[PendingPlacement] = Field(default_factory=list)
    migratedFromMaster: bool = False
    migration: Optional[dict[str, Any]] = None
    renderSessionId: Optional[str] = None


class AddToTimelineRequest(BaseModel):
    mediaType: str
    assetId: str
    assetUrl: Optional[str] = None
    targetTrackType: Optional[str] = None
    startTime: float = 0.0
    durationSec: Optional[float] = None
    shotId: Optional[str] = None
    label: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
