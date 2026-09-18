"""Deterministic audio diagnostics (Ch 26-27 of the Media Intelligence Packet).

Promoted and generalized from the MiniMax H3 fidelity mission's ad-hoc
amplitude scan (``.runtime/_fidelity_analyze.py``): hardcoded paths and
print-based reporting are replaced by a reusable, never-raising API that
populates the frozen ``AudioDiagnostics`` schema and localizes distortion
into ``DistortionSpan`` records.

Pure CPU: ffmpeg decode -> float32 PCM -> numpy measurement. No GPU, no
model inference, no VLM. Every fact here is measured, never perceived.

Design rules (non-negotiable, matching ``media_probe``):

- Resolve ffmpeg via ``shutil.which`` — never hardcode the binary path.
- Stream-level facts (sampleRate, channels) come from the canonical
  ``media_probe.probe_audio_stream`` — ffprobe logic is NOT duplicated here.
- Degrade, never crash: if ffmpeg/ffprobe is absent, the file is
  undecodable, or there is no audio stream, return a zeroed
  ``AudioDiagnostics`` (and ``[]`` for distortion spans). Never raise.

Memory note: decoding reads the whole stream into memory as float32
(≈ 11.5 MB per minute of stereo 48 kHz). That is bounded and acceptable
for diagnostic passes over generated assets.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np

from .media_packet import AudioDiagnostics, DistortionSpan
from .media_probe import probe_audio_stream

# Decode timeout (seconds). Bounded so a hung ffmpeg never wedges the
# diagnostics layer; generous enough for multi-minute assets.
_DECODE_TIMEOUT_SEC = 180.0

# A sample whose magnitude is at/above this fraction of full scale counts
# as clipped (matches the fidelity mission's 0.99 rail).
_CLIP_THRESHOLD = 0.99

# Short-time window for silence / noise / distortion localization (50 ms).
_WINDOW_SEC = 0.05

# A 50 ms window whose RMS is below this counts as silent (~-80 dBFS).
_SILENCE_RMS = 1e-4

# Percentile of short-time window RMS used for the energy floor, and the
# percentile of per-window median spectral magnitude used for the spectral
# noise floor. Low percentiles track the quietest moments of the signal.
_FLOOR_PERCENTILE = 5.0

# FFT size for spectral measurements (≈ 42 ms at 48 kHz).
_SPECTRAL_FFT = 2048

# --- Distortion span thresholds (deterministic, documented) ---

# A window is flagged as clipping when more than this fraction of its
# samples sit at/above the clip rail.
_CLIP_WINDOW_FRACTION = 0.01
# A window is flagged as static when its RMS is at least this (audible)
# AND its spectral flatness meets the broadband-noise bar below.
_STATIC_MIN_RMS = 0.01
_STATIC_MIN_FLATNESS = 0.45
# Severity ladders.
_CLIP_MODERATE_FRACTION = 0.02
_CLIP_MAJOR_FRACTION = 0.10
_STATIC_MODERATE_FLATNESS = 0.55
_STATIC_MAJOR_FLATNESS = 0.70
_STATIC_MAJOR_RMS = 0.05


def _find_ffmpeg() -> str | None:
    """Resolve the ffmpeg binary via PATH. Never hardcodes a path.

    ``shutil.which`` is case-insensitive and consults PATHEXT on Windows, so
    ``shutil.which("ffmpeg")`` finds ``ffmpeg.EXE``. The ``ffmpeg.exe``
    fallback is belt-and-suspenders for odd PATH configurations.
    """
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def _to_int(value: object) -> int:
    """Best-effort int conversion. Returns 0 for absent / unparseable values."""
    if value is None:
        return 0
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def decode_audio_pcm(path: str | Path, sample_rate: int | None = None) -> tuple[np.ndarray, int]:
    """Decode arbitrary audio to float32 PCM via ffmpeg.

    Returns ``(samples, sample_rate)`` where ``samples`` is an ``[N, C]``
    float32 array (C = channel count, deinterleaved). When ``sample_rate``
    is given the stream is resampled to that rate; otherwise the source
    rate is kept.

    Returns ``(empty [0, 1] array, 0)`` when ffmpeg is absent, the call
    fails, or the decode yields no samples. Never raises.
    """
    empty = np.zeros((0, 1), dtype=np.float32)
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return empty, 0

    stream = probe_audio_stream(path)
    channels = _to_int(stream.get("channels"))
    if channels <= 0:
        channels = 1  # deinterleave fallback: treat as mono

    cmd = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
    ]
    if sample_rate and sample_rate > 0:
        cmd += ["-ar", str(sample_rate)]
    cmd += ["-"]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=_DECODE_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return empty, 0
    except Exception:  # noqa: BLE001 — last-line defense; diagnostics never crash
        return empty, 0
    if proc.returncode != 0 or not proc.stdout:
        return empty, 0

    arr = np.frombuffer(proc.stdout, dtype=np.float32)
    if arr.size == 0:
        return empty, 0
    # Deinterleave: drop any trailing partial frame, then reshape [N, C].
    usable = arr.size - (arr.size % channels)
    if usable <= 0:
        return empty, 0
    arr = arr[:usable].reshape(-1, channels)

    out_sr = sample_rate if sample_rate and sample_rate > 0 else _to_int(stream.get("sample_rate"))
    return arr, out_sr


def _windowed_rms(mono: np.ndarray, window: int) -> np.ndarray:
    """RMS per non-overlapping window of ``window`` samples (tail dropped)."""
    if mono.size < window or window <= 0:
        return np.zeros(0, dtype=np.float64)
    n_win = mono.size // window
    framed = mono[: n_win * window].reshape(n_win, window)
    return np.sqrt(np.mean(framed * framed, axis=1))


def _spectral_floor_db(mono: np.ndarray, sample_rate: int) -> float | None:
    """Estimated spectral noise floor in dB (deterministic).

    Per FFT window: magnitude spectrum of the Hann-windowed mono signal,
    then the MEDIAN bin magnitude (robust to tones — a clean sine leaves
    most bins near zero, so its floor is low; broadband static fills all
    bins, so its floor is high). The floor is the low percentile of those
    per-window medians, normalized to approximate full-scale amplitude and
    expressed in dB. Relative comparison is the intended use; absolute dB
    depends on the FFT size and window.
    """
    win = min(_SPECTRAL_FFT, mono.size)
    if win < 64 or sample_rate <= 0:
        return None
    n_win = mono.size // win
    if n_win <= 0:
        return None
    hann = np.hanning(win).astype(np.float64)
    framed = mono[: n_win * win].reshape(n_win, win).astype(np.float64) * hann
    mags = np.abs(np.fft.rfft(framed, axis=1))
    if mags.shape[1] < 2:
        return None
    # Median across bins (skip DC), then low percentile across windows.
    per_window = np.median(mags[:, 1:], axis=1)
    floor = float(np.percentile(per_window, _FLOOR_PERCENTILE))
    # Hann coherent gain ≈ 0.5 → amplitude ≈ magnitude * 2 / win.
    amp = floor * 2.0 / win
    return 20.0 * math.log10(max(amp, 1e-12))


def _spectral_flatness(mono: np.ndarray, window: int) -> np.ndarray:
    """Spectral flatness (0 = tonal, 1 = white noise) per window.

    Geometric mean / arithmetic mean of the power spectrum. Deterministic
    broadband-noise discriminator used for static detection.
    """
    if mono.size < window or window <= 0:
        return np.zeros(0, dtype=np.float64)
    n_win = mono.size // window
    framed = mono[: n_win * window].reshape(n_win, window).astype(np.float64)
    power = np.abs(np.fft.rfft(framed, axis=1)) ** 2
    power = power[:, 1:]  # skip DC
    eps = 1e-20
    geo = np.exp(np.mean(np.log(power + eps), axis=1))
    arith = np.mean(power + eps, axis=1)
    return geo / np.maximum(arith, eps)


def _measure_pcm(arr: np.ndarray, sample_rate: int, channels: int) -> AudioDiagnostics:
    """Pure numpy measurement over decoded PCM. Never raises.

    NaN/Inf samples are counted, then excluded from amplitude statistics so
    a corrupt region cannot poison the whole measurement.
    """
    if arr.size == 0 or sample_rate <= 0:
        return AudioDiagnostics(sampleRate=sample_rate, channels=channels)

    nan_count = int(np.isnan(arr).sum())
    inf_count = int(np.isinf(arr).sum())
    finite_mask = np.isfinite(arr)
    finite = arr[finite_mask]
    if finite.size == 0:
        return AudioDiagnostics(
            sampleRate=sample_rate,
            channels=channels,
            nanCount=nan_count,
            infCount=inf_count,
        )

    finite64 = finite.astype(np.float64)
    peak = float(np.max(np.abs(finite64)))
    rms = float(np.sqrt(np.mean(finite64 * finite64)))
    clipping_fraction = float((np.abs(finite64) >= _CLIP_THRESHOLD).mean())

    # DC offset is measured per channel; the scalar surfaced is the WORST
    # (max absolute) per-channel offset — the diagnostic-relevant figure.
    dc_offset: float | None = None
    if arr.shape[1] > 0:
        per_ch_dc = []
        for c in range(arr.shape[1]):
            col = arr[:, c]
            col_finite = col[np.isfinite(col)]
            if col_finite.size:
                per_ch_dc.append(abs(float(col_finite.astype(np.float64).mean())))
        if per_ch_dc:
            dc_offset = max(per_ch_dc)

    # Mono mixdown for windowed measurements (finite samples only).
    mono = np.zeros(arr.shape[0], dtype=np.float64)
    for c in range(arr.shape[1]):
        col = arr[:, c].astype(np.float64)
        mono += np.where(np.isfinite(col), col, 0.0)
    mono /= max(arr.shape[1], 1)

    window = max(1, int(sample_rate * _WINDOW_SEC))
    win_rms = _windowed_rms(mono, window)
    silence_fraction = (
        float((win_rms < _SILENCE_RMS).mean()) if win_rms.size else (1.0 if rms < _SILENCE_RMS else 0.0)
    )

    spectral_floor = _spectral_floor_db(mono, sample_rate)

    return AudioDiagnostics(
        sampleRate=sample_rate,
        channels=channels,
        peak=peak,
        rms=rms,
        clippingFraction=clipping_fraction,
        dcOffset=dc_offset,
        nanCount=nan_count,
        infCount=inf_count,
        silenceFraction=silence_fraction,
        spectralNoiseFloor=spectral_floor,
    )


def analyze_audio(path: str | Path) -> AudioDiagnostics:
    """Measure an asset's audio and return the frozen ``AudioDiagnostics``.

    Stream-level facts (sampleRate, channels) come from the canonical
    ``media_probe.probe_audio_stream``; PCM-level measurement (peak, RMS,
    clipping, DC offset, NaN/Inf, silence, spectral noise floor) is done
    here on the decoded float32 signal.

    Degrades gracefully: ffprobe absent / no audio stream -> fully zeroed
    diagnostics; ffmpeg absent / decode failure -> stream facts populated,
    PCM metrics zeroed. Never raises.
    """
    stream = probe_audio_stream(path)
    if not stream:
        # ffprobe absent, undecodable file, or no audio stream.
        return AudioDiagnostics()

    sample_rate = _to_int(stream.get("sample_rate"))
    channels = _to_int(stream.get("channels"))

    pcm, out_sr = decode_audio_pcm(path)
    if pcm.size == 0:
        # ffmpeg absent or decode failed — keep the stream facts, zero the rest.
        return AudioDiagnostics(sampleRate=sample_rate, channels=channels)

    return _measure_pcm(pcm, out_sr or sample_rate, channels or pcm.shape[1])


def _merge_spans(flags: np.ndarray, window_sec: float) -> list[tuple[int, int, float, float]]:
    """Merge contiguous flagged windows into (start_idx, end_idx, t0, t1) runs."""
    spans: list[tuple[int, int, float, float]] = []
    start: int | None = None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            spans.append((start, i - 1, start * window_sec, i * window_sec))
            start = None
    if start is not None:
        spans.append((start, len(flags) - 1, start * window_sec, len(flags) * window_sec))
    return spans


def _clip_severity(span_clip_fraction: float) -> str:
    if span_clip_fraction >= _CLIP_MAJOR_FRACTION:
        return "major"
    if span_clip_fraction >= _CLIP_MODERATE_FRACTION:
        return "moderate"
    return "minor"


def _static_severity(mean_flatness: float, mean_rms: float) -> str:
    if mean_flatness >= _STATIC_MAJOR_FLATNESS and mean_rms >= _STATIC_MAJOR_RMS:
        return "major"
    if mean_flatness >= _STATIC_MODERATE_FLATNESS:
        return "moderate"
    return "minor"


def locate_distortions(
    pcm: np.ndarray,
    sample_rate: int,
    *,
    window_sec: float = _WINDOW_SEC,
    boundary: str = "asset-decode",
) -> list[DistortionSpan]:
    """Localize clipping and static into ``DistortionSpan`` records (Ch 27).

    Operates on the decoded PCM scan (``decode_audio_pcm`` output). Windows
    of ``window_sec`` seconds are flagged as:

    - ``clipping`` — more than 1% of window samples at/above the 0.99 rail;
      severity from the span's overall clipped-sample fraction
      (>=10% major, >=2% moderate, else minor).
    - ``static`` — audible (RMS >= 0.01) broadband noise (spectral flatness
      >= 0.45); severity from span mean flatness/RMS.

    ``boundary`` labels which pipeline boundary the PCM was measured at
    (e.g. ``asset-decode``, ``raw-decode``, ``final-mux``) so reports can
    attribute the distortion. Frame indices stay None (audio measurement);
    confidence is 1.0 — this is a deterministic measurement, not a guess.

    Returns ``[]`` for empty/invalid input. Never raises.
    """
    if pcm.size == 0 or sample_rate <= 0 or window_sec <= 0:
        return []

    mono = pcm.astype(np.float64).mean(axis=1)
    mono = np.where(np.isfinite(mono), mono, 0.0)
    window = max(1, int(sample_rate * window_sec))
    n_win = mono.size // window
    if n_win <= 0:
        return []
    framed = mono[: n_win * window].reshape(n_win, window)

    win_rms = np.sqrt(np.mean(framed * framed, axis=1))
    win_clip_frac = (np.abs(framed) >= _CLIP_THRESHOLD).mean(axis=1)
    win_flat = _spectral_flatness(mono, window)

    spans: list[DistortionSpan] = []

    clip_flags = win_clip_frac > _CLIP_WINDOW_FRACTION
    for start_idx, end_idx, t0, t1 in _merge_spans(clip_flags, window_sec):
        span_clip_fraction = float(win_clip_frac[start_idx : end_idx + 1].mean())
        spans.append(
            DistortionSpan(
                startTime=t0,
                endTime=t1,
                confidence=1.0,
                severity=_clip_severity(span_clip_fraction),
                distortionType="clipping",
                boundary=boundary,
            )
        )

    # Windows already explained by clipping are not double-labelled static —
    # a rail-pinned (or pure-DC) window has a degenerate spectrum that would
    # otherwise masquerade as broadband noise.
    static_flags = (win_rms >= _STATIC_MIN_RMS) & (win_flat >= _STATIC_MIN_FLATNESS) & ~clip_flags
    for start_idx, end_idx, t0, t1 in _merge_spans(static_flags, window_sec):
        mean_flat = float(win_flat[start_idx : end_idx + 1].mean())
        mean_rms = float(win_rms[start_idx : end_idx + 1].mean())
        spans.append(
            DistortionSpan(
                startTime=t0,
                endTime=t1,
                confidence=1.0,
                severity=_static_severity(mean_flat, mean_rms),
                distortionType="static",
                boundary=boundary,
            )
        )

    spans.sort(key=lambda s: (s.startTime or 0.0, s.distortionType))
    return spans


def detect_distortions(path: str | Path, *, boundary: str = "asset-decode") -> list[DistortionSpan]:
    """Decode an asset's audio and localize clipping/static spans.

    Convenience wrapper: ``decode_audio_pcm`` + ``locate_distortions``.
    Returns ``[]`` when ffmpeg/ffprobe is absent, there is no audio stream,
    or the decode fails. Never raises.
    """
    pcm, sample_rate = decode_audio_pcm(path)
    if pcm.size == 0 or sample_rate <= 0:
        return []
    return locate_distortions(pcm, sample_rate, boundary=boundary)
