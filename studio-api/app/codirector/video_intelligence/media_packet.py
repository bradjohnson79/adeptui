"""Adept Media Intelligence Packet — shared authority for AV perception.

FROZEN CONTRACT (Law #16). Asset-scoped (projectId+assetId), not batch-scoped.
Combines deterministic media facts (Ch 4,24), perceptual events (Ch 8-13),
and measured diagnostics (Ch 25-29). Persisted on ProjectTraitRow
(category=media_intelligence_packet) for project isolation + reload survival
(Ch 41-42). Cache fingerprint (Ch 7) invalidates on asset/model/version change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

MEDIA_PACKET_SCHEMA = "media-intelligence-v1"
ANALYSIS_VERSION = "media-intelligence-v1.0"

QWEN_OMNI_MODEL_ID = "qwen2-5-omni-7b"
VIDEOCHAT3_MODEL_ID = "videochat3-4b"
INTERNVIDEO3_MODEL_ID = "internvideo3-8b-instruct"

PacketAvailability = Literal["ready", "unavailable", "low_confidence", "degraded"]
AnalysisMode = Literal["summary", "events", "ground", "transcribe", "diagnose", "footsteps", "full"]
FootSide = Literal["left", "right", "unknown"]
Confidence = Optional[float]


def _nid(prefix: str = "mip_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Temporal primitives (Ch 5 — one time authority)


class TimedEvent(BaseModel):
    """Base for every timestamped event. Seconds + frame index + confidence (Ch 33)."""

    startTime: Optional[float] = None
    endTime: Optional[float] = None
    startFrame: Optional[int] = None
    endFrame: Optional[int] = None
    confidence: Confidence = None


# Deterministic media facts (Ch 4, 24) — never asked of a VLM


class ColorspaceTags(BaseModel):
    colorSpace: str = "unknown"
    colorTransfer: str = "unknown"
    colorPrimaries: str = "unknown"
    colorRange: str = "unknown"
    pixelFormat: str = "unknown"


class MediaFacts(BaseModel):
    container: str = ""
    videoCodec: str = ""
    audioCodec: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    frameCount: int = 0
    durationSec: float = 0.0
    sampleRate: int = 0
    channels: int = 0
    bitrate: int = 0
    colorspace: ColorspaceTags = Field(default_factory=ColorspaceTags)
    hasAudio: bool = False


# Perceptual events (Ch 8-13)


class VisualEvent(TimedEvent):
    label: str = ""
    detail: str = ""
    phase: Literal["early", "mid", "late", "unknown"] = "unknown"


class CharacterAction(TimedEvent):
    characterId: Optional[str] = None
    characterLabel: str = ""
    action: str = ""
    actionCompletion: Optional[float] = None
    movementDirection: Optional[str] = None


class MotionEvent(TimedEvent):
    subject: Literal["camera", "character", "object", "unknown"] = "unknown"
    motionType: str = ""
    direction: Optional[str] = None
    velocity: Optional[str] = None


class ContactEvent(TimedEvent):
    """Foot/contact event for Timeline SFX (Ch 10). Replaces inferred 0.55s cadence."""

    characterId: Optional[str] = None
    characterLabel: str = ""
    foot: FootSide = "unknown"
    surface: Optional[str] = None
    intensity: Optional[float] = None
    timingSource: Literal["visible_contact", "motion_derived", "cadence_inference", "manual"] = (
        "visible_contact"
    )


class CueOpportunity(TimedEvent):
    """Structured SFX/ambience candidate. Co-Director decides whether to place."""

    kind: Literal[
        "footstep",
        "door",
        "impact",
        "cloth",
        "machinery",
        "prop",
        "environment",
        "explosion",
        "ambience",
        "other",
    ] = "other"
    label: str = ""
    suggestedQuery: str = ""
    presentInAudio: bool = False
    characterId: Optional[str] = None
    characterLabel: str = ""


class MusicOpportunity(TimedEvent):
    """Music-entry/exit candidate. Qwen does not place music — Co-Director does."""

    role: Literal["enter", "exit", "bed", "swell", "silence_window"] = "bed"
    intensity: Optional[str] = None
    dialogueDensity: Optional[str] = None
    emotionalTone: Optional[str] = None
    duckUnderDialogue: bool = True


class TimelineAnalysisContext(BaseModel):
    """Which Timeline scene/range produced this packet. Not a second time authority."""

    projectId: str = ""
    sceneId: str = ""
    clipAssetId: str = ""
    executionId: Optional[str] = None
    rangeStartSec: float = 0.0
    rangeEndSec: Optional[float] = None
    playheadSec: Optional[float] = None


class AudioEvent(TimedEvent):
    """Sound event present or to place (Ch 11). presentInAudio=False => candidate SFX."""

    eventType: str = ""
    intensity: Optional[float] = None
    material: Optional[str] = None
    context: Optional[str] = None
    presentInAudio: bool = False


class SpeechSegment(TimedEvent):
    """Detected speech/dialogue (Ch 12). speaker only set when confident."""

    speaker: Optional[str] = None
    speakerConfident: bool = False
    transcription: str = ""
    isSilence: bool = False
    overlap: bool = False


class EnvironmentEvent(TimedEvent):
    """Persistent ambience bed (Ch 13) — suggested ranges."""

    ambienceType: str = ""
    description: str = ""


# Diagnostics (Ch 24-29)


class ColorDiagnostics(BaseModel):
    meanRgb: tuple[float, float, float] = (0.0, 0.0, 0.0)
    meanLuma: float = 0.0
    saturationEstimate: float = 0.0
    gammaShiftEstimate: Optional[float] = None
    rangeObserved: str = "unknown"
    colorspaceMetadata: ColorspaceTags = Field(default_factory=ColorspaceTags)
    perceptualNote: str = ""


class AudioDiagnostics(BaseModel):
    """Raw audio measurement (promoted from .runtime/_fidelity_analyze). Ch 26."""

    sampleRate: int = 0
    channels: int = 0
    peak: float = 0.0
    rms: float = 0.0
    clippingFraction: float = 0.0
    dcOffset: Optional[float] = None
    nanCount: int = 0
    infCount: int = 0
    silenceFraction: float = 0.0
    spectralNoiseFloor: Optional[float] = None
    perceptualNote: str = ""


class DistortionSpan(TimedEvent):
    """Timestamped distortion region (Ch 27)."""

    severity: Literal["none", "minor", "moderate", "major"] = "none"
    distortionType: str = ""
    boundary: str = ""


class AVSyncDiagnostics(BaseModel):
    videoDurationSec: float = 0.0
    audioDurationSec: float = 0.0
    videoStartOffsetSec: float = 0.0
    audioStartOffsetSec: float = 0.0
    driftSec: float = 0.0
    speechLipMismatch: Optional[bool] = None


DiagnosticVerdict = Literal["PASS", "FAIL", "DEGRADED", "NOT_APPLICABLE", "NOT_VERIFIED"]


class VideoDiagnostics(BaseModel):
    codec: str = ""
    fps: float = 0.0
    frameCount: int = 0
    bitrate: int = 0
    colorspace: ColorspaceTags = Field(default_factory=ColorspaceTags)
    color: ColorDiagnostics = Field(default_factory=ColorDiagnostics)
    identityDrift: Optional[bool] = None
    temporalArtifacts: Optional[bool] = None
    frameCorruption: Optional[bool] = None


class DiagnosticReport(BaseModel):
    """Engineering-facing verdict block (Ch 29). firstBrokenBoundary needs proof."""

    overall: DiagnosticVerdict = "NOT_VERIFIED"
    colorFidelity: DiagnosticVerdict = "NOT_VERIFIED"
    temporalArtifacts: DiagnosticVerdict = "NOT_VERIFIED"
    identity: DiagnosticVerdict = "NOT_VERIFIED"
    audioStatic: DiagnosticVerdict = "NOT_VERIFIED"
    audioClipping: DiagnosticVerdict = "NOT_VERIFIED"
    avSync: DiagnosticVerdict = "NOT_VERIFIED"
    firstBrokenBoundary: str = ""
    evidence: list[str] = Field(default_factory=list)


class Diagnostics(BaseModel):
    video: VideoDiagnostics = Field(default_factory=VideoDiagnostics)
    audio: AudioDiagnostics = Field(default_factory=AudioDiagnostics)
    avSync: AVSyncDiagnostics = Field(default_factory=AVSyncDiagnostics)
    distortions: list[DistortionSpan] = Field(default_factory=list)
    report: DiagnosticReport = Field(default_factory=DiagnosticReport)


# CREATE diagnostics surface context (Ch 20-23)

CreateSurface = Literal["text_to_video", "one_frame", "three_frame", "general"]


class CreateDiagnosticContext(BaseModel):
    """Surface-specific framing. referenceAssetIds carry source (1F) or START/MIDDLE/END (3F)."""

    surface: CreateSurface = "general"
    prompt: str = ""
    referenceAssetIds: list[str] = Field(default_factory=list)
    referenceRoles: list[Literal["source", "start", "middle", "end"]] = Field(default_factory=list)
    adherenceNotes: list[str] = Field(default_factory=list)


# Model evidence (Ch 6)


class ModelRunEvidence(BaseModel):
    modelId: str = ""
    invoked: bool = False
    availability: PacketAvailability = "unavailable"
    loadToInferSec: Optional[float] = None
    vramUsedGb: Optional[float] = None
    device: Optional[str] = None
    rawText: str = ""
    parseOk: bool = False
    confidence: Confidence = None


class ModelEvidence(BaseModel):
    qwenOmni: ModelRunEvidence = Field(default_factory=ModelRunEvidence)
    videoChat3: ModelRunEvidence = Field(default_factory=ModelRunEvidence)
    internVideo3: ModelRunEvidence = Field(default_factory=ModelRunEvidence)


# Cache fingerprint (Ch 7)


class AnalysisFingerprint(BaseModel):
    assetId: str = ""
    assetHash: str = ""
    analysisVersion: str = ANALYSIS_VERSION
    qwenOmniModelVersion: str = ""
    videoChat3ModelVersion: str = ""
    diagnosticVersion: str = ""


# The packet


class MediaIntelligencePacket(BaseModel):
    """One structured AV-understanding packet per asset. Shared authority.

    Produced by the Adept Media Intelligence Service (extended video_intelligence).
    Consumed by Co-Director (Ch 14), Timeline (Ch 15-18), CREATE Diagnostics (Ch 20-23).
    """

    schemaVersion: str = MEDIA_PACKET_SCHEMA
    packetId: str = Field(default_factory=_nid)
    projectId: str = ""
    assetId: str = ""
    analysisVersion: str = ANALYSIS_VERSION
    availability: PacketAvailability = "unavailable"
    reason: Optional[str] = None
    mode: AnalysisMode = "summary"

    media: MediaFacts = Field(default_factory=MediaFacts)
    summary: str = ""

    visualEvents: list[VisualEvent] = Field(default_factory=list)
    audioEvents: list[AudioEvent] = Field(default_factory=list)
    speechSegments: list[SpeechSegment] = Field(default_factory=list)
    characterActions: list[CharacterAction] = Field(default_factory=list)
    motionEvents: list[MotionEvent] = Field(default_factory=list)
    contactEvents: list[ContactEvent] = Field(default_factory=list)
    environmentEvents: list[EnvironmentEvent] = Field(default_factory=list)
    sceneChanges: list[VisualEvent] = Field(default_factory=list)
    cameraMotion: list[MotionEvent] = Field(default_factory=list)
    cueOpportunities: list[CueOpportunity] = Field(default_factory=list)
    musicOpportunities: list[MusicOpportunity] = Field(default_factory=list)
    timelineContext: Optional[TimelineAnalysisContext] = None

    diagnostics: Diagnostics = Field(default_factory=Diagnostics)
    createContext: Optional[CreateDiagnosticContext] = None
    modelEvidence: ModelEvidence = Field(default_factory=ModelEvidence)
    fingerprint: AnalysisFingerprint = Field(default_factory=AnalysisFingerprint)

    createdAt: str = Field(default_factory=_now)
    extras: dict[str, Any] = Field(default_factory=dict)

    def is_ready(self) -> bool:
        return self.availability in ("ready", "low_confidence", "degraded")


def compose_audio_prompt_from_packet(
    packet: "MediaIntelligencePacket",
    *,
    kind: str,
    base_prompt: str,
    max_len: int = 2000,
) -> str:
    """Fold Omni Media Intelligence into an ACE-Step / MMAudio prompt.

    Co-Director generate tools call this so watch->compose is a real closed loop:
    Qwen 2.5 Omni packet summary + music/cue opportunities enrich the human prompt.
    Never invents facts beyond the packet; returns base_prompt unchanged when empty.
    """
    base = (base_prompt or "").strip()
    if packet is None or not packet.is_ready():
        return base[:max_len]
    parts: list[str] = []
    if base:
        parts.append(base)
    summary = (packet.summary or "").strip()
    if summary:
        parts.append(f"Scene watch (Qwen 2.5 Omni): {summary}")
    kind_l = (kind or "").strip().lower()
    if kind_l == "music":
        opps = list(packet.musicOpportunities or [])
        if opps:
            first = opps[0]
            bits = [
                f"role={getattr(first, 'role', None) or 'bed'}",
                f"intensity={getattr(first, 'intensity', None) or 'n/a'}",
                f"emotionalTone={getattr(first, 'emotionalTone', None) or 'n/a'}",
                f"start={getattr(first, 'startTime', 0.0)}s",
            ]
            if getattr(first, "endTime", None) is not None:
                bits.append(f"end={first.endTime}s")
            parts.append("Music opportunity from watch: " + ", ".join(bits) + ".")
            if len(opps) > 1:
                parts.append(f"Additional music windows: {len(opps) - 1}.")
    elif kind_l in {"sfx", "ambience"}:
        cues = [
            c
            for c in (packet.cueOpportunities or [])
            if not bool(getattr(c, "presentInAudio", False))
        ][:6]
        if cues:
            labels = "; ".join(
                f"{getattr(c, 'kind', 'sfx')}:{getattr(c, 'suggestedQuery', None) or getattr(c, 'label', '')} @{getattr(c, 'startTime', 0.0)}s"
                for c in cues
            )
            parts.append(f"SFX cue opportunities from watch: {labels}.")
        contacts = list(packet.contactEvents or [])[:8]
        if contacts and kind_l == "sfx":
            contact_bits = "; ".join(
                f"{getattr(c, 'characterLabel', '') or 'foot'} {getattr(c, 'surface', '') or 'floor'} @{getattr(c, 'startTime', 0.0)}s"
                for c in contacts
            )
            parts.append(f"Visible contacts for foley timing: {contact_bits}.")
        envs = list(packet.environmentEvents or [])[:3]
        if envs and kind_l == "ambience":
            parts.append(
                "Ambience from watch: "
                + "; ".join(
                    f"{getattr(e, 'ambienceType', '') or 'ambience'}: {getattr(e, 'description', '') or ''}"
                    for e in envs
                )
                + "."
            )
    heard = [e for e in (packet.audioEvents or []) if bool(getattr(e, "presentInAudio", False))][:3]
    if heard and kind_l == "sfx":
        parts.append(
            "Already audible (avoid duplicating): "
            + "; ".join(f"{getattr(e, 'eventType', 'sound')}" for e in heard)
            + "."
        )
    out = " ".join(p for p in parts if p).strip() or base
    return out[:max_len]

