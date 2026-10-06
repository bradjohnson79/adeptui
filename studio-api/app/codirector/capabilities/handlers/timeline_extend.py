"""Capability handler: timeline.extend — Review & Extend through Timeline Suite."""

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
    duration_sec: float | None = None,
    force: bool = False,
    **_: Any,
) -> dict[str, Any]:
    from ....director_timeline_w46.generation.registry import get_registry
    from ....film_timeline.availability import continuation_copy
    from ....film_timeline.orchestrator import FilmTimelineError, continue_shot
    from ....film_timeline.store import require_film

    mode = "none"
    copy = continuation_copy(mode)
    if not scene_id:
        return {
            "status": "failed",
            "error": "SCENE_REQUIRED",
            "child_jobs": [],
            "job_ids": [execution_id],
            "surface_type": "timeline_extend",
            "creatorAck": "Open the scene on Timeline first so it can be reviewed and continued.",
        }
    try:
        film = require_film(db, project_id, scene_id)
        shot = film.shots[-1] if film.shots else None
        if shot is None:
            return {
                "status": "failed",
                "error": "SHOT_NOT_FOUND",
                "child_jobs": [],
                "job_ids": [execution_id],
                "surface_type": "timeline_extend",
                "creatorAck": "Create a shot before continuing it.",
            }
        generator_id = str(shot.state.modelId or film.generatorId or "")
        try:
            mode = str(get_registry().get(generator_id).capabilities.continuationMode or "none")
        except Exception:
            mode = "none"
        copy = continuation_copy(mode)
        if mode == "none":
            return {
                "status": "failed",
                "error": "CONTINUATION_UNSUPPORTED",
                "child_jobs": [],
                "job_ids": [execution_id],
                "surface_type": "timeline_extend",
                "creatorAck": copy["helper"],
            }
        result = continue_shot(
            db,
            project_id,
            scene_id,
            shot.id,
            duration_sec=float(duration_sec or shot.durationSec or 10),
            timed_prompt=prompt or shot.timedPrompt,
        )
    except FilmTimelineError as exc:
        result = {"ok": False, "error": exc.code, "message": exc.message}
    _ = force
    ok = bool(result.get("ok"))
    segment = result.get("segment") if isinstance(result.get("segment"), dict) else {}
    shot_number = int(segment.get("shotNumber") or 0)
    ack = result.get("message")
    if ok and not ack:
        ack = f"Shot {shot_number} is generating." if shot_number else "The next shot is generating."
    elif not ok and not ack:
        ack = "The scene could not be extended."
    if mode == "soft" and copy.get("helper"):
        ack = f"{copy['label']}. {copy['helper']} {ack}"
    elif ok and "ltx" in generator_id.lower():
        ack = f"Continuation start is the previous shot's final frame. {ack}"
    return {
        "status": "completed" if ok else "failed",
        "error": None if ok else (result.get("message") or result.get("error") or "EXTEND_FAILED"),
        "child_jobs": [
            {
                "job_id": str(result.get("executionId") or result.get("segmentId") or execution_id),
                "label": "Review & Extend",
                "status": "completed" if ok else "failed",
                "child_index": 0,
                "metadata": {
                    "segmentId": result.get("segmentId"),
                    "batchBlockId": result.get("batchBlockId"),
                    "h3Mode": result.get("h3Mode"),
                    "shotNumber": shot_number or None,
                },
            }
        ],
        "job_ids": [execution_id],
        "surface_type": "timeline_extend",
        "creatorAck": ack,
        "result": result,
    }
