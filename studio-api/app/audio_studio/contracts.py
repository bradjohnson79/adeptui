"""Frozen M42 W45 shared contracts — see docs/release-gate/m42/M42_W45_SHARED_CONTRACTS.md."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

StemRole = Literal[
    "Drums", "Bass", "Vocals", "Pads", "FX", "Lead", "Strings", "Percussion", "Custom"
]
CandidateStatus = Literal["ready", "failed", "selected", "approved", "archived"]
AudioKind = Literal["music", "sfx", "ambience"]


class AudioCreativeBrief(BaseModel):
    project_id: str
    scene_id: Optional[str] = None
    shot_id: Optional[str] = None
    category: str = "music"
    prompt: str = ""
    duration_seconds: Optional[float] = 20.0
    mood: list[str] = Field(default_factory=list)
    intensity: Optional[str] = None
    tempo: Optional[int] = None
    instrumentation: list[str] = Field(default_factory=list)
    loop_required: bool = False
    start_behavior: Optional[str] = None
    end_behavior: Optional[str] = None
    reference_asset_ids: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    genre: Optional[str] = None
    energy: Optional[str] = None


class MusicIntent(BaseModel):
    brief: AudioCreativeBrief
    kind: Literal["music"] = "music"


class SoundEffectIntent(BaseModel):
    brief: AudioCreativeBrief
    kind: Literal["sfx"] = "sfx"


class AmbienceIntent(BaseModel):
    brief: AudioCreativeBrief
    kind: Literal["ambience"] = "ambience"


class AudioGenerationJob(BaseModel):
    id: str
    project_id: str
    intent_id: str = ""
    provider: str = ""
    runtime: str = ""
    status: str = "queued"
    attempt_index: int = 0
    error: Optional[str] = None
    output_asset_id: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None


class AudioCandidate(BaseModel):
    id: str
    batch_id: str
    name: str
    asset_id: Optional[str] = None
    status: CandidateStatus = "ready"
    summary: str = ""
    provider: str = ""
    runtime: str = ""
    parent_candidate_id: Optional[str] = None
    error: Optional[str] = None
    path: Optional[str] = None


class AudioCandidateBatch(BaseModel):
    id: str
    project_id: str
    method: Literal["music", "sfx", "ambience", "similar"] = "music"
    brief_snapshot: dict[str, Any] = Field(default_factory=dict)
    candidate_ids: list[str] = Field(default_factory=list)
    parent_candidate_id: Optional[str] = None
    created_at: str = ""
    candidates: list[AudioCandidate] = Field(default_factory=list)


class AudioApprovalDecision(BaseModel):
    candidate_id: str
    approved: bool
    approved_by: str = "owner"
    approved_at: str = ""


class MusicStem(BaseModel):
    role: StemRole
    asset_id: str
    muted: bool = False


class MusicStemSet(BaseModel):
    parent_version_id: str
    stems: list[MusicStem] = Field(default_factory=list)
    stems_supported: bool = False


class AudioVersionLineage(BaseModel):
    version_id: str
    parent_version_id: Optional[str] = None
    asset_id: str
    stems: Optional[MusicStemSet] = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class AudioAssetMetadata(BaseModel):
    asset_id: str
    role: str
    project_id: str
    category: str = ""
    provider: str = ""
    runtime: str = ""
    duration_seconds: Optional[float] = None
    approval_status: str = "draft"
    version_id: Optional[str] = None
    batch_id: Optional[str] = None


class TimelineAudioClip(BaseModel):
    clip_id: str
    asset_id: str
    asset_version_id: Optional[str] = None
    category: str = "music"
    provider: str = ""
    runtime: str = ""
    source_intent_id: Optional[str] = None
    start_time: float = 0.0
    duration: float = 0.0
    gain: float = 1.0
    pan: float = 0.0
    mute: bool = False
    solo: bool = False
    loop: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    crossfade_to_clip_id: Optional[str] = None
    approval_status: str = "draft"
    provenance_id: Optional[str] = None


class AudioPlacementIntent(BaseModel):
    project_id: str
    asset_id: str
    category: str = "music"
    scene_id: Optional[str] = None
    start_ms: int = 0
    loop: bool = False
    track: str = "music"


class AudioMixClipState(BaseModel):
    clip_id: str
    gain: float = 1.0
    pan: float = 0.0
    mute: bool = False
    solo: bool = False
    normalize: bool = False
    fade_in_ms: float = 0.0
    fade_out_ms: float = 0.0
    crossfade_to_clip_id: Optional[str] = None
    track_route: str = "master"
    loop: bool = False
    peak: Optional[float] = None
    lufs: Optional[float] = None


class AudioMasterOutput(BaseModel):
    gain: float = 1.0
    peak: Optional[float] = None
    lufs_integrated: Optional[float] = None
    lufs_short_term: Optional[float] = None


class HostedAudioProviderMapping(BaseModel):
    provider: Literal["kie.ai", "wavespeed.ai", "fal.ai"]
    status: str = "Unavailable"
    stems_supported: bool = False
    modalities: list[str] = Field(default_factory=lambda: ["audio"])
    message: str = ""


class LocalAudioRuntimeMapping(BaseModel):
    runtime: Literal["ACE-Step", "MMAudio"]
    ready: bool = False
    registry_id: str = ""
    message: str = ""


class CoDirectorAudioProposal(BaseModel):
    id: str
    kind: AudioKind
    brief: AudioCreativeBrief
    recommended_provider: str = ""
    alternatives: list[str] = Field(default_factory=list)
    approved: bool = False
    executed: bool = False
