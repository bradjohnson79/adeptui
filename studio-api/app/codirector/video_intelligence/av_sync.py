"""Deterministic A/V sync diagnostics (Ch 28 of the Media Intelligence Packet).

Container-level sync facts measured with ffprobe only — no decode, no GPU,
no model inference. Populates the frozen ``AVSyncDiagnostics`` schema:

- ``videoDurationSec`` / ``audioDurationSec`` — per-stream durations
  (format duration as fallback when a stream omits its own).
- ``videoStartOffsetSec`` / ``audioStartOffsetSec`` — per-stream
  ``start_time`` (container edit offsets).
- ``driftSec`` — audio minus video duration delta. Positive means the
  audio runs longer than the video (e.g. trailing padding, encoder delay).
- ``speechLipMismatch`` stays ``None`` — that is a perceptual judgement
  made by the VLM layer, never by this deterministic probe.

Reuses ``media_probe._run_ffprobe_json`` (same-package import) so ffprobe
invocation, timeout, and degradation logic live in exactly one place.
Degrades to a zeroed ``AVSyncDiagnostics`` when ffprobe is absent or the
file is undecodable. Never raises.
"""

from __future__ import annotations

from pathlib import Path

from .media_packet import AVSyncDiagnostics
from .media_probe import _run_ffprobe_json, _to_float


def measure_av_sync(path: str | Path) -> AVSyncDiagnostics:
    """Measure container-level A/V sync facts for a media file.

    One ffprobe call (via the canonical ``media_probe`` wrapper). When the
    file has no audio stream, audio duration/offset are 0.0 and drift is
    reported as 0.0 — with no audio there is no delta to measure. Never
    raises.
    """
    data = _run_ffprobe_json(path)
    if not data:
        return AVSyncDiagnostics()

    streams = data.get("streams") or []
    fmt = data.get("format") or {}

    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    format_duration = _to_float(fmt.get("duration"))

    video_duration = 0.0
    video_start = 0.0
    if video:
        video_duration = _to_float(video.get("duration"))
        if video_duration <= 0:
            video_duration = format_duration
        video_start = _to_float(video.get("start_time"))

    audio_duration = 0.0
    audio_start = 0.0
    drift = 0.0
    if audio:
        audio_duration = _to_float(audio.get("duration"))
        if audio_duration <= 0:
            audio_duration = format_duration
        audio_start = _to_float(audio.get("start_time"))
        drift = audio_duration - video_duration

    return AVSyncDiagnostics(
        videoDurationSec=video_duration,
        audioDurationSec=audio_duration,
        videoStartOffsetSec=video_start,
        audioStartOffsetSec=audio_start,
        driftSec=drift,
        speechLipMismatch=None,  # perceptual — set by the VLM layer, never here
    )
