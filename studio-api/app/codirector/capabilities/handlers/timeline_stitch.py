"""Capability handler: timeline.stitch — assemble the current track with the Timeline stitch."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    scene_id: str = "",
    **_: Any,
) -> dict[str, Any]:
    from ....film_timeline.stitch import stitch_shot
    from ....film_timeline.store import require_film

    _ = prompt
    if not scene_id:
        return _done(False, execution_id, "Open the scene on Timeline first.")
    film = require_film(db, project_id, scene_id)
    shot = film.shots[-1] if film.shots else None
    if shot is None:
        return _done(False, execution_id, "Create a shot before stitching the scene.")
    result = stitch_shot(db, project_id, scene_id, shot.id)
    ok = bool(result.get("ok")) and result.get("stitchStatus") != "failed"
    if result.get("stitchStatus") == "not_needed":
        return _done(False, execution_id, "Add at least two clips before stitching.")
    message = "Scene stitched." if ok else str(result.get("message") or "Stitch failed.")
    return _done(ok, execution_id, message, result)


def _done(ok: bool, execution_id: str, message: str, result: dict | None = None) -> dict[str, Any]:
    return {
        "status": "completed" if ok else "failed",
        "error": None if ok else message,
        "child_jobs": [],
        "job_ids": [execution_id],
        "surface_type": "timeline_stitch",
        "creatorAck": message,
        "result": result or {},
    }
