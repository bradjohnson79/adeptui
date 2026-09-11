"""Rebuild scene audio for a windowed media retake using a pure ffmpeg filter graph.

The graph is constructed as a string so it can be unit-tested without invoking ffmpeg.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..media_ops import run_ffmpeg


@dataclass
class AudioGraph:
    """Description of an ffmpeg filter graph for the retake soundtrack."""

    filter_complex: str
    line_inputs: list[str] = field(default_factory=list)
    output_label: str = "[aout]"


@dataclass
class _AudioSegment:
    kind: str  # "outside" or "window"
    start: float
    end: float
    window_index: int = -1  # index into sorted_windows for window segments


def _fmt(value: float) -> str:
    return f"{value:.6f}"


def _segment_label(index: int, is_window: bool) -> str:
    return f"[{'win' if is_window else 'seg'}{index}]"


def _resample_chain(sample_rate: int) -> str:
    return f"aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts=stereo"


def build_audio_filter(
    windows: list[Any],
    donor_span: tuple[float, float],
    scene_duration_sec: float,
    sample_rate: int = 32000,
    crossfade_ms: int = 30,
) -> AudioGraph:
    """Construct an ffmpeg filter graph that rebuilds the scene audio track.

    Inputs:
      - input 0: master video/audio (the original scene soundtrack).
      - inputs 1..N: replacement line audio files, one per window, in time order.

    Each window is rendered as replacement line mixed over a room-tone bed
    taken from the donor span. Segments outside windows keep the original audio.

    Timeline preservation: ``acrossfade`` overlaps its inputs by the crossfade
    duration, which would otherwise shorten the soundtrack and desync every
    later region from the video. To keep every boundary exactly on its scene
    time, each segment carries half-crossfade "handles" of extra content on
    shared boundaries, so the overlap consumes the handles — never the
    timeline. Window lines still start exactly at their window start.
    """
    if not windows:
        raise ValueError("At least one window is required to build an audio filter graph")

    sorted_windows = sorted(windows, key=lambda w: (float(w.start), float(w.end)))
    crossfade_d = crossfade_ms / 1000.0
    handle = crossfade_d / 2.0

    # Build a single unified list of segments in strict time order.
    segments: list[_AudioSegment] = []
    cursor = 0.0
    for window_index, w in enumerate(sorted_windows):
        if cursor < w.start:
            segments.append(_AudioSegment("outside", cursor, float(w.start)))
        segments.append(_AudioSegment("window", float(w.start), float(w.end), window_index))
        cursor = max(cursor, float(w.end))
    if cursor < scene_duration_sec:
        segments.append(_AudioSegment("outside", cursor, scene_duration_sec))

    donor_start, donor_end = donor_span
    donor_len = donor_end - donor_start
    if donor_len <= 0:
        raise ValueError("Donor span must have positive duration")

    n_seg = len(segments)
    filters: list[str] = []
    segment_labels: list[str] = []

    for seg_index, seg in enumerate(segments):
        # Handles: half a crossfade of extra content on each shared boundary.
        hl = handle if seg_index > 0 else 0.0
        hr = handle if seg_index < n_seg - 1 else 0.0
        if seg.kind == "outside":
            label = _segment_label(seg_index, is_window=False)
            src_start = max(0.0, seg.start - hl)
            src_end = min(scene_duration_sec, seg.end + hr)
            filters.append(
                f"[0:a]atrim=start={_fmt(src_start)}:end={_fmt(src_end)},"
                "asetpts=PTS-STARTPTS,"
                f"{_resample_chain(sample_rate)}{label}"
            )
            segment_labels.append(label)
        else:
            window_index = seg.window_index
            window_len = seg.end - seg.start
            seg_len = hl + window_len + hr
            line_input = window_index + 1
            bed_label = f"[bed{window_index}]"
            line_label = f"[line{window_index}]"
            win_label = _segment_label(window_index, is_window=True)

            # Loop the donor span to the full segment length (window + handles)
            # with an explicit sample count.
            donor_samples = max(1, math.ceil(donor_len * sample_rate))
            filters.append(
                f"[0:a]atrim=start={_fmt(donor_start)}:end={_fmt(donor_end)},"
                "asetpts=PTS-STARTPTS,"
                f"aloop=loop=-1:size={donor_samples},"
                f"atrim=start=0:end={_fmt(seg_len)},"
                f"{_resample_chain(sample_rate)}{bed_label}"
            )

            # The line starts exactly at the window start: delay it past the
            # left handle, then pad/trim to the full segment length.
            filters.append(
                f"[{line_input}:a]"
                f"{_resample_chain(sample_rate)},"
                f"adelay={int(round(hl * 1000))}:all=1,"
                f"apad=pad_dur={_fmt(seg_len)},"
                f"atrim=start={_fmt(0.0)}:end={_fmt(seg_len)}"
                f"{line_label}"
            )

            # Mix line over the room-tone bed, then limit to avoid clipping.
            filters.append(
                f"{bed_label}{line_label}amix=inputs=2:normalize=0,"
                f"alimiter=limit=0.95{win_label}"
            )
            segment_labels.append(win_label)

    # Crossfade every adjacent segment in time order.
    n = len(segment_labels)
    if n == 1:
        filters.append(f"{segment_labels[0]}anull[aout]")
        output_label = "[aout]"
    else:
        current = segment_labels[0]
        for i in range(1, n):
            next_label = segment_labels[i]
            out_label = "[aout]" if i == n - 1 else f"[xf{i - 1}]"
            filters.append(
                f"{current}{next_label}acrossfade=d={_fmt(crossfade_d)}:c1=tri:c2=tri{out_label}"
            )
            current = out_label
        output_label = current

    # Preserve exact scene duration after crossfade overlaps.
    filters.append(
        f"{output_label}apad=pad_dur={_fmt(scene_duration_sec)},"
        f"atrim=start=0:end={_fmt(scene_duration_sec)}[aout_final]"
    )
    output_label = "[aout_final]"

    line_inputs = [
        getattr(w, "audio_asset_id", f"line_{i}") for i, w in enumerate(sorted_windows)
    ]

    return AudioGraph(
        filter_complex=";".join(filters),
        line_inputs=line_inputs,
        output_label=output_label,
    )


def rebuild_audio(
    master_path: Path,
    line_paths: list[Path],
    windows: list[Any],
    donor_span: tuple[float, float],
    out_wav: Path,
    *,
    sample_rate: int = 32000,
    crossfade_ms: int = 30,
) -> AudioGraph:
    """Run ffmpeg to write the rebuilt WAV soundtrack."""
    from ..editor_mix import probe_duration

    scene_duration_sec = probe_duration(master_path)
    if scene_duration_sec <= 0:
        sorted_windows = sorted(windows, key=lambda w: (float(w.start), float(w.end)))
        scene_duration_sec = max((float(w.end) for w in sorted_windows), default=0.0)

    graph = build_audio_filter(
        windows,
        donor_span,
        scene_duration_sec=scene_duration_sec,
        sample_rate=sample_rate,
        crossfade_ms=crossfade_ms,
    )

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    args: list[str] = ["-i", str(master_path)]
    for line_path in line_paths:
        args.extend(["-i", str(line_path)])
    args.extend(
        [
            "-filter_complex",
            graph.filter_complex,
            "-map",
            graph.output_label,
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            "2",
            str(out_wav),
        ]
    )
    run_ffmpeg(args)
    return graph
