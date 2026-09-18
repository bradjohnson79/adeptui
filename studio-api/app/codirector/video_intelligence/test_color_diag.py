"""Unit tests for deterministic color diagnostics (Ch 25).

Fixtures are tiny real files built with ffmpeg: a testsrc MP4, a
bt601-tagged MP4, and exact PNG stills (red / dark red / gray) for
reference-shift detection. Degradation is asserted with ffmpeg/ffprobe
spoofed missing.

No runtimes are touched (:8188 / :8192 untouched). No GPU, no models.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.codirector.video_intelligence import color_diag, media_probe
from app.codirector.video_intelligence.color_diag import analyze_color, compute_color_shift
from app.codirector.video_intelligence.media_packet import ColorDiagnostics


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"))


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def _make_testsrc_mp4(path: Path, *, duration: float = 1.0) -> None:
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=size=320x180:rate=24:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(path),
    ])


def _make_bt601_mp4(path: Path, *, duration: float = 1.0) -> None:
    """testsrc encoded with explicit bt601 (NTSC) tags + tv range.

    The ``h264_metadata`` bitstream filter rewrites the VUI directly:
    6 = smpte170m (bt601 NTSC) for primaries/transfer/matrix. Encoder-side
    ``-color_primaries``/``-color_trc`` options do NOT survive this ffmpeg +
    libx264 path (verified empirically) — the bitstream filter does.
    """
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=size=320x180:rate=24:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-bsf:v", "h264_metadata=colour_primaries=6:transfer_characteristics=6:matrix_coefficients=6:video_full_range_flag=0",
        "-movflags", "+faststart", str(path),
    ])


def _make_still_png(path: Path, color: str, *, size: str = "64x64") -> None:
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"color=c={color}:size={size}",
        "-frames:v", "1", str(path),
    ])


@pytest.fixture
def testsrc_mp4(tmp_path: Path) -> Path:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "testsrc.mp4"
    _make_testsrc_mp4(path)
    return path


# --- analyze_color: measured values on real fixtures ---


def test_analyze_color_testsrc(testsrc_mp4: Path) -> None:
    diag = analyze_color(testsrc_mp4)
    assert isinstance(diag, ColorDiagnostics)
    # Means on the 0-255 scale; testsrc has bright saturated bars.
    assert len(diag.meanRgb) == 3
    for channel_mean in diag.meanRgb:
        assert 0.0 <= channel_mean <= 255.0
    assert 20.0 < diag.meanLuma < 235.0
    # Saturated color bars -> clearly non-zero saturation.
    assert 0.15 < diag.saturationEstimate <= 1.0
    # Untagged file: range is honestly estimated from decoded RGB headroom
    # (testsrc spans black..white -> full).
    assert diag.rangeObserved == "full-estimated"
    # Colorspace metadata reused from the canonical probe.
    assert diag.colorspaceMetadata.pixelFormat == "yuv420p"
    # No reference -> no gamma estimate.
    assert diag.gammaShiftEstimate is None
    # Perceptual note is owned by the perceptual layer.
    assert diag.perceptualNote == ""


def test_analyze_color_bt601_tags(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    path = tmp_path / "bt601.mp4"
    _make_bt601_mp4(path)
    diag = analyze_color(path)
    # Tagged bt601/NTSC metadata survives encode -> probe -> packet.
    assert diag.colorspaceMetadata.colorSpace == "smpte170m"
    assert diag.colorspaceMetadata.colorPrimaries == "smpte170m"
    assert diag.colorspaceMetadata.colorTransfer == "smpte170m"
    # Tagged tv range is reported as the normalized "limited".
    assert diag.rangeObserved == "limited"


def test_analyze_color_gray_still_zero_saturation(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    gray = tmp_path / "gray.png"
    _make_still_png(gray, "gray")
    diag = analyze_color(gray)
    assert diag.saturationEstimate < 0.02
    # Neutral gray: channels equal, luma equals the channel value.
    r, g, b = diag.meanRgb
    assert abs(r - g) < 1.0 and abs(g - b) < 1.0
    assert abs(diag.meanLuma - r) < 1.0


# --- Reference shift detection (1F source still / 3F frames) ---


def test_compute_color_shift_red_vs_darkred(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    red = tmp_path / "red.png"
    darkred = tmp_path / "darkred.png"
    _make_still_png(red, "red")        # (255, 0, 0)
    _make_still_png(darkred, "0x800000")  # (128, 0, 0)
    shift = compute_color_shift(red, darkred)
    assert shift["measured"] is True
    dr, dg, db = shift["deltaRgb"]
    assert abs(dr - 127.0) <= 3.0
    assert abs(dg) <= 2.0
    assert abs(db) <= 2.0
    # Rec.601 luma delta: 0.299 * 127 ≈ +38.
    assert 30.0 < shift["deltaLuma"] < 46.0
    # Brighter than the reference under the pure-gamma model -> ratio < 1.
    assert shift["gammaShiftEstimate"] is not None
    assert 0.4 < shift["gammaShiftEstimate"] < 0.9


def test_analyze_color_with_reference_fills_gamma(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    red = tmp_path / "red.png"
    darkred = tmp_path / "darkred.png"
    _make_still_png(red, "red")
    _make_still_png(darkred, "0x800000")
    diag = analyze_color(red, reference_path=darkred)
    # Target stats are exact for a lossless PNG still.
    assert abs(diag.meanRgb[0] - 255.0) <= 2.0
    assert abs(diag.meanRgb[1]) <= 2.0
    assert abs(diag.meanRgb[2]) <= 2.0
    assert abs(diag.meanLuma - 0.299 * 255.0) <= 2.0
    assert diag.saturationEstimate > 0.95
    assert diag.gammaShiftEstimate is not None
    assert 0.4 < diag.gammaShiftEstimate < 0.9


def test_analyze_color_identity_reference_no_shift(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    red = tmp_path / "red.png"
    _make_still_png(red, "red")
    shift = compute_color_shift(red, red)
    assert shift["measured"] is True
    assert abs(shift["deltaLuma"]) < 1e-6
    assert all(abs(d) < 1e-6 for d in shift["deltaRgb"])
    assert shift["gammaShiftEstimate"] is not None
    assert abs(shift["gammaShiftEstimate"] - 1.0) < 1e-6


def test_compute_color_shift_missing_reference(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    red = tmp_path / "red.png"
    _make_still_png(red, "red")
    shift = compute_color_shift(red, tmp_path / "does_not_exist.png")
    assert shift["measured"] is False
    assert shift["gammaShiftEstimate"] is None
    # And analyze_color still measures the target, just without a gamma estimate.
    diag = analyze_color(red, reference_path=tmp_path / "does_not_exist.png")
    assert diag.meanLuma > 0
    assert diag.gammaShiftEstimate is None


# --- Graceful degradation (never raises) ---


def test_analyze_color_degrades_when_ffmpeg_absent(monkeypatch, testsrc_mp4: Path) -> None:
    """ffmpeg gone, ffprobe present: colorspace metadata kept, stats zeroed."""
    monkeypatch.setattr(color_diag, "_find_ffmpeg", lambda: None)
    diag = analyze_color(testsrc_mp4)
    assert isinstance(diag, ColorDiagnostics)
    assert diag.meanRgb == (0.0, 0.0, 0.0)
    assert diag.meanLuma == 0.0
    assert diag.saturationEstimate == 0.0
    assert diag.rangeObserved == "unknown"
    assert diag.gammaShiftEstimate is None
    # Metadata still probed via ffprobe.
    assert diag.colorspaceMetadata.pixelFormat == "yuv420p"


def test_analyze_color_degrades_when_ffmpeg_path_spoofed(monkeypatch, testsrc_mp4: Path, tmp_path: Path) -> None:
    bogus = str(tmp_path / "nonexistent_ffmpeg.exe")
    monkeypatch.setattr(color_diag, "_find_ffmpeg", lambda: bogus)
    diag = analyze_color(testsrc_mp4)
    assert diag.meanLuma == 0.0
    assert diag.colorspaceMetadata.pixelFormat == "yuv420p"


def test_analyze_color_degrades_when_both_absent(monkeypatch, testsrc_mp4: Path) -> None:
    monkeypatch.setattr(media_probe, "_find_ffprobe", lambda: None)
    monkeypatch.setattr(color_diag, "_find_ffmpeg", lambda: None)
    diag = analyze_color(testsrc_mp4)
    assert diag.meanRgb == (0.0, 0.0, 0.0)
    assert diag.meanLuma == 0.0
    assert diag.rangeObserved == "unknown"
    assert diag.colorspaceMetadata.colorSpace == "unknown"
    assert diag.colorspaceMetadata.pixelFormat == "unknown"


def test_analyze_color_missing_file() -> None:
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    diag = analyze_color("no/such/file.mp4")
    assert isinstance(diag, ColorDiagnostics)
    assert diag.meanLuma == 0.0
    assert diag.saturationEstimate == 0.0
