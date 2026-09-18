"""Unit tests for deterministic audio diagnostics (Ch 26-27).

Fixtures are tiny real files built with ffmpeg (sine stereo WAV, a hard-
clipped sine, a silent track, white noise, and a video-only MP4). All
measured values are asserted against the known-generative parameters.
Graceful degradation is asserted with ffmpeg/ffprobe spoofed missing.

No runtimes are touched (:8188 / :8192 untouched). No GPU, no models.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from app.codirector.video_intelligence import audio_diag, media_probe
from app.codirector.video_intelligence.audio_diag import (
    _measure_pcm,
    analyze_audio,
    decode_audio_pcm,
    detect_distortions,
    locate_distortions,
)
from app.codirector.video_intelligence.media_packet import AudioDiagnostics


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"))


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def _make_sine_wav(path: Path, *, volume: float = 0.5, sr: int = 48000, duration: float = 1.0) -> None:
    """Stereo sine WAV at an exact amplitude (aevalsrc is full-scale; the
    ``sine`` filter is not — it emits 1/8 amplitude). Stereo is generated at
    the source because ``-ac 2`` mono->stereo rematrix applies -3 dB.
    volume=0.5 keeps peaks well clear of the clip rail."""
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"aevalsrc=sin(2*PI*440*t)|sin(2*PI*440*t):s={sr}:d={duration}",
        "-af", f"volume={volume}",
        "-c:a", "pcm_s16le", str(path),
    ])


def _make_clipped_wav(path: Path, *, sr: int = 48000, duration: float = 1.0) -> None:
    """Full-scale sine driven 3x over into pcm_s16le -> hard-clipped rails
    (~78% of samples pinned, theoretically (2/pi)*arccos(1/3))."""
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"aevalsrc=sin(2*PI*440*t)|sin(2*PI*440*t):s={sr}:d={duration}",
        "-af", "volume=3.0",
        "-c:a", "pcm_s16le", str(path),
    ])


def _make_silent_wav(path: Path, *, sr: int = 48000, duration: float = 1.0) -> None:
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={sr}",
        "-t", str(duration), "-c:a", "pcm_s16le", str(path),
    ])


def _make_noise_wav(path: Path, *, sr: int = 48000, duration: float = 1.0) -> None:
    """White noise at 0.8 amplitude — broadband, below the clip rail."""
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"anoisesrc=color=white:amplitude=0.8:sample_rate={sr}:duration={duration}",
        "-ac", "2", "-c:a", "pcm_s16le", str(path),
    ])


def _make_video_only_mp4(path: Path) -> None:
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        "-movflags", "+faststart", str(path),
    ])


@pytest.fixture
def sine_wav(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "sine.wav"
    _make_sine_wav(path)
    return path


@pytest.fixture
def clipped_wav(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "clipped.wav"
    _make_clipped_wav(path)
    return path


@pytest.fixture
def silent_wav(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "silent.wav"
    _make_silent_wav(path)
    return path


@pytest.fixture
def noise_wav(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "noise.wav"
    _make_noise_wav(path)
    return path


# --- analyze_audio: measured values on real fixtures ---


def test_analyze_audio_sine_measured_values(sine_wav: Path) -> None:
    diag = analyze_audio(sine_wav)
    assert isinstance(diag, AudioDiagnostics)
    # Stream facts (via canonical probe_audio_stream).
    assert diag.sampleRate == 48000
    assert diag.channels == 2
    # 0.5-amplitude sine: peak ~0.5, RMS ~0.5/sqrt(2) ~ 0.354.
    assert 0.4 <= diag.peak <= 0.6
    assert 0.3 <= diag.rms <= 0.45
    # Peaks stay clear of the 0.99 rail: exactly zero clipped samples.
    assert diag.clippingFraction == 0.0
    # Symmetric sine: no DC offset.
    assert diag.dcOffset is not None
    assert abs(diag.dcOffset) < 0.01
    # Clean decode: no NaN/Inf.
    assert diag.nanCount == 0
    assert diag.infCount == 0
    # Continuous tone: essentially no silence.
    assert diag.silenceFraction < 0.05
    # Clean tone: spectral floor is low (most bins near zero).
    assert diag.spectralNoiseFloor is not None
    assert diag.spectralNoiseFloor < -20.0


def test_analyze_audio_clipped_sine(clipped_wav: Path) -> None:
    diag = analyze_audio(clipped_wav)
    assert diag.sampleRate == 48000
    assert diag.channels == 2
    # Rail-pinned: peak at full scale, a large fraction of samples clipped.
    assert diag.peak >= 0.99
    assert diag.clippingFraction > 0.3
    assert diag.nanCount == 0
    assert diag.infCount == 0


def test_analyze_audio_silent_track(silent_wav: Path) -> None:
    diag = analyze_audio(silent_wav)
    assert diag.sampleRate == 48000
    assert diag.channels == 2
    assert diag.peak < 1e-6
    assert diag.rms < 1e-6
    assert diag.clippingFraction == 0.0
    assert diag.silenceFraction > 0.95
    # Digital zero: floor bottoms out at the dB guard.
    assert diag.spectralNoiseFloor is not None
    assert diag.spectralNoiseFloor <= -100.0


def test_analyze_audio_noise_floor_above_sine(sine_wav: Path, noise_wav: Path) -> None:
    """Broadband noise fills all bins -> far higher spectral floor than a tone."""
    sine = analyze_audio(sine_wav)
    noise = analyze_audio(noise_wav)
    assert sine.spectralNoiseFloor is not None
    assert noise.spectralNoiseFloor is not None
    assert noise.spectralNoiseFloor > sine.spectralNoiseFloor + 10.0
    # 0.8-amplitude noise never touches the rail.
    assert noise.clippingFraction == 0.0


def test_decode_audio_pcm_shape(sine_wav: Path) -> None:
    pcm, sr = decode_audio_pcm(sine_wav)
    assert sr == 48000
    assert pcm.ndim == 2
    assert pcm.shape[1] == 2  # deinterleaved stereo
    # ~1s at 48 kHz (s16 wav is exact).
    assert abs(pcm.shape[0] - 48000) <= 2


# --- Pure measurement over synthetic PCM (NaN/Inf, DC) ---


def test_measure_pcm_counts_nan_inf_and_uses_finite_only() -> None:
    sr = 48000
    t = np.arange(sr, dtype=np.float32) / sr
    arr = np.stack([0.5 * np.sin(2 * np.pi * 440 * t)] * 2, axis=1).astype(np.float32)
    arr[100, 0] = np.nan
    arr[200:205, 1] = np.inf
    diag = _measure_pcm(arr, sr, 2)
    assert diag.nanCount == 1
    assert diag.infCount == 5
    # Stats computed over finite samples only — not poisoned to NaN.
    assert 0.4 <= diag.peak <= 0.6
    assert 0.3 <= diag.rms <= 0.45
    assert diag.dcOffset is not None and abs(diag.dcOffset) < 0.01


def test_measure_pcm_dc_offset_worst_channel() -> None:
    sr = 48000
    arr = np.zeros((sr, 2), dtype=np.float32)
    arr[:, 0] = 0.0
    arr[:, 1] = 0.25  # constant DC on one channel
    diag = _measure_pcm(arr, sr, 2)
    assert diag.dcOffset is not None
    assert abs(diag.dcOffset - 0.25) < 1e-6


# --- Distortion spans ---


def test_detect_distortions_clipped_sine(clipped_wav: Path) -> None:
    spans = detect_distortions(clipped_wav)
    clip_spans = [s for s in spans if s.distortionType == "clipping"]
    assert clip_spans, "clipped fixture must produce a clipping span"
    span = clip_spans[0]
    assert span.severity == "major"  # ~78% of samples pinned at the rail
    assert span.confidence == 1.0
    assert span.boundary == "asset-decode"
    # The whole 1s file is clipped: one span covering ~the full duration.
    assert (span.startTime or 0.0) < 0.1
    assert (span.endTime or 0.0) > 0.9


def test_detect_distortions_static_in_white_noise(noise_wav: Path) -> None:
    spans = detect_distortions(noise_wav)
    static_spans = [s for s in spans if s.distortionType == "static"]
    assert static_spans, "white noise must be flagged as static"
    assert static_spans[0].confidence == 1.0
    # Broadband noise below the rail: no clipping spans.
    assert not [s for s in spans if s.distortionType == "clipping"]


def test_detect_distortions_clean_sine_has_none(sine_wav: Path) -> None:
    assert detect_distortions(sine_wav) == []


def test_detect_distortions_silent_has_none(silent_wav: Path) -> None:
    assert detect_distortions(silent_wav) == []


def test_locate_distortions_synthetic_boundaries() -> None:
    """A clipped middle segment localizes to its time window."""
    sr = 48000
    quiet = 0.1 * np.sin(2 * np.pi * 440 * np.arange(sr // 2, dtype=np.float64) / sr)
    clipped = np.ones(sr // 2, dtype=np.float64)  # 0.5s pinned at the rail
    mono = np.concatenate([quiet, clipped, quiet])
    pcm = np.stack([mono, mono], axis=1).astype(np.float32)
    spans = locate_distortions(pcm, sr)
    clip_spans = [s for s in spans if s.distortionType == "clipping"]
    assert len(clip_spans) == 1
    span = clip_spans[0]
    assert span.severity == "major"
    # 50 ms windows: boundaries within one window of the true [0.5, 1.0].
    assert abs((span.startTime or 0.0) - 0.5) <= 0.05
    assert abs((span.endTime or 0.0) - 1.0) <= 0.05


def test_locate_distortions_empty_input() -> None:
    assert locate_distortions(np.zeros((0, 1), dtype=np.float32), 48000) == []
    assert locate_distortions(np.zeros((100, 1), dtype=np.float32), 0) == []


# --- Graceful degradation (never raises) ---


def test_analyze_audio_degrades_when_ffmpeg_absent(monkeypatch, sine_wav: Path) -> None:
    """ffmpeg gone, ffprobe present: stream facts kept, PCM metrics zeroed."""
    monkeypatch.setattr(audio_diag, "_find_ffmpeg", lambda: None)
    diag = analyze_audio(sine_wav)
    assert isinstance(diag, AudioDiagnostics)
    assert diag.sampleRate == 48000
    assert diag.channels == 2
    assert diag.peak == 0.0
    assert diag.rms == 0.0
    assert diag.clippingFraction == 0.0
    assert diag.nanCount == 0
    assert diag.infCount == 0
    assert diag.silenceFraction == 0.0
    assert diag.spectralNoiseFloor is None


def test_analyze_audio_degrades_when_ffmpeg_path_spoofed(monkeypatch, sine_wav: Path, tmp_path: Path) -> None:
    bogus = str(tmp_path / "nonexistent_ffmpeg.exe")
    monkeypatch.setattr(audio_diag, "_find_ffmpeg", lambda: bogus)
    diag = analyze_audio(sine_wav)
    assert diag.sampleRate == 48000  # stream facts still come from ffprobe
    assert diag.peak == 0.0
    assert diag.spectralNoiseFloor is None


def test_analyze_audio_degrades_when_both_absent(monkeypatch, sine_wav: Path) -> None:
    monkeypatch.setattr(media_probe, "_find_ffprobe", lambda: None)
    monkeypatch.setattr(audio_diag, "_find_ffmpeg", lambda: None)
    diag = analyze_audio(sine_wav)
    assert isinstance(diag, AudioDiagnostics)
    assert diag.sampleRate == 0
    assert diag.channels == 0
    assert diag.peak == 0.0
    assert diag.rms == 0.0
    assert diag.dcOffset is None
    assert diag.spectralNoiseFloor is None


def test_analyze_audio_no_audio_stream(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    video_only = tmp_path / "video_only.mp4"
    _make_video_only_mp4(video_only)
    diag = analyze_audio(video_only)
    assert isinstance(diag, AudioDiagnostics)
    assert diag.sampleRate == 0
    assert diag.channels == 0
    assert diag.peak == 0.0
    assert diag.rms == 0.0


def test_detect_distortions_degrades_when_ffmpeg_absent(monkeypatch, clipped_wav: Path) -> None:
    monkeypatch.setattr(audio_diag, "_find_ffmpeg", lambda: None)
    assert detect_distortions(clipped_wav) == []
