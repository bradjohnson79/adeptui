"""Unit tests for deterministic A/V sync diagnostics (Ch 28).

Fixtures are tiny real files built with ffmpeg: a normal testsrc+sine MP4,
an MP4 whose audio is delayed 750 ms (deterministic drift), and a
video-only MP4. Degradation is asserted with ffprobe spoofed missing.

No runtimes are touched (:8188 / :8192 untouched). No GPU, no models.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.codirector.video_intelligence import media_probe
from app.codirector.video_intelligence.av_sync import measure_av_sync
from app.codirector.video_intelligence.media_packet import AVSyncDiagnostics


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"))


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def _make_av_mp4(path: Path, *, duration: float = 1.0) -> None:
    """1s testsrc + 1s sine stereo, both starting at ~0."""
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=size=160x120:rate=24:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-movflags", "+faststart", str(path),
    ])


def _make_delayed_audio_mp4(path: Path, *, delay_ms: int = 750, duration: float = 1.0) -> None:
    """Audio delayed by delay_ms -> audio stream runs longer than video."""
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=size=160x120:rate=24:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={duration}",
        "-af", f"adelay={delay_ms}:all=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-movflags", "+faststart", str(path),
    ])


def _make_video_only_mp4(path: Path) -> None:
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        "-movflags", "+faststart", str(path),
    ])


@pytest.fixture
def av_mp4(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "av.mp4"
    _make_av_mp4(path)
    return path


def test_measure_av_sync_aligned_file(av_mp4: Path) -> None:
    sync = measure_av_sync(av_mp4)
    assert isinstance(sync, AVSyncDiagnostics)
    # Both streams ~1s (AAC priming may extend audio slightly).
    assert 0.9 <= sync.videoDurationSec <= 1.1
    assert 0.9 <= sync.audioDurationSec <= 1.2
    # Both streams start at ~0.
    assert abs(sync.videoStartOffsetSec) < 0.1
    assert abs(sync.audioStartOffsetSec) < 0.1
    # driftSec is exactly the audio-minus-video duration delta...
    assert sync.driftSec == pytest.approx(sync.audioDurationSec - sync.videoDurationSec)
    # ...and for an aligned file it is small (AAC priming is tens of ms).
    assert abs(sync.driftSec) < 0.15
    # Perceptual judgement is never made by the deterministic probe.
    assert sync.speechLipMismatch is None


def test_measure_av_sync_detects_drift(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "drift.mp4"
    _make_delayed_audio_mp4(path, delay_ms=750)
    sync = measure_av_sync(path)
    # Audio = 1s content + 0.75s delay -> drift ≈ +0.75 (audio longer).
    assert 0.6 <= sync.driftSec <= 0.9
    assert sync.audioDurationSec > sync.videoDurationSec
    assert sync.speechLipMismatch is None


def test_measure_av_sync_video_only(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "video_only.mp4"
    _make_video_only_mp4(path)
    sync = measure_av_sync(path)
    assert sync.videoDurationSec > 0
    # No audio stream: no delta to measure.
    assert sync.audioDurationSec == 0.0
    assert sync.audioStartOffsetSec == 0.0
    assert sync.driftSec == 0.0
    assert sync.speechLipMismatch is None


def test_measure_av_sync_degrades_when_ffprobe_absent(monkeypatch) -> None:
    monkeypatch.setattr(media_probe, "_find_ffprobe", lambda: None)
    sync = measure_av_sync("any/path/does/not/matter.mp4")
    assert isinstance(sync, AVSyncDiagnostics)
    assert sync.videoDurationSec == 0.0
    assert sync.audioDurationSec == 0.0
    assert sync.videoStartOffsetSec == 0.0
    assert sync.audioStartOffsetSec == 0.0
    assert sync.driftSec == 0.0
    assert sync.speechLipMismatch is None


def test_measure_av_sync_degrades_when_ffprobe_path_spoofed(monkeypatch, tmp_path: Path) -> None:
    bogus = str(tmp_path / "nonexistent_ffprobe.exe")
    monkeypatch.setattr(media_probe, "_find_ffprobe", lambda: bogus)
    sync = measure_av_sync(tmp_path / "anything.mp4")
    assert isinstance(sync, AVSyncDiagnostics)
    assert sync.videoDurationSec == 0.0
    assert sync.driftSec == 0.0
