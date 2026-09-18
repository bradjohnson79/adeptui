"""Tests for the shared CREATE inspection report + deterministic diagnostics stage.

Covers the report law that the CREATE gates (1F/3F/T2V) depend on:

- ``inspection`` (did Media Intelligence successfully inspect?) and
  ``generatedMediaQuality`` (does the media have defects?) are NEVER
  conflated: a hard-clipped asset yields inspection PASS + quality FAIL.
- Deterministic fields (codec, sampleRate, colorspace, drift) come from the
  probe/diag modules ONLY — perceptual payload claims never override them.
- ``firstSuspectBoundary`` derives from ``DistortionSpan.boundary``.
- The Qwen-unavailable path degrades honestly: deterministic diagnostics
  completed, perception did not — inspection DEGRADED, never a full AV PASS.

Fixtures are tiny real files built with ffmpeg (mirrors test_audio_diag.py):
a clean testsrc+sine MP4 and a hard-clipped MOV (pcm_s16le rails pinned by a
3x-overdriven sine, ~78% clipped samples). No GPU, no models, no runtimes
(:8188 / :8192 untouched); ``run_perception``/``run_av_perception`` are never
invoked here — packets are constructed directly.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.codirector.video_intelligence import inspection_report as ir
from app.codirector.video_intelligence.inspection_report import (
    PERCEPTION_UNAVAILABLE_REASON,
    build_inspection_report,
    enrich_packet_diagnostics,
    packet_has_current_diagnostics,
    run_deterministic_diagnostics,
)
from app.codirector.video_intelligence.media_packet import (
    QWEN_OMNI_MODEL_ID,
    AVSyncDiagnostics,
    CreateDiagnosticContext,
    DistortionSpan,
    MediaIntelligencePacket,
)
from app.codirector.video_intelligence.media_probe import probe_media


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"))


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def _make_clean_mp4(path: Path) -> None:
    """testsrc video + 0.5-amplitude stereo sine (peaks clear of the clip rail)."""
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=1",
        "-f", "lavfi", "-i", "aevalsrc=sin(2*PI*440*t)|sin(2*PI*440*t):s=48000:d=1",
        "-af", "volume=0.5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-movflags", "+faststart", str(path),
    ])


def _make_distorted_mov(path: Path) -> None:
    """testsrc video + 3x-overdriven sine into pcm_s16le -> hard-clipped rails
    (~78% of samples pinned, theoretically (2/pi)*arccos(1/3)). Deterministic
    across ffmpeg builds (PCM clips at encode time, unlike lossy AAC)."""
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=1",
        "-f", "lavfi", "-i", "aevalsrc=sin(2*PI*440*t)|sin(2*PI*440*t):s=48000:d=1",
        "-af", "volume=3.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "pcm_s16le", "-movflags", "+faststart", str(path),
    ])


@pytest.fixture()
def clean_mp4(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "clean.mp4"
    _make_clean_mp4(path)
    return path


@pytest.fixture()
def distorted_mov(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "distorted.mov"
    _make_distorted_mov(path)
    return path


def _packet_for(
    path: Path,
    *,
    availability: str = "ready",
    qwen_invoked: bool = True,
    parse_ok: bool = True,
    ctx: CreateDiagnosticContext | None = None,
) -> MediaIntelligencePacket:
    """A packet as the orchestrated path would produce it: probe facts (set by
    analyze_asset) + deterministic diagnostics enrichment (this stage)."""
    packet = MediaIntelligencePacket(
        projectId="proj-report",
        assetId="asset-1",
        availability=availability,  # type: ignore[arg-type]
        mode="diagnose",
        media=probe_media(path),
        createContext=ctx,
    )
    enrich_packet_diagnostics(packet, path)
    evidence = packet.modelEvidence.qwenOmni
    evidence.modelId = QWEN_OMNI_MODEL_ID
    evidence.invoked = qwen_invoked
    evidence.parseOk = parse_ok
    evidence.availability = "ready" if parse_ok else "low_confidence"
    return packet


# ---------------------------------------------------------------------------
# Deterministic diagnostics stage (real fixtures, measured values)
# ---------------------------------------------------------------------------


def test_deterministic_diagnostics_clean_fixture(clean_mp4: Path) -> None:
    diag = run_deterministic_diagnostics(clean_mp4)
    assert diag.video.codec == "h264"
    assert diag.video.fps == 24.0
    assert diag.video.frameCount == 24
    assert diag.audio.sampleRate == 48000
    assert diag.audio.channels == 2
    assert diag.audio.clippingFraction == 0.0
    assert diag.audio.nanCount == 0 and diag.audio.infCount == 0
    assert diag.distortions == []
    assert abs(diag.avSync.driftSec) <= 0.08
    assert diag.report.audioClipping == "PASS"
    assert diag.report.avSync == "PASS"
    assert diag.report.firstBrokenBoundary == ""


def test_deterministic_diagnostics_distorted_fixture(distorted_mov: Path) -> None:
    diag = run_deterministic_diagnostics(distorted_mov)
    assert diag.audio.clippingFraction > 0.3
    clip_spans = [s for s in diag.distortions if s.distortionType == "clipping"]
    assert clip_spans, "clipped fixture must produce clipping spans"
    assert any(s.severity in ("moderate", "major") for s in clip_spans)
    assert all(s.boundary == "asset-decode" for s in clip_spans)
    assert diag.report.audioClipping == "FAIL"
    assert diag.report.overall == "FAIL"
    assert diag.report.firstBrokenBoundary == "asset-decode"


def test_enrich_packet_diagnostics_marks_extras_and_preserves_media(clean_mp4: Path) -> None:
    facts = probe_media(clean_mp4)
    packet = MediaIntelligencePacket(projectId="p", assetId="a", media=facts)
    media_before = packet.media.model_dump()
    fingerprint_before = packet.fingerprint.model_dump()
    enrich_packet_diagnostics(packet, clean_mp4)
    assert packet_has_current_diagnostics(packet)
    assert packet.extras["deterministicDiagnostics"]["version"] == ir.DIAGNOSTIC_VERSION
    # C3 + cache safety: media facts and fingerprint are never rewritten.
    assert packet.media.model_dump() == media_before
    assert packet.fingerprint.model_dump() == fingerprint_before


# ---------------------------------------------------------------------------
# The mandatory distinction: inspection PASS vs generatedMediaQuality FAIL
# ---------------------------------------------------------------------------


def test_report_clean_fixture_inspection_pass_quality_pass(clean_mp4: Path) -> None:
    report = build_inspection_report(_packet_for(clean_mp4))
    assert report["inspection"] == "PASS"
    assert report["generatedMediaQuality"] == "PASS"
    assert report["firstSuspectBoundary"] == ""
    assert report["audio"]["verdict"] == "PASS"
    assert report["avSync"]["verdict"] == "PASS"


def test_report_distorted_fixture_inspection_pass_quality_fail(distorted_mov: Path) -> None:
    """A detected defect = inspection PASS (we measured it) + media quality FAIL."""
    report = build_inspection_report(_packet_for(distorted_mov))
    assert report["inspection"] == "PASS", "real deterministic evidence was produced"
    assert report["generatedMediaQuality"] == "FAIL", "clipping defect must fail media quality"
    assert report["firstSuspectBoundary"] == "asset-decode"
    assert report["audio"]["verdict"] == "FAIL"
    assert report["audio"]["clippingFraction"] > 0.3
    assert any("clipping" in e for e in report["deterministicEvidence"])
    assert any("asset-decode" in e for e in report["deterministicEvidence"])


def test_report_unavailable_packet_inspection_fail_quality_not_verified() -> None:
    """No evidence at all -> inspection FAIL; quality is honestly NOT_VERIFIED
    (we never accuse — or bless — media we could not measure)."""
    packet = MediaIntelligencePacket(
        projectId="p",
        assetId="missing",
        availability="unavailable",
        reason="SOURCE_VIDEO_MISSING",
    )
    report = build_inspection_report(packet)
    assert report["inspection"] == "FAIL"
    assert report["generatedMediaQuality"] == "NOT_VERIFIED"
    assert report["firstSuspectBoundary"] == ""


def test_report_perception_unavailable_degrades_honestly(clean_mp4: Path) -> None:
    """Qwen-unavailable path: deterministic diagnostics completed, perception
    did not -> inspection DEGRADED (never a full AV PASS), quality still
    measured from deterministic evidence."""
    packet = _packet_for(clean_mp4, availability="unavailable", qwen_invoked=False, parse_ok=False)
    packet.reason = "MODEL_NOT_INSTALLED"
    packet.modelEvidence.qwenOmni.availability = "unavailable"
    report = build_inspection_report(packet)
    assert report["inspection"] == "DEGRADED"
    assert report["generatedMediaQuality"] == "PASS"
    assert PERCEPTION_UNAVAILABLE_REASON in report["perceptualEvidence"]
    assert "qwenOmni.invoked=False" in report["perceptualEvidence"]


def test_report_low_confidence_perception_is_degraded_not_fail(clean_mp4: Path) -> None:
    packet = _packet_for(clean_mp4, availability="low_confidence", parse_ok=False)
    report = build_inspection_report(packet)
    assert report["inspection"] == "DEGRADED"
    assert report["generatedMediaQuality"] == "PASS"


# ---------------------------------------------------------------------------
# C3 at the report layer: perceptual claims never override deterministic fact
# ---------------------------------------------------------------------------


def test_report_deterministic_fields_immune_to_perceptual_claims(clean_mp4: Path) -> None:
    packet = _packet_for(clean_mp4)
    # The VLM claims contradictory media facts in its summary + raw text.
    packet.summary = "This vp9 clip at 96kHz audio shows a spinning rig."
    packet.modelEvidence.qwenOmni.rawText = '{"videoCodec": "vp9", "sampleRate": 96000}'
    report = build_inspection_report(packet)
    # Deterministic sections carry the probed facts only.
    assert report["visual"]["codec"] == "h264"
    assert report["audio"]["sampleRate"] == 48000
    assert report["visual"]["fps"] == 24.0
    assert "codec=h264" in report["deterministicEvidence"]
    assert "sampleRate=48000" in report["deterministicEvidence"]
    assert not any("vp9" in e or "96000" in e for e in report["deterministicEvidence"])
    # The VLM text is quoted as perceptual EVIDENCE, never as fact.
    assert any("vp9" in e for e in report["perceptualEvidence"])


# ---------------------------------------------------------------------------
# Quality ladders: avSync drift, reference adherence, boundary attribution
# ---------------------------------------------------------------------------


def _packet_with_drift(clean_mp4: Path, drift: float) -> MediaIntelligencePacket:
    packet = _packet_for(clean_mp4)
    packet.diagnostics.avSync = AVSyncDiagnostics(
        videoDurationSec=1.0,
        audioDurationSec=1.0 + drift,
        driftSec=drift,
    )
    return packet


def test_report_avsync_drift_ladder(clean_mp4: Path) -> None:
    report = build_inspection_report(_packet_with_drift(clean_mp4, 0.30))
    assert report["avSync"]["verdict"] == "FAIL"
    assert report["generatedMediaQuality"] == "FAIL"
    assert report["firstSuspectBoundary"] == "container:mux"

    report = build_inspection_report(_packet_with_drift(clean_mp4, 0.12))
    assert report["avSync"]["verdict"] == "DEGRADED"
    assert report["generatedMediaQuality"] == "DEGRADED"

    report = build_inspection_report(_packet_with_drift(clean_mp4, 0.0))
    assert report["avSync"]["verdict"] == "PASS"
    assert report["generatedMediaQuality"] == "PASS"


def test_report_reference_adherence_gamma_shift(clean_mp4: Path) -> None:
    ctx = CreateDiagnosticContext(
        surface="one_frame",
        prompt="a test pattern",
        referenceAssetIds=["ref-1"],
        referenceRoles=["source"],
    )
    packet = _packet_for(clean_mp4, ctx=ctx)
    packet.diagnostics.video.color.gammaShiftEstimate = 3.0
    report = build_inspection_report(packet)
    assert report["surface"] == "one_frame"
    assert report["referenceAdherence"]["verdict"] == "FAIL"
    assert report["referenceAdherence"]["referenceAssetIds"] == ["ref-1"]
    assert report["generatedMediaQuality"] == "FAIL"
    assert report["firstSuspectBoundary"] == "reference:color"

    packet.diagnostics.video.color.gammaShiftEstimate = 1.4
    report = build_inspection_report(packet)
    assert report["referenceAdherence"]["verdict"] == "DEGRADED"

    packet.diagnostics.video.color.gammaShiftEstimate = 1.0
    report = build_inspection_report(packet)
    assert report["referenceAdherence"]["verdict"] == "PASS"

    packet.diagnostics.video.color.gammaShiftEstimate = None
    report = build_inspection_report(packet)
    assert report["referenceAdherence"]["verdict"] == "NOT_VERIFIED"


def test_report_reference_adherence_not_applicable_without_references(clean_mp4: Path) -> None:
    report = build_inspection_report(_packet_for(clean_mp4))
    assert report["surface"] == "general"
    assert report["referenceAdherence"]["verdict"] == "NOT_APPLICABLE"


def test_report_prompt_adherence_is_honestly_not_verified(clean_mp4: Path) -> None:
    ctx = CreateDiagnosticContext(surface="text_to_video", prompt="a tester walks left")
    packet = _packet_for(clean_mp4, ctx=ctx)
    packet.summary = "A synthetic test pattern with a tone."
    report = build_inspection_report(packet)
    assert report["promptAdherence"]["verdict"] == "NOT_VERIFIED"
    assert report["promptAdherence"]["prompt"] == "a tester walks left"
    assert any("a tester walks left" in e for e in report["promptAdherence"]["evidence"])

    report = build_inspection_report(_packet_for(clean_mp4))
    assert report["promptAdherence"]["verdict"] == "NOT_APPLICABLE"


def test_report_first_suspect_boundary_picks_worst_span(clean_mp4: Path) -> None:
    packet = _packet_for(clean_mp4)
    packet.diagnostics.distortions = [
        DistortionSpan(
            startTime=0.0, endTime=0.2, confidence=1.0,
            severity="minor", distortionType="static", boundary="raw-decode",
        ),
        DistortionSpan(
            startTime=0.5, endTime=0.7, confidence=1.0,
            severity="major", distortionType="clipping", boundary="final-mux",
        ),
    ]
    report = build_inspection_report(packet)
    assert report["generatedMediaQuality"] == "FAIL"
    assert report["firstSuspectBoundary"] == "final-mux"


def test_report_speech_lip_mismatch_fails_quality(clean_mp4: Path) -> None:
    packet = _packet_for(clean_mp4)
    packet.diagnostics.avSync.speechLipMismatch = True
    report = build_inspection_report(packet)
    assert report["avSync"]["verdict"] == "FAIL"
    assert report["generatedMediaQuality"] == "FAIL"
    assert report["firstSuspectBoundary"] == "perception:av-sync"


def test_report_no_audio_asset_av_sections_not_applicable(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "silent_video.mp4"
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        "-movflags", "+faststart", str(path),
    ])
    report = build_inspection_report(_packet_for(path))
    assert report["inspection"] == "PASS"
    assert report["audio"]["verdict"] == "NOT_APPLICABLE"
    assert report["avSync"]["verdict"] == "NOT_APPLICABLE"
    assert report["generatedMediaQuality"] == "PASS"
