"""Capability handler: timeline.reorder — the same composition move as the track menu."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

_BEFORE = re.compile(r"\bmove\b.+\bshot\s*(\d+)\b.+\bbefore\b.+\bshot\s*(\d+)\b", re.I)
_AFTER_SHOT = re.compile(r"\bmove\b.+\bshot\s*(\d+)\b.+\bafter\b.+\bshot\s*(\d+)\b", re.I)
_AFTER_LIBRARY = re.compile(r"\bput\b.+\b(?:imported|library)\b.+\bafter\b.+\bshot\s*(\d+)\b", re.I)
_DIRECTION = re.compile(r"\bmove\b.+\bshot\s*(\d+)\b.+\b(earlier|later)\b", re.I)


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    scene_id: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ....film_timeline.orchestrator import FilmTimelineError, composition_units, reorder_composition
    from ....film_timeline.store import require_film

    if not scene_id:
        return _done(False, execution_id, "Open the scene on Timeline first.")
    film = require_film(db, project_id, scene_id)
    shot = film.shots[-1] if film.shots else None
    if shot is None:
        return _done(False, execution_id, "There is no clip to move.")
    text = prompt or ""
    try:
        if match := _BEFORE.search(text):
            _place(db, project_id, scene_id, shot.id, _blocks(shot, int(match.group(1))), before=_first(shot, int(match.group(2))))
        elif match := _AFTER_SHOT.search(text):
            _place(db, project_id, scene_id, shot.id, _blocks(shot, int(match.group(1))), after=_first(shot, int(match.group(2))))
        elif match := _AFTER_LIBRARY.search(text):
            library = _library_block(shot)
            _place(db, project_id, scene_id, shot.id, library, after=_first(shot, int(match.group(1))))
        elif match := _DIRECTION.search(text):
            block = _blocks(shot, int(match.group(1)))
            anchor = block[-1][0].id if match.group(2).lower() == "later" else block[0][0].id
            reorder_composition(db, project_id, scene_id, shot.id, segment_id=anchor, direction=match.group(2).lower())
        else:
            return _done(False, execution_id, "Say which shot should move, and whether it goes earlier, later, before, or after another shot.")
    except FilmTimelineError as exc:
        return _done(False, execution_id, exc.message)
    units = composition_units(require_film(db, project_id, scene_id).shots[-1])
    order = ", ".join(_label(unit[0]) for unit in units)
    return _done(True, execution_id, f"The track is now {order}.")


def _label(segment: Any) -> str:
    number = int(getattr(segment, "shotNumber", 0) or 0)
    if str(getattr(segment, "origin", "") or "") == "library" and number:
        return f"Shot {number}"
    return f"Shot {number}" if number else "Clip"


def _blocks(shot: Any, number: int) -> list[list[Any]]:
    from ....film_timeline.orchestrator import composition_units

    matched = [unit for unit in composition_units(shot) if any(int(item.shotNumber or 0) == number for item in unit)]
    if not matched:
        from ....film_timeline.orchestrator import FilmTimelineError

        raise FilmTimelineError("SEGMENT_NOT_FOUND", f"Shot {number} is not on the track.")
    return matched


def _library_block(shot: Any) -> list[list[Any]]:
    from ....film_timeline.orchestrator import FilmTimelineError, composition_units

    matched = [unit for unit in composition_units(shot) if any(str(item.origin or "") == "library" for item in unit)]
    if len(matched) != 1:
        raise FilmTimelineError("SEGMENT_NOT_FOUND", "Say which imported clip should move.")
    return matched


def _first(shot: Any, number: int) -> str:
    return _blocks(shot, number)[0][0].id


def _place(db: Session, project_id: str, scene_id: str, shot_id: str, blocks: list[list[Any]], *, before: str | None = None, after: str | None = None) -> None:
    from ....film_timeline.orchestrator import reorder_composition

    if before:
        target = before
        for unit in reversed(blocks):
            reorder_composition(db, project_id, scene_id, shot_id, segment_id=unit[0].id, before_segment_id=target)
            target = unit[0].id
        return
    target = after
    for unit in blocks:
        reorder_composition(db, project_id, scene_id, shot_id, segment_id=unit[0].id, after_segment_id=target)
        target = unit[-1].id


def _done(ok: bool, execution_id: str, message: str) -> dict[str, Any]:
    return {
        "status": "completed" if ok else "failed",
        "error": None if ok else message,
        "child_jobs": [],
        "job_ids": [execution_id],
        "surface_type": "timeline_reorder",
        "creatorAck": message,
    }
