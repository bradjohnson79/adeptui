"""Unit tests for the canonical deterministic media probe.

These tests create a tiny real MP4 via ffmpeg (testsrc + sine, stereo) and
assert that ``probe_media`` populates the full frozen ``MediaFacts`` schema,
plus graceful degradation when ffprobe is unavailable.

No runtimes are touched (:8188 / :8192 untouched). No GPU.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.codirector.video_intelligence import media_probe
from app.codirector.video_intelligence.media_packet import ColorspaceTags, MediaFacts
from app.codirector.video_intelligence.media_probe import (
    probe_audio_stream,
    probe_colorspace,
    probe_media,
)


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"))


def _make_test_mp4(path: Path, *, fps: int = 24, duration: float = 1.0, sr: int = 44100) -> None:
    """Create a tiny testsrc + sine stereo MP4 via ffmpeg (~1s)."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=size=320x180:rate={fps}:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate={sr}:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(duration),
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-movflags", "+faststart", str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


@pytest.fixture
def test_mp4(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "probe_test.mp4"
    _make_test_mp4(path)
    return path


def test_probe_media_populates_full_schema(test_mp4: Path) -> None:
    facts = probe_media(test_mp4)

    assert isinstance(facts, MediaFacts)
    # Container + codecs populated (mp4 family + h264 + aac).
    assert "mp4" in facts.container
    assert facts.videoCodec == "h264"
    assert facts.audioCodec == "aac"
    # Dimensions.
    assert facts.width == 320
    assert facts.height == 180
    # Audio present + stereo.
    assert facts.hasAudio is True
    assert facts.channels == 2
    # Duration + fps positive.
    assert facts.durationSec > 0
    assert facts.fps > 0
    # Frame count derived (duration * fps for lavfi testsrc, nb_frames often present).
    assert facts.frameCount > 0
    # Bitrate populated (format bit_rate is reported for aac+h264 mux).
    assert facts.bitrate > 0
    # Colorspace tags fully populated (even if "unknown").
    assert isinstance(facts.colorspace, ColorspaceTags)
    for value in (
        facts.colorspace.colorSpace,
        facts.colorspace.colorTransfer,
        facts.colorspace.colorPrimaries,
        facts.colorspace.colorRange,
        facts.colorspace.pixelFormat,
    ):
        assert value, "colorspace tag must be populated (non-empty), even if 'unknown'"
    # pix_fmt for this encode is yuv420p (a real value, not "unknown").
    assert facts.colorspace.pixelFormat == "yuv420p"


def test_probe_media_sample_rate_matches(test_mp4: Path) -> None:
    facts = probe_media(test_mp4)
    assert facts.hasAudio is True
    assert facts.sampleRate == 44100


def test_probe_colorspace_returns_tags(test_mp4: Path) -> None:
    cs = probe_colorspace(test_mp4)
    assert isinstance(cs, ColorspaceTags)
    # All five fields populated (non-empty).
    assert cs.colorSpace
    assert cs.colorTransfer
    assert cs.colorPrimaries
    assert cs.colorRange
    assert cs.pixelFormat == "yuv420p"


def test_probe_audio_stream_returns_raw_fields(test_mp4: Path) -> None:
    audio = probe_audio_stream(test_mp4)
    assert isinstance(audio, dict)
    assert audio.get("codec_type") == "audio"
    assert audio.get("codec_name") == "aac"
    assert int(audio.get("channels") or 0) == 2
    assert int(audio.get("sample_rate") or 0) == 44100


def test_probe_media_degrades_when_ffprobe_absent(monkeypatch) -> None:
    """ffprobe absent -> zeroed MediaFacts, hasAudio=False, no raise."""
    monkeypatch.setattr(media_probe, "_find_ffprobe", lambda: None)
    facts = probe_media("any/path/does/not/matter.mp4")
    assert isinstance(facts, MediaFacts)
    assert facts.hasAudio is False
    assert facts.width == 0
    assert facts.height == 0
    assert facts.durationSec == 0.0
    assert facts.fps == 0.0
    assert facts.frameCount == 0
    assert facts.channels == 0
    assert facts.sampleRate == 0
    assert facts.bitrate == 0
    assert facts.container == ""


def test_probe_media_degrades_when_ffprobe_path_spoofed_missing(monkeypatch, tmp_path: Path) -> None:
    """ffprobe path spoofed to a missing binary -> zeroed MediaFacts, no raise."""
    bogus = str(tmp_path / "nonexistent_ffprobe.exe")
    monkeypatch.setattr(media_probe, "_find_ffprobe", lambda: bogus)
    facts = probe_media(tmp_path / "anything.mp4")
    assert isinstance(facts, MediaFacts)
    assert facts.hasAudio is False
    assert facts.width == 0
    assert facts.durationSec == 0.0


def test_probe_colorspace_degrades_when_ffprobe_absent(monkeypatch) -> None:
    monkeypatch.setattr(media_probe, "_find_ffprobe", lambda: None)
    cs = probe_colorspace("nope.mp4")
    assert isinstance(cs, ColorspaceTags)
    assert cs.colorSpace == "unknown"
    assert cs.colorTransfer == "unknown"
    assert cs.colorPrimaries == "unknown"
    assert cs.colorRange == "unknown"
    assert cs.pixelFormat == "unknown"


def test_probe_audio_stream_degrades_when_ffprobe_absent(monkeypatch) -> None:
    monkeypatch.setattr(media_probe, "_find_ffprobe", lambda: None)
    assert probe_audio_stream("nope.mp4") == {}


def test_probe_audio_stream_empty_when_no_audio_stream(monkeypatch, tmp_path: Path) -> None:
    """A media file with no audio stream -> empty dict, no raise."""
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    # Video-only MP4 (no -an; omit the sine input entirely).
    video_only = tmp_path / "video_only.mp4"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        "-movflags", "+faststart", str(video_only),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    facts = probe_media(video_only)
    assert facts.hasAudio is False
    assert facts.channels == 0
    assert probe_audio_stream(video_only) == {}
