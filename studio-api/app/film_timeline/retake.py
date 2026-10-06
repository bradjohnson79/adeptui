"""Mark-in / mark-out against one assembled shot.

A range inside one segment becomes a head, a replacement, and a tail.
A range that crosses two segments is refused. The picture stays as it is.
"""

from __future__ import annotations

import math

from .contracts import Segment, Shot

_TOLERANCE = 0.05
_MIN_GENERATE_SEC = 3


def _clock(value: float) -> str:
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 1e-6:
        return f"{int(round(rounded))}s"
    return f"{rounded:.2f}s"


def _on_composition(segment: Segment) -> bool:
    if segment.generationMetadata.get("compositionHold"):
        return False
    return segment.status == "completed" and bool(segment.assetId)


def assembled_windows(shot: Shot) -> list[tuple[Segment, float, float]]:
    cursor = 0.0
    windows: list[tuple[Segment, float, float]] = []
    for segment in sorted(shot.segments, key=lambda item: item.order):
        if not _on_composition(segment):
            continue
        start = cursor
        end = cursor + float(segment.durationSec or 0)
        windows.append((segment, start, end))
        cursor = end
    return windows


def resolve_retake_segment(shot: Shot, mark_in: float | None, mark_out: float | None) -> dict:
    if mark_in is None or mark_out is None:
        return {"ok": False, "code": "RETAKE_RANGE", "message": "Mark In and Mark Out first."}
    start = float(mark_in)
    end = float(mark_out)
    if end < start:
        return {"ok": False, "code": "RETAKE_RANGE", "message": "Mark Out is before Mark In."}
    if end - start <= 0:
        return {"ok": False, "code": "RETAKE_RANGE", "message": "Mark a region with some length."}
    windows = assembled_windows(shot)
    total = windows[-1][2] if windows else 0.0
    if start < -_TOLERANCE or end > total + _TOLERANCE:
        return {"ok": False, "code": "RETAKE_RANGE", "message": "That range is outside this shot."}
    matches = [
        segment
        for segment, window_start, window_end in windows
        if abs(window_start - start) <= _TOLERANCE and abs(window_end - end) <= _TOLERANCE
    ]
    if len(matches) == 1:
        return {"ok": True, "mode": "whole", "segment": matches[0]}
    containing = [
        (segment, window_start, window_end)
        for segment, window_start, window_end in windows
        if start >= window_start - _TOLERANCE and end <= window_end + _TOLERANCE
    ]
    if len(containing) == 1:
        segment, window_start, window_end = containing[0]
        file_in = float(segment.trimInSec or 0) + max(0.0, start - window_start)
        file_out = float(segment.trimInSec or 0) + max(0.0, end - window_start)
        return {
            "ok": True,
            "mode": "partial",
            "segment": segment,
            "fileIn": file_in,
            "fileOut": file_out,
            "marked": end - start,
            "windowStart": window_start,
            "windowEnd": window_end,
        }
    crossed = [
        (window_start, window_end)
        for _segment, window_start, window_end in windows
        if window_end > start + _TOLERANCE and window_start < end - _TOLERANCE
    ]
    named = " and ".join(f"{_clock(window_start)}–{_clock(window_end)}" for window_start, window_end in crossed[:2])
    if len(crossed) >= 2:
        message = (
            f"{_clock(start)}–{_clock(end)} crosses more than one batch ({named}). "
            "Mark a range inside one batch. Picture in the other batches stays as it is."
        )
    else:
        message = "Mark a range inside one batch. Neighboring picture stays as it is."
    return {"ok": False, "code": "PARTIAL_RETAKE_UNSUPPORTED", "message": message}


def generate_seconds(marked: float) -> int:
    """H3's shortest shot is 3 seconds. The composition still uses the marked length."""

    return max(_MIN_GENERATE_SEC, int(math.ceil(float(marked) - 1e-6)))


def plan_replacement_pieces(source: Segment, generated_asset_id: str, *, file_in: float, file_out: float, marked: float, generated_sec: float, prompt: str) -> list[Segment]:
    """Head and tail keep the source file. The middle is the new picture, trimmed to the mark."""

    pieces: list[Segment] = []
    origin_in = float(source.trimInSec or 0)
    if file_in - origin_in > _TOLERANCE:
        pieces.append(
            Segment(
                assetId=source.assetId,
                durationSec=file_in - origin_in,
                requestedDurationSec=file_in - origin_in,
                status="completed",
                timedPrompt=source.timedPrompt,
                trimInSec=origin_in,
                trimOutSec=file_in,
                compositionRole="source",
                sourceSegmentId=source.id,
                origin=source.origin,
                generatorId=source.generatorId,
                shotNumber=int(source.shotNumber or 0),
            )
        )
    snap = float(generated_sec) - float(marked) > _TOLERANCE
    pieces.append(
        Segment(
            assetId=generated_asset_id,
            durationSec=float(marked),
            requestedDurationSec=float(generated_sec),
            status="completed",
            timedPrompt=prompt or source.timedPrompt,
            trimInSec=0.0,
            trimOutSec=float(marked),
            compositionRole="retake",
            sourceSegmentId=source.id,
            origin="generated",
            generatorId=source.generatorId,
            shotNumber=int(source.shotNumber or 0),
            generationMetadata={"durationSnap": snap, "generatedDurationSec": float(generated_sec)},
        )
    )
    file_end = float(source.trimOutSec) if source.trimOutSec is not None else origin_in + float(source.durationSec or 0)
    if file_end - file_out > _TOLERANCE:
        pieces.append(
            Segment(
                assetId=source.assetId,
                durationSec=file_end - file_out,
                requestedDurationSec=file_end - file_out,
                status="completed",
                timedPrompt=source.timedPrompt,
                trimInSec=file_out,
                trimOutSec=file_end,
                compositionRole="source",
                sourceSegmentId=source.id,
                origin=source.origin,
                generatorId=source.generatorId,
                shotNumber=int(source.shotNumber or 0),
            )
        )
    return pieces
