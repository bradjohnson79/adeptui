"""Canonical deterministic media probe for the Adept Media Intelligence Service.

ONE reusable ffprobe wrapper that returns the full frozen ``MediaFacts``
schema (Ch 4, 24 of the Media Intelligence Packet). This consolidates the
five+ fragmented ffprobe helpers that previously lived in:

- ``app.magi.media`` (``probe_media`` / ``ffprobe_json``) — structured, video-focused
- ``app.minimax_h3.route_a_adapter`` (``validate_media`` / ``_stream_colorspace``)
- ``app.video_runtime.output_gate`` (``_ffprobe_json``) — video-focused
- ``app.media_clip`` (``probe_video_duration``) — duration only
- ``app.character_identity.voice`` — WAV/non-WAV probes

This module is the single canonical authority. Existing callers are NOT
migrated here yet (avoid collisions with in-flight work); a later migration
task will swap them over one at a time.

Design rules (non-negotiable):

- Resolve ffprobe via ``shutil.which`` — never hardcode the binary path.
- Diagnostics must degrade, not crash: if ffprobe is absent, the file is
  undecodable, or the call fails, return a zeroed ``MediaFacts`` with
  ``hasAudio=False``. Never raise.
- One ffprobe call per ``probe_media`` (``-show_streams -show_format -of json``).
- Populate the FULL ``MediaFacts`` schema including ``ColorspaceTags``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .media_packet import ColorspaceTags, MediaFacts

# ffprobe call timeout (seconds). Generous enough for large files, bounded so
# a hung probe never wedges the diagnostics layer.
_PROBE_TIMEOUT_SEC = 60.0


def _find_ffprobe() -> str | None:
    """Resolve the ffprobe binary via PATH. Never hardcodes a path.

    ``shutil.which`` is case-insensitive and consults PATHEXT on Windows, so
    ``shutil.which("ffprobe")`` finds ``ffprobe.EXE``. The ``ffprobe.exe``
    fallback is belt-and-suspenders for odd PATH configurations.
    """
    return shutil.which("ffprobe") or shutil.which("ffprobe.exe")


def _clean_colorspace_value(value: Any) -> str:
    """Normalize an ffprobe colorspace field to a non-empty string.

    ffprobe reports ``unknown`` for untagged streams and may omit a field
    entirely. Both collapse to ``"unknown"`` so ``ColorspaceTags`` is always
    fully populated (never an empty string), matching the frozen schema's
    default and the audit requirement that tags be populated even when
    unknown.
    """
    if value is None:
        return "unknown"
    s = str(value).strip()
    if not s or s.lower() == "unknown" or s.lower() == "n/a":
        return "unknown"
    return s


def _colorspace_from_stream(stream: dict[str, Any]) -> ColorspaceTags:
    """Map an ffprobe video stream dict to ``ColorspaceTags``.

    ffprobe keys (snake_case) -> ColorspaceTags fields (camelCase):
        color_space      -> colorSpace
        color_transfer    -> colorTransfer
        color_primaries   -> colorPrimaries
        color_range       -> colorRange
        pix_fmt           -> pixelFormat
    """
    return ColorspaceTags(
        colorSpace=_clean_colorspace_value(stream.get("color_space")),
        colorTransfer=_clean_colorspace_value(stream.get("color_transfer")),
        colorPrimaries=_clean_colorspace_value(stream.get("color_primaries")),
        colorRange=_clean_colorspace_value(stream.get("color_range")),
        pixelFormat=_clean_colorspace_value(stream.get("pix_fmt")),
    )


def _parse_frame_rate(rate: Any) -> float:
    """Parse an ffprobe fractional frame rate (e.g. ``"24/1"`` or ``"30000/1001"``).

    Returns 0.0 for absent / unparseable / ``"0/0"`` values. Never raises.
    """
    if rate is None:
        return 0.0
    s = str(rate).strip()
    if not s or s.lower() in ("n/a", "unknown"):
        return 0.0
    try:
        if "/" in s:
            num_str, den_str = s.split("/", 1)
            num = float(num_str)
            den = float(den_str)
            if den <= 0:
                return 0.0
            return num / den
        return float(s)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _to_int(value: Any) -> int:
    """Best-effort int conversion. Returns 0 for absent / unparseable values."""
    if value is None:
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    """Best-effort float conversion. Returns 0.0 for absent / unparseable values."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _run_ffprobe_json(path: str | Path) -> dict[str, Any] | None:
    """Run a single ``ffprobe -show_streams -show_format -of json`` call.

    Returns the parsed JSON dict, or ``None`` when ffprobe is absent, the
    call fails, or the output is not valid JSON. Never raises.
    """
    ffprobe = _find_ffprobe()
    if not ffprobe:
        return None
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        # ffprobe missing at runtime, or the OS refused to launch it. Degrade.
        return None
    except Exception:  # noqa: BLE001 — last-line defense; diagnostics never crash
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def probe_media(path: str | Path) -> MediaFacts:
    """Probe a media file and return the full frozen ``MediaFacts`` schema.

    One ffprobe call (``-show_streams -show_format -of json``). Degrades
    gracefully: if ffprobe is absent, the file is undecodable, or the call
    fails, returns a zeroed ``MediaFacts`` with ``hasAudio=False`` (never
    raises — diagnostics must degrade, not crash).

    Populates: container, videoCodec, audioCodec, width, height, fps,
    frameCount, durationSec, sampleRate, channels, bitrate, hasAudio, and
    colorspace (``ColorspaceTags``).
    """
    data = _run_ffprobe_json(path)
    if not data:
        return MediaFacts()  # zeros + hasAudio=False

    streams = data.get("streams") or []
    fmt = data.get("format") or {}

    video = next((s for s in streams if s.get("codec_type") == "video"), None) or {}
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    container = str(fmt.get("format_name") or "")
    duration_sec = _to_float(fmt.get("duration") or video.get("duration"))

    fps = _parse_frame_rate(video.get("avg_frame_rate") or video.get("r_frame_rate"))

    frame_count = _to_int(video.get("nb_frames"))
    if frame_count <= 0 and duration_sec > 0 and fps > 0:
        frame_count = max(1, int(round(duration_sec * fps)))

    bitrate = _to_int(fmt.get("bit_rate") or video.get("bit_rate"))

    audio_dict = audio or {}
    has_audio = audio is not None
    sample_rate = _to_int(audio_dict.get("sample_rate")) if has_audio else 0
    channels = _to_int(audio_dict.get("channels")) if has_audio else 0

    colorspace = _colorspace_from_stream(video) if video else ColorspaceTags()

    return MediaFacts(
        container=container,
        videoCodec=str(video.get("codec_name") or ""),
        audioCodec=str(audio_dict.get("codec_name") or "") if has_audio else "",
        width=_to_int(video.get("width")),
        height=_to_int(video.get("height")),
        fps=fps,
        frameCount=frame_count,
        durationSec=duration_sec,
        sampleRate=sample_rate,
        channels=channels,
        bitrate=bitrate,
        colorspace=colorspace,
        hasAudio=has_audio,
    )


def probe_colorspace(path: str | Path) -> ColorspaceTags:
    """Probe only the video stream's colorspace tags.

    Generalizes ``route_a_adapter._stream_colorspace`` to also surface
    ``pixelFormat`` (``pix_fmt``) and return the frozen ``ColorspaceTags``
    schema. Uses a focused ffprobe call
    (``-select_streams v:0 -show_entries stream=color_space,color_transfer,
    color_primaries,color_range,pix_fmt``). Degrades to an all-``"unknown"``
    ``ColorspaceTags`` if ffprobe is absent or the call fails (never raises).
    """
    ffprobe = _find_ffprobe()
    if not ffprobe:
        return ColorspaceTags()
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=color_space,color_transfer,color_primaries,color_range,pix_fmt",
                "-of",
                "default=noprint_wrappers=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return ColorspaceTags()
    except Exception:  # noqa: BLE001
        return ColorspaceTags()
    if proc.returncode != 0:
        return ColorspaceTags()

    raw: dict[str, str] = {}
    for line in (proc.stdout or "").splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            raw[key.strip()] = (val or "").strip()

    return ColorspaceTags(
        colorSpace=_clean_colorspace_value(raw.get("color_space")),
        colorTransfer=_clean_colorspace_value(raw.get("color_transfer")),
        colorPrimaries=_clean_colorspace_value(raw.get("color_primaries")),
        colorRange=_clean_colorspace_value(raw.get("color_range")),
        pixelFormat=_clean_colorspace_value(raw.get("pix_fmt")),
    )


def probe_audio_stream(path: str | Path) -> dict[str, Any]:
    """Probe the first audio stream and return its raw ffprobe fields.

    For the audio diagnostics layer (Ch 26 ``AudioDiagnostics``). Returns the
    raw ffprobe audio stream dict (with ``sample_rate``, ``channels``,
    ``codec_name``, ``bit_rate``, ``duration``, ``bits_per_sample``,
    ``channel_layout``, etc.) so the diagnostics layer can pick what it needs
    without re-probing. Returns ``{}`` if ffprobe is absent, the file is
    undecodable, or no audio stream is present. Never raises.
    """
    data = _run_ffprobe_json(path)
    if not data:
        return {}
    streams = data.get("streams") or []
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not audio or not isinstance(audio, dict):
        return {}
    return dict(audio)
