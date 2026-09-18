"""Shared CREATE inspection report + deterministic diagnostics stage.

This module is the CREATE-gate (1F/3F/T2V) orchestration layer that Phase C's
``media_analyze.analyze_asset`` does NOT cover:

- ``run_deterministic_diagnostics`` — runs the canonical probe/diag building
  blocks (``media_probe``, ``audio_diag``, ``av_sync``, ``color_diag``) and
  compiles the frozen ``Diagnostics`` schema. Pure CPU (ffprobe/ffmpeg +
  numpy). No GPU, no model inference, no ComfyUI. Never raises.
- ``enrich_packet_diagnostics`` — attaches those diagnostics to an existing
  packet (idempotent via an ``extras`` marker). Never touches
  ``packet.media`` (C3: deterministic media facts come from
  ``media_probe.probe_media`` ONLY, already set by ``analyze_asset``) and
  never touches the cache fingerprint (writing ``diagnosticVersion`` into
  the fingerprint would invalidate every cache hit against
  ``analyze_asset``'s fingerprint, which leaves it empty).
- ``build_inspection_report`` — the shared CREATE report contract.

Report law (non-negotiable):

- ``inspection`` answers "did Media Intelligence successfully inspect?"
  PASS when real evidence was produced. A detected defect is inspection
  PASS — the inspection worked.
- ``generatedMediaQuality`` answers "does the media have defects?"
  FAIL when distortion/color/sync defects are detected.
- The two are NEVER conflated: a clipped, drifting, gamma-shifted asset
  yields ``inspection=PASS`` + ``generatedMediaQuality=FAIL``.
- When inspection fails outright (no deterministic evidence at all),
  quality is reported ``NOT_VERIFIED`` — we never accuse media we could
  not measure, and never bless it either.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional

from .audio_diag import analyze_audio, detect_distortions
from .av_sync import measure_av_sync
from .color_diag import analyze_color
from .media_packet import (
    ANALYSIS_VERSION,
    AudioDiagnostics,
    AVSyncDiagnostics,
    ColorDiagnostics,
    DiagnosticReport,
    Diagnostics,
    DistortionSpan,
    MediaIntelligencePacket,
    VideoDiagnostics,
)
from .media_probe import probe_media

REPORT_SCHEMA = "media-inspection-report-v1"

# Version of the deterministic diagnostics stage. Recorded in
# ``packet.extras["deterministicDiagnostics"]`` — deliberately NOT in the
# cache fingerprint (see module docstring).
DIAGNOSTIC_VERSION = "media-diagnostics-v1.0"

# Qwen-unavailable failure policy wording (failure-policy chapter): the
# deterministic layer still completed, so this is never a full AV PASS.
PERCEPTION_UNAVAILABLE_REASON = (
    "Audio-visual perception unavailable. Deterministic media diagnostics completed."
)

# --- Quality ladders (deterministic, documented) ---------------------------

# A/V sync drift tolerances (seconds). AAC priming/edit-list residue can
# contribute ~40-80 ms of container-level duration delta on clean encodes,
# so DEGRADED starts above that; beyond FAIL the drift is audible/visible.
_AV_SYNC_DEGRADED_SEC = 0.08
_AV_SYNC_FAIL_SEC = 0.20

# Global clipped-sample fraction ladders, mirroring audio_diag's span
# severity thresholds (moderate at >= 0.02, major at >= 0.10).
_CLIP_FAIL_FRACTION = 0.02

# Gamma-shift ratio vs a reference (pure-gamma model; 1.0 = no shift).
_GAMMA_DEGRADED = 1.25
_GAMMA_FAIL = 2.0

_SEVERITY_RANK = {"none": 0, "minor": 1, "moderate": 2, "major": 3}

_VERDICT_RANK = {"NOT_APPLICABLE": -1, "NOT_VERIFIED": 0, "PASS": 1, "DEGRADED": 2, "FAIL": 3}


def _worst(*verdicts: str) -> str:
    """Worst verdict wins; NOT_APPLICABLE/NOT_VERIFIED never outrank evidence."""
    present = [v for v in verdicts if v in _VERDICT_RANK]
    if not present:
        return "NOT_VERIFIED"
    return max(present, key=lambda v: _VERDICT_RANK[v])


def _gamma_exceeds(gamma: Optional[float], limit: float) -> bool:
    """True when the gamma ratio deviates from 1.0 by more than ``limit`` (x or 1/x)."""
    if gamma is None or gamma <= 0 or limit <= 1:
        return False
    return gamma > limit or gamma < 1.0 / limit


# ---------------------------------------------------------------------------
# Deterministic diagnostics stage
# ---------------------------------------------------------------------------


def _audio_clipping_verdict(audio: AudioDiagnostics, spans: list[DistortionSpan], has_audio: bool) -> str:
    if not has_audio:
        return "NOT_APPLICABLE"
    clip_spans = [s for s in spans if s.distortionType == "clipping"]
    if audio.clippingFraction >= _CLIP_FAIL_FRACTION or any(
        _SEVERITY_RANK.get(s.severity, 0) >= 2 for s in clip_spans
    ):
        return "FAIL"
    if audio.clippingFraction > 0.0 or clip_spans:
        return "DEGRADED"
    return "PASS"


def _audio_static_verdict(audio: AudioDiagnostics, spans: list[DistortionSpan], has_audio: bool) -> str:
    if not has_audio:
        return "NOT_APPLICABLE"
    static_spans = [s for s in spans if s.distortionType == "static"]
    if any(_SEVERITY_RANK.get(s.severity, 0) >= 2 for s in static_spans):
        return "FAIL"
    if static_spans:
        return "DEGRADED"
    return "PASS"


def _av_sync_verdict(av_sync: AVSyncDiagnostics, has_audio: bool) -> str:
    if not has_audio:
        return "NOT_APPLICABLE"
    if av_sync.speechLipMismatch is True:
        return "FAIL"
    drift = abs(av_sync.driftSec)
    if drift > _AV_SYNC_FAIL_SEC:
        return "FAIL"
    if drift > _AV_SYNC_DEGRADED_SEC:
        return "DEGRADED"
    return "PASS"


def _color_verdict(color: ColorDiagnostics, measured: bool, has_reference: bool) -> str:
    if not measured:
        return "NOT_VERIFIED"
    if has_reference and _gamma_exceeds(color.gammaShiftEstimate, _GAMMA_FAIL):
        return "FAIL"
    if has_reference and _gamma_exceeds(color.gammaShiftEstimate, _GAMMA_DEGRADED):
        return "DEGRADED"
    tags = color.colorspaceMetadata
    if tags.colorSpace == "unknown" and tags.colorTransfer == "unknown":
        # Untagged output: fidelity unverifiable, not a defect per se.
        return "DEGRADED"
    return "PASS"


def _worst_span(spans: list[DistortionSpan]) -> Optional[DistortionSpan]:
    """Highest-severity, then earliest, distortion span."""
    if not spans:
        return None
    return sorted(
        spans,
        key=lambda s: (-_SEVERITY_RANK.get(s.severity, 0), s.startTime or 0.0),
    )[0]


def run_deterministic_diagnostics(
    video_path: str | Path,
    *,
    reference_path: str | Path | None = None,
) -> Diagnostics:
    """Run every deterministic diagnostic against an asset and compile the
    frozen ``Diagnostics`` schema.

    Sources (canonical building blocks, never re-implemented here):
    ``media_probe.probe_media`` (video block), ``audio_diag.analyze_audio`` +
    ``detect_distortions`` (audio + Ch 27 spans), ``av_sync.measure_av_sync``,
    ``color_diag.analyze_color`` (with optional 1F/3F reference).

    Pure CPU; degrades to zeroed sub-blocks when ffmpeg/ffprobe are absent.
    Never raises.
    """
    facts = probe_media(video_path)
    audio = analyze_audio(video_path)
    spans = detect_distortions(video_path, boundary="asset-decode")
    av_sync = measure_av_sync(video_path)
    color = analyze_color(video_path, reference_path=reference_path)

    video = VideoDiagnostics(
        codec=facts.videoCodec,
        fps=facts.fps,
        frameCount=facts.frameCount,
        bitrate=facts.bitrate,
        colorspace=facts.colorspace,
        color=color,
    )

    has_audio = facts.hasAudio
    color_measured = color.meanLuma > 0.0 or color.colorspaceMetadata.colorSpace != "unknown"
    clipping_v = _audio_clipping_verdict(audio, spans, has_audio)
    static_v = _audio_static_verdict(audio, spans, has_audio)
    av_sync_v = _av_sync_verdict(av_sync, has_audio)
    color_v = _color_verdict(color, color_measured, reference_path is not None)

    evidence: list[str] = []
    if audio.nanCount or audio.infCount:
        evidence.append(f"audio corruption: nanCount={audio.nanCount} infCount={audio.infCount}")
    for span in spans:
        evidence.append(
            f"{span.distortionType}:{span.severity} @{span.boundary} "
            f"[{span.startTime:.3f}s..{span.endTime:.3f}s]"
        )
    if has_audio and abs(av_sync.driftSec) > _AV_SYNC_DEGRADED_SEC:
        evidence.append(f"avSync drift {av_sync.driftSec:+.3f}s")
    if reference_path is not None and color.gammaShiftEstimate is not None:
        evidence.append(f"gammaShiftEstimate={color.gammaShiftEstimate:.3f} vs reference")

    worst = _worst_span(spans)
    report = DiagnosticReport(
        overall=_worst(clipping_v, static_v, av_sync_v, color_v),
        colorFidelity=color_v,
        temporalArtifacts="NOT_VERIFIED",  # no deterministic temporal-artifact detector yet
        identity="NOT_VERIFIED",  # perceptual judgement — VLM layer, never here
        audioStatic=static_v,
        audioClipping=clipping_v,
        avSync=av_sync_v,
        firstBrokenBoundary=(worst.boundary if worst and worst.boundary else ""),
        evidence=evidence,
    )

    return Diagnostics(video=video, audio=audio, avSync=av_sync, distortions=spans, report=report)


def enrich_packet_diagnostics(
    packet: MediaIntelligencePacket,
    video_path: str | Path,
    *,
    reference_path: str | Path | None = None,
) -> MediaIntelligencePacket:
    """Attach deterministic diagnostics to an existing packet (idempotent).

    Writes ONLY ``packet.diagnostics`` + an ``extras`` marker. Never touches
    ``packet.media`` (C3 — probe facts are ``analyze_asset``'s job) and never
    touches the fingerprint (cache-invalidation hazard).
    """
    packet.diagnostics = run_deterministic_diagnostics(video_path, reference_path=reference_path)
    packet.extras["deterministicDiagnostics"] = {
        "version": DIAGNOSTIC_VERSION,
        "referenceUsed": reference_path is not None,
    }
    return packet


def packet_has_current_diagnostics(packet: MediaIntelligencePacket) -> bool:
    """True when the packet already carries this version's deterministic diagnostics."""
    marker = packet.extras.get("deterministicDiagnostics")
    return isinstance(marker, dict) and marker.get("version") == DIAGNOSTIC_VERSION


# ---------------------------------------------------------------------------
# Shared CREATE inspection report
# ---------------------------------------------------------------------------


def _probe_ok(packet: MediaIntelligencePacket) -> bool:
    """True when the packet carries real deterministic media evidence."""
    facts = packet.media
    return bool(
        facts.container
        or facts.videoCodec
        or facts.frameCount > 0
        or facts.durationSec > 0
        or facts.sampleRate > 0
    )


def _inspection_verdict(packet: MediaIntelligencePacket) -> str:
    """Did Media Intelligence successfully inspect? (Never a media-quality verdict.)"""
    if not _probe_ok(packet):
        return "FAIL"  # no deterministic evidence at all — nothing was inspected
    if packet.availability == "ready":
        return "PASS"
    # low_confidence / degraded / unavailable-with-facts: deterministic
    # inspection completed, perceptual stage did not fully deliver.
    return "DEGRADED"


def _quality_verdict(packet: MediaIntelligencePacket, inspection: str) -> str:
    """Does the media have defects? Derived from measured diagnostics only."""
    if inspection == "FAIL":
        return "NOT_VERIFIED"  # never accuse (or bless) media we could not measure
    diag = packet.diagnostics
    audio = diag.audio
    spans = diag.distortions
    av_sync = diag.avSync
    color = diag.video.color
    has_reference = bool(packet.createContext and packet.createContext.referenceAssetIds)

    # FAIL ladder — hard defects.
    if audio.nanCount > 0 or audio.infCount > 0:
        return "FAIL"
    if any(_SEVERITY_RANK.get(s.severity, 0) >= 2 for s in spans):
        return "FAIL"
    if audio.clippingFraction >= _CLIP_FAIL_FRACTION:
        return "FAIL"
    if packet.media.hasAudio and abs(av_sync.driftSec) > _AV_SYNC_FAIL_SEC:
        return "FAIL"
    if av_sync.speechLipMismatch is True:
        return "FAIL"
    if diag.video.frameCorruption is True:
        return "FAIL"
    if has_reference and _gamma_exceeds(color.gammaShiftEstimate, _GAMMA_FAIL):
        return "FAIL"

    # DEGRADED ladder — minor / unverifiable issues.
    if spans:
        return "DEGRADED"
    if audio.clippingFraction > 0.0:
        return "DEGRADED"
    if packet.media.hasAudio and abs(av_sync.driftSec) > _AV_SYNC_DEGRADED_SEC:
        return "DEGRADED"
    if has_reference and _gamma_exceeds(color.gammaShiftEstimate, _GAMMA_DEGRADED):
        return "DEGRADED"
    if diag.video.temporalArtifacts is True or diag.video.identityDrift is True:
        return "DEGRADED"
    if audio.perceptualNote or color.perceptualNote:
        return "DEGRADED"
    return "PASS"


def _first_suspect_boundary(packet: MediaIntelligencePacket, quality: str) -> str:
    """Pipeline boundary most likely responsible for the first/worst defect."""
    worst = _worst_span(packet.diagnostics.distortions)
    if worst is not None and worst.boundary:
        return worst.boundary
    if quality in ("FAIL", "DEGRADED"):
        if packet.diagnostics.avSync.speechLipMismatch is True:
            return "perception:av-sync"
        if abs(packet.diagnostics.avSync.driftSec) > _AV_SYNC_DEGRADED_SEC:
            return "container:mux"
        if _gamma_exceeds(
            packet.diagnostics.video.color.gammaShiftEstimate, _GAMMA_DEGRADED
        ):
            return "reference:color"
    return ""


def _visual_section(packet: MediaIntelligencePacket) -> dict[str, Any]:
    facts = packet.media
    video = packet.diagnostics.video
    if not _probe_ok(packet):
        verdict = "NOT_VERIFIED"
    elif video.frameCorruption is True:
        verdict = "FAIL"
    elif video.temporalArtifacts is True:
        verdict = "DEGRADED"
    else:
        verdict = "PASS"
    evidence = [
        f"codec={facts.videoCodec or 'unknown'}",
        f"container={facts.container or 'unknown'}",
        f"{facts.width}x{facts.height} @{facts.fps:.3f}fps frames={facts.frameCount}",
        f"durationSec={facts.durationSec:.3f}",
    ]
    if video.temporalArtifacts is True:
        evidence.append("temporalArtifacts detected (perceptual)")
    if video.frameCorruption is True:
        evidence.append("frameCorruption detected")
    return {
        "verdict": verdict,
        "codec": facts.videoCodec,
        "container": facts.container,
        "width": facts.width,
        "height": facts.height,
        "fps": facts.fps,
        "frameCount": facts.frameCount,
        "durationSec": facts.durationSec,
        "bitrate": facts.bitrate,
        "colorspace": facts.colorspace.model_dump(),
        "visualEventCount": len(packet.visualEvents),
        "identityDrift": video.identityDrift,
        "temporalArtifacts": video.temporalArtifacts,
        "frameCorruption": video.frameCorruption,
        "evidence": evidence,
    }


def _motion_section(packet: MediaIntelligencePacket) -> dict[str, Any]:
    perceived = packet.modelEvidence.qwenOmni.invoked and packet.modelEvidence.qwenOmni.parseOk
    verdict = "PASS" if perceived else "NOT_VERIFIED"
    evidence = [
        f"motionEvents={len(packet.motionEvents)}",
        f"contactEvents={len(packet.contactEvents)}",
        f"characterActions={len(packet.characterActions)}",
    ]
    if not perceived:
        evidence.append("motion perception not verified (perceptual stage unavailable or unparsed)")
    return {
        "verdict": verdict,
        "motionEventCount": len(packet.motionEvents),
        "contactEventCount": len(packet.contactEvents),
        "characterActionCount": len(packet.characterActions),
        "evidence": evidence,
    }


def _audio_section(packet: MediaIntelligencePacket) -> dict[str, Any]:
    audio = packet.diagnostics.audio
    spans = packet.diagnostics.distortions
    has_audio = packet.media.hasAudio
    if not has_audio:
        verdict = "NOT_APPLICABLE"
    else:
        verdict = _worst(
            _audio_clipping_verdict(audio, spans, has_audio),
            _audio_static_verdict(audio, spans, has_audio),
            "FAIL" if (audio.nanCount or audio.infCount) else "PASS",
        )
        if verdict == "PASS" and audio.perceptualNote:
            verdict = "DEGRADED"
    evidence = [
        f"sampleRate={audio.sampleRate}",
        f"channels={audio.channels}",
        f"peak={audio.peak:.3f}",
        f"rms={audio.rms:.3f}",
        f"clippingFraction={audio.clippingFraction:.4f}",
        f"silenceFraction={audio.silenceFraction:.3f}",
        f"distortionSpans={len(spans)}",
    ]
    if audio.spectralNoiseFloor is not None:
        evidence.append(f"spectralNoiseFloor={audio.spectralNoiseFloor:.1f}dB")
    if audio.nanCount or audio.infCount:
        evidence.append(f"corruption: nanCount={audio.nanCount} infCount={audio.infCount}")
    if audio.perceptualNote:
        evidence.append(f"perceptualNote: {audio.perceptualNote}")
    return {
        "verdict": verdict,
        "hasAudio": has_audio,
        "sampleRate": audio.sampleRate,
        "channels": audio.channels,
        "peak": audio.peak,
        "rms": audio.rms,
        "clippingFraction": audio.clippingFraction,
        "dcOffset": audio.dcOffset,
        "nanCount": audio.nanCount,
        "infCount": audio.infCount,
        "silenceFraction": audio.silenceFraction,
        "spectralNoiseFloor": audio.spectralNoiseFloor,
        "distortionSpans": [s.model_dump(mode="json") for s in spans],
        "audioEventCount": len(packet.audioEvents),
        "speechSegmentCount": len(packet.speechSegments),
        "perceptualNote": audio.perceptualNote,
        "evidence": evidence,
    }


def _color_section(packet: MediaIntelligencePacket) -> dict[str, Any]:
    color = packet.diagnostics.video.color
    has_reference = bool(packet.createContext and packet.createContext.referenceAssetIds)
    measured = color.meanLuma > 0.0 or color.colorspaceMetadata.colorSpace != "unknown"
    verdict = _color_verdict(color, measured, has_reference)
    if verdict == "PASS" and color.perceptualNote:
        verdict = "DEGRADED"
    evidence = [
        f"meanLuma={color.meanLuma:.2f}",
        f"saturationEstimate={color.saturationEstimate:.3f}",
        f"rangeObserved={color.rangeObserved}",
        f"colorSpace={color.colorspaceMetadata.colorSpace}",
        f"colorTransfer={color.colorspaceMetadata.colorTransfer}",
        f"colorRange={color.colorspaceMetadata.colorRange}",
        f"pixelFormat={color.colorspaceMetadata.pixelFormat}",
    ]
    if color.gammaShiftEstimate is not None:
        evidence.append(f"gammaShiftEstimate={color.gammaShiftEstimate:.3f}")
    if color.perceptualNote:
        evidence.append(f"perceptualNote: {color.perceptualNote}")
    return {
        "verdict": verdict,
        "meanRgb": list(color.meanRgb),
        "meanLuma": color.meanLuma,
        "saturationEstimate": color.saturationEstimate,
        "gammaShiftEstimate": color.gammaShiftEstimate,
        "rangeObserved": color.rangeObserved,
        "colorspaceMetadata": color.colorspaceMetadata.model_dump(),
        "perceptualNote": color.perceptualNote,
        "evidence": evidence,
    }


def _av_sync_section(packet: MediaIntelligencePacket) -> dict[str, Any]:
    av_sync = packet.diagnostics.avSync
    has_audio = packet.media.hasAudio
    verdict = _av_sync_verdict(av_sync, has_audio)
    evidence = [
        f"videoDurationSec={av_sync.videoDurationSec:.3f}",
        f"audioDurationSec={av_sync.audioDurationSec:.3f}",
        f"driftSec={av_sync.driftSec:+.3f}",
        f"videoStartOffsetSec={av_sync.videoStartOffsetSec:+.3f}",
        f"audioStartOffsetSec={av_sync.audioStartOffsetSec:+.3f}",
    ]
    if av_sync.speechLipMismatch is not None:
        evidence.append(f"speechLipMismatch={av_sync.speechLipMismatch} (perceptual)")
    return {
        "verdict": verdict,
        "videoDurationSec": av_sync.videoDurationSec,
        "audioDurationSec": av_sync.audioDurationSec,
        "videoStartOffsetSec": av_sync.videoStartOffsetSec,
        "audioStartOffsetSec": av_sync.audioStartOffsetSec,
        "driftSec": av_sync.driftSec,
        "speechLipMismatch": av_sync.speechLipMismatch,
        "evidence": evidence,
    }


def _reference_adherence_section(packet: MediaIntelligencePacket) -> dict[str, Any]:
    ctx = packet.createContext
    if ctx is None or not ctx.referenceAssetIds:
        return {"verdict": "NOT_APPLICABLE", "referenceAssetIds": [], "evidence": ["no reference assets supplied"]}
    color = packet.diagnostics.video.color
    if color.gammaShiftEstimate is None:
        verdict = "NOT_VERIFIED"
    elif _gamma_exceeds(color.gammaShiftEstimate, _GAMMA_FAIL):
        verdict = "FAIL"
    elif _gamma_exceeds(color.gammaShiftEstimate, _GAMMA_DEGRADED):
        verdict = "DEGRADED"
    else:
        verdict = "PASS"
    evidence = [
        f"referenceAssetIds={list(ctx.referenceAssetIds)}",
        f"referenceRoles={list(ctx.referenceRoles)}",
    ]
    if color.gammaShiftEstimate is not None:
        evidence.append(f"gammaShiftEstimate={color.gammaShiftEstimate:.3f} (1.0 = no shift)")
    else:
        evidence.append("reference color shift not measured")
    evidence.extend(ctx.adherenceNotes)
    return {
        "verdict": verdict,
        "referenceAssetIds": list(ctx.referenceAssetIds),
        "referenceRoles": list(ctx.referenceRoles),
        "gammaShiftEstimate": color.gammaShiftEstimate,
        "adherenceNotes": list(ctx.adherenceNotes),
        "evidence": evidence,
    }


def _prompt_adherence_section(packet: MediaIntelligencePacket) -> dict[str, Any]:
    ctx = packet.createContext
    prompt = (ctx.prompt if ctx else "") or ""
    if not prompt.strip():
        return {"verdict": "NOT_APPLICABLE", "prompt": "", "evidence": ["no prompt supplied"]}
    # Honest labelling: deterministic measurement cannot score prompt
    # adherence; a perceptual judge is a future integration point. We surface
    # the prompt + perception summary as evidence and report NOT_VERIFIED.
    evidence = [f"prompt: {prompt[:240]}"]
    if packet.summary:
        evidence.append(f"perception summary: {packet.summary[:240]}")
    else:
        evidence.append("no perception summary available")
    return {
        "verdict": "NOT_VERIFIED",
        "prompt": prompt,
        "summary": packet.summary,
        "evidence": evidence,
    }


def build_inspection_report(packet: MediaIntelligencePacket) -> dict[str, Any]:
    """Compile the shared CREATE inspection report from a packet.

    ``inspection`` = did Media Intelligence successfully inspect (PASS when
    real evidence was produced). ``generatedMediaQuality`` = does the media
    have defects (FAIL on measured distortion/color/sync defects). A detected
    defect is inspection PASS + media-quality FAIL — never conflated.
    """
    inspection = _inspection_verdict(packet)
    quality = _quality_verdict(packet, inspection)
    boundary = _first_suspect_boundary(packet, quality)

    visual = _visual_section(packet)
    motion = _motion_section(packet)
    audio = _audio_section(packet)
    color = _color_section(packet)
    av_sync = _av_sync_section(packet)
    reference = _reference_adherence_section(packet)
    prompt = _prompt_adherence_section(packet)

    qwen = packet.modelEvidence.qwenOmni
    deterministic_evidence: list[str] = []
    deterministic_evidence.extend(visual["evidence"])
    deterministic_evidence.extend(audio["evidence"])
    deterministic_evidence.extend(av_sync["evidence"])
    deterministic_evidence.extend(color["evidence"])
    for span in packet.diagnostics.distortions:
        deterministic_evidence.append(
            f"distortion {span.distortionType}:{span.severity} boundary={span.boundary} "
            f"[{span.startTime:.3f}s..{span.endTime:.3f}s]"
        )

    perceptual_evidence: list[str] = [
        f"qwenOmni.invoked={qwen.invoked}",
        f"qwenOmni.availability={qwen.availability}",
        f"qwenOmni.parseOk={qwen.parseOk}",
    ]
    if not qwen.invoked:
        # Failure-policy wording: deterministic diagnostics completed; this is
        # NOT a full AV PASS.
        perceptual_evidence.append(PERCEPTION_UNAVAILABLE_REASON)
    if qwen.device:
        perceptual_evidence.append(f"qwenOmni.device={qwen.device}")
    if qwen.vramUsedGb is not None:
        perceptual_evidence.append(f"qwenOmni.vramUsedGb={qwen.vramUsedGb}")
    if qwen.loadToInferSec is not None:
        perceptual_evidence.append(f"qwenOmni.loadToInferSec={qwen.loadToInferSec}")
    if packet.summary:
        perceptual_evidence.append(f"summary: {packet.summary[:240]}")
    perceptual_evidence.append(
        "events: "
        f"visual={len(packet.visualEvents)} audio={len(packet.audioEvents)} "
        f"speech={len(packet.speechSegments)} motion={len(packet.motionEvents)}"
    )
    if packet.reason:
        perceptual_evidence.append(f"packet.reason={packet.reason}")

    surface = packet.createContext.surface if packet.createContext else "general"

    return {
        "schemaVersion": REPORT_SCHEMA,
        "analysisVersion": ANALYSIS_VERSION,
        "diagnosticVersion": DIAGNOSTIC_VERSION,
        "packetId": packet.packetId,
        "projectId": packet.projectId,
        "assetId": packet.assetId,
        "mode": packet.mode,
        "surface": surface,
        "inspection": inspection,
        "generatedMediaQuality": quality,
        "availability": packet.availability,
        "reason": packet.reason,
        "visual": visual,
        "motion": motion,
        "audio": audio,
        "color": color,
        "avSync": av_sync,
        "referenceAdherence": reference,
        "promptAdherence": prompt,
        "deterministicEvidence": deterministic_evidence,
        "perceptualEvidence": perceptual_evidence,
        "firstSuspectBoundary": boundary,
        "createdAt": packet.createdAt,
    }
