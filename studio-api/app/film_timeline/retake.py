"""Mark-in / mark-out against one assembled shot.

A retake replaces a whole existing segment. It does not stretch the marks
to a neighboring segment.
"""

from __future__ import annotations

from .contracts import Segment, Shot

_TOLERANCE = 0.05


def assembled_windows(shot: Shot) -> list[tuple[Segment, float, float]]:
    cursor = 0.0
    windows: list[tuple[Segment, float, float]] = []
    for segment in sorted(shot.segments, key=lambda item: item.order):
        if segment.status != "completed" or not segment.assetId:
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
        return {"ok": True, "segment": matches[0]}
    return {
        "ok": False,
        "code": "PARTIAL_RETAKE_UNSUPPORTED",
        "message": "This model can retake a whole segment. Mark that full segment. Neighboring picture stays as it is.",
    }
