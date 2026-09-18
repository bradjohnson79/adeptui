"""Deterministic color diagnostics (Ch 25 of the Media Intelligence Packet).

Representative frames are decoded via ffmpeg to RGB24 and measured with
numpy — pure CPU, no GPU, no model inference. Populates the frozen
``ColorDiagnostics`` schema:

- ``meanRgb`` / ``meanLuma`` — per-channel mean and Rec.601 luma over the
  sampled frames, on the 0-255 scale (matching the fidelity mission's
  reporting convention).
- ``saturationEstimate`` — mean per-pixel HSV-style saturation
  ``(max-min)/max``, 0..1.
- ``rangeObserved`` — the container's tagged color range when present
  (normalized to ``limited``/``full``); otherwise a decoded-RGB headroom
  estimate (``limited-estimated`` / ``full-estimated`` / ``unknown``).
  Honestly labelled: post-conversion RGB cannot prove the encoded range.
- ``colorspaceMetadata`` — reused from the canonical
  ``media_probe.probe_colorspace`` (never duplicated here).
- ``gammaShiftEstimate`` — only when a reference is supplied: ratio of
  effective gamma under a pure-gamma model,
  ``log(luma/255) / log(refLuma/255)``. 1.0 means no shift; < 1 means the
  target sits brighter than the reference, > 1 darker.

When ``reference_path`` is given (1F source still, or a 3F
START/MIDDLE/END frame), ``compute_color_shift`` additionally exposes the
raw mean-RGB/luma deltas for shift detection. References may be stills or
videos — means are resolution-independent, so no resize is needed.

Degrades gracefully: missing ffmpeg/ffprobe, undecodable files, or missing
references yield zeroed diagnostics (colorspace metadata is still filled
whenever ffprobe can read it). Never raises.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from .media_packet import ColorDiagnostics
from .media_probe import probe_colorspace, probe_media

# Frame-decode timeout (seconds). Bounded so a hung ffmpeg never wedges the
# diagnostics layer.
_DECODE_TIMEOUT_SEC = 120.0

# Decoded-RGB headroom bounds for the range estimate (8-bit scale).
_RANGE_LIMITED_MIN = 12.0
_RANGE_LIMITED_MAX = 243.0
_RANGE_FULL_MIN = 4.0
_RANGE_FULL_MAX = 251.0


def _find_ffmpeg() -> str | None:
    """Resolve the ffmpeg binary via PATH. Never hardcodes a path."""
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def _frame_indices(frame_count: int) -> list[int]:
    """Deterministic representative frame indices: first / middle / last."""
    if frame_count >= 3:
        return sorted({0, frame_count // 2, frame_count - 1})
    return [0]


def _decode_rgb_frames(
    path: str | Path,
    width: int,
    height: int,
    frame_indices: list[int],
) -> np.ndarray | None:
    """Decode selected frames to RGB24 via ffmpeg.

    Returns an ``[F, H, W, 3]`` uint8 array, or ``None`` when ffmpeg is
    absent, dimensions are unknown, the call fails, or no frame decodes.
    Never raises.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg or width <= 0 or height <= 0 or not frame_indices:
        return None

    select = "select=" + "+".join(f"eq(n\\,{i})" for i in frame_indices)
    cmd = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(path),
        "-vf",
        select,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=_DECODE_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    except Exception:  # noqa: BLE001 — diagnostics never crash
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None

    frame_bytes = width * height * 3
    n_frames = len(proc.stdout) // frame_bytes
    if n_frames <= 0:
        return None
    raw = proc.stdout[: n_frames * frame_bytes]
    return np.frombuffer(raw, dtype=np.uint8).reshape(n_frames, height, width, 3)


def _sample_rgb(path: str | Path) -> np.ndarray | None:
    """Probe dimensions/frame count, then decode representative frames.

    Returns an ``[M, 3]`` float64 pixel matrix pooled across the sampled
    frames, or ``None`` on any failure. Never raises.
    """
    facts = probe_media(path)
    if facts.width <= 0 or facts.height <= 0:
        return None
    frames = _decode_rgb_frames(path, facts.width, facts.height, _frame_indices(facts.frameCount))
    if frames is None or frames.size == 0:
        return None
    return frames.reshape(-1, 3).astype(np.float64)


def _rgb_stats(pixels: np.ndarray) -> dict[str, Any]:
    """Mean RGB, Rec.601 luma, and mean HSV-style saturation for pixels."""
    mean_rgb = pixels.mean(axis=0)
    luma = 0.299 * pixels[:, 0] + 0.587 * pixels[:, 1] + 0.114 * pixels[:, 2]
    mx = pixels.max(axis=1)
    mn = pixels.min(axis=1)
    saturation = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    return {
        "meanRgb": (float(mean_rgb[0]), float(mean_rgb[1]), float(mean_rgb[2])),
        "meanLuma": float(luma.mean()),
        "saturationEstimate": float(saturation.mean()),
        "observedMin": float(pixels.min()),
        "observedMax": float(pixels.max()),
    }


def _observed_range(color_range_tag: str, observed_min: float, observed_max: float) -> str:
    """Normalize the tagged range, else estimate from decoded-RGB headroom."""
    tag = (color_range_tag or "").strip().lower()
    if tag in ("tv", "limited", "mpeg"):
        return "limited"
    if tag in ("pc", "full", "jpeg"):
        return "full"
    if observed_min >= _RANGE_LIMITED_MIN and observed_max <= _RANGE_LIMITED_MAX:
        return "limited-estimated"
    if observed_min <= _RANGE_FULL_MIN and observed_max >= _RANGE_FULL_MAX:
        return "full-estimated"
    return "unknown"


def _gamma_shift(mean_luma: float, reference_luma: float) -> float | None:
    """Effective-gamma ratio under a pure-gamma model. 1.0 = no shift."""
    if not (0.0 < mean_luma < 255.0 and 0.0 < reference_luma < 255.0):
        return None
    return math.log(mean_luma / 255.0) / math.log(reference_luma / 255.0)


def compute_color_shift(path: str | Path, reference_path: str | Path) -> dict[str, Any]:
    """Mean-RGB/luma delta between a target and a reference (shift detection).

    ``reference_path`` may be a 1F source still or a 3F START/MIDDLE/END
    frame (image or video). Returns ``{"deltaRgb", "deltaLuma",
    "gammaShiftEstimate"}``; all values are ``None``/zero-tuples when either
    side cannot be measured. Never raises.
    """
    empty: dict[str, Any] = {
        "deltaRgb": (0.0, 0.0, 0.0),
        "deltaLuma": 0.0,
        "gammaShiftEstimate": None,
        "measured": False,
    }
    target_px = _sample_rgb(path)
    reference_px = _sample_rgb(reference_path)
    if target_px is None or reference_px is None:
        return empty

    target = _rgb_stats(target_px)
    reference = _rgb_stats(reference_px)
    delta_rgb = tuple(t - r for t, r in zip(target["meanRgb"], reference["meanRgb"]))
    delta_luma = target["meanLuma"] - reference["meanLuma"]
    return {
        "deltaRgb": (float(delta_rgb[0]), float(delta_rgb[1]), float(delta_rgb[2])),
        "deltaLuma": float(delta_luma),
        "gammaShiftEstimate": _gamma_shift(target["meanLuma"], reference["meanLuma"]),
        "measured": True,
    }


def analyze_color(path: str | Path, reference_path: str | Path | None = None) -> ColorDiagnostics:
    """Measure an asset's color and return the frozen ``ColorDiagnostics``.

    Colorspace metadata is always attempted via the canonical
    ``media_probe.probe_colorspace`` — even when frame decode fails — so a
    tagged file still yields its metadata. With ``reference_path`` given,
    the measured mean-RGB/luma delta fills ``gammaShiftEstimate``.
    ``perceptualNote`` stays empty (set by the perceptual layer). Never
    raises.
    """
    colorspace = probe_colorspace(path)

    pixels = _sample_rgb(path)
    if pixels is None:
        # ffmpeg absent / undecodable / unknown dimensions — metadata only.
        return ColorDiagnostics(colorspaceMetadata=colorspace)

    stats = _rgb_stats(pixels)
    range_observed = _observed_range(colorspace.colorRange, stats["observedMin"], stats["observedMax"])

    gamma_shift: float | None = None
    if reference_path is not None:
        shift = compute_color_shift(path, reference_path)
        if shift["measured"]:
            gamma_shift = shift["gammaShiftEstimate"]

    return ColorDiagnostics(
        meanRgb=stats["meanRgb"],
        meanLuma=stats["meanLuma"],
        saturationEstimate=stats["saturationEstimate"],
        gammaShiftEstimate=gamma_shift,
        rangeObserved=range_observed,
        colorspaceMetadata=colorspace,
    )
