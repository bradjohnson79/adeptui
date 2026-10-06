"""Capability handler: timeline.generate_shot

Explicit generate of an existing Timeline shot uses the shared Timeline
generate service. Scene-building language prepares a Timeline shot instead
of a fake chat handoff.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ...production.errors import GenerationSubmissionError
from ...production.orchestrator import generate_prepared_scene, load_active_production
from ...routing.generation_authority import classify_generation_authority
from .timeline_prepare_scene import handle as prepare_handle


def _generate_result(submitted: dict[str, Any], *, execution_id: str, scene_id: str, shot_id: str) -> dict[str, Any]:
    job_id = str(
        submitted.get("queueJobId")
        or submitted.get("internalJobId")
        or ((submitted.get("job") or {}) if isinstance(submitted.get("job"), dict) else {}).get("id")
        or f"timeline-job-{execution_id}"
    )
    return {
        "job_ids": [job_id],
        "child_jobs": [
            {
                "job_id": job_id,
                "label": "Timeline generation",
                "status": "queued",
                "child_index": 0,
                "metadata": {"owner": "timeline", "sceneId": scene_id, "shotId": shot_id},
            }
        ],
        "status": "queued",
        "surface_type": "timeline_production",
        "plan_data": {
            "sceneProduction": True,
            "sceneId": scene_id,
            "shotId": shot_id,
            "generationJobId": job_id,
            "submitted": True,
        },
    }


def _find_shot_by_index(db: Session, project_id: str, shot_index: int) -> tuple[str, str] | None:
    from ....film_timeline.store import load_film
    from ....scene_service import list_scenes

    for scene in list_scenes(db, project_id):
        loaded = load_film(db, project_id, scene.id)
        if not loaded.get("ok"):
            continue
        shots = list(getattr(loaded.get("film"), "shots", None) or [])
        if 1 <= shot_index <= len(shots):
            return scene.id, str(shots[shot_index - 1].id)
    return None


def _remember_ltx_intent(db: Session, project_id: str, scene_id: str, shot_id: str, message: str) -> str | None:
    """Persist a proven LTX mode, or stop when the request needs three frames."""

    if db is None or not scene_id or not shot_id:
        return None
    from ....film_timeline.orchestrator import FilmTimelineError
    from ....film_timeline.store import require_film, save_film

    try:
        film = require_film(db, project_id, scene_id)
    except FilmTimelineError:
        return None
    shot = next((item for item in film.shots if item.id == shot_id), None)
    if shot is None:
        return None
    model = str(shot.state.modelId or film.generatorId or "")
    text = message or ""
    if re.search(r"\b(?:three|3)[-\s]?frames?\b|\bmiddle frame\b", text, re.I):
        return (
            "LTX 2.5 on Timeline uses Text to Video, a Start Frame, or a Start Frame and an End Frame. "
            "It does not take a third or middle frame. I have not started a shot."
        )
    mode = ""
    if re.search(r"\b(?:finish on this image|end on this image|start \+ end|start and end)\b", text, re.I):
        mode = "start_end"
    elif re.search(r"\b(?:from text|text[-\s]?to[-\s]?video)\b", text, re.I):
        mode = "text"
    elif re.search(
        r"\b(?:animate (?:this|the) image|start frame|start picture|use (?:1|one)[-\s]?frame|(?:1|one)-frame)\b",
        text,
        re.I,
    ):
        mode = "one_frame"
    if not mode:
        return None
    if "ltx-2.5" not in model:
        shot.state.modelId = "ltx-2.5-distilled"
    stored = dict(shot.state.resolvedGeneration or {})
    stored["ltxMode"] = mode
    shot.state.resolvedGeneration = stored
    save_film(db, project_id, scene_id, film)
    return None


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    user_instructions: str = "",
    scene_id: str = "",
    plan_only: bool | None = None,
    plan_data: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    saved = plan_data if isinstance(plan_data, dict) else {}
    if saved.get("sceneProduction") and saved.get("shotId") and plan_only is False:
        return prepare_handle(
            db,
            project_id,
            execution_id,
            prompt=prompt,
            user_instructions=user_instructions,
            scene_id=str(saved.get("sceneId") or scene_id or ""),
            plan_only=False,
            plan_data=saved,
            **kwargs,
        )

    message = user_instructions or prompt
    authority = classify_generation_authority(message)
    shot_index = authority.shot_index if authority else None
    if shot_index is None:
        match = re.search(r"\bshot\s*(\d+)\b", message, re.I)
        if match:
            shot_index = int(match.group(1))

    explicit_generate = bool(
        re.search(r"\b(?:generate|render|run)\s+(?:this\s+|that\s+|the\s+)?shot\b", message, re.I)
    )
    if explicit_generate:
        target = None
        if shot_index and db is not None:
            target = _find_shot_by_index(db, project_id, shot_index)
        if target is None and db is not None:
            active = load_active_production(db, project_id)
            if active.get("sceneId") and active.get("shotId"):
                target = (str(active["sceneId"]), str(active["shotId"]))
        if target is None:
            return {
                "job_ids": [f"timeline-missing-{execution_id}"],
                "child_jobs": [
                    {
                        "job_id": f"timeline-missing-{execution_id}",
                        "label": "Timeline shot missing",
                        "status": "failed",
                        "child_index": 0,
                        "error": (
                            f"Shot {shot_index} is not on Timeline yet."
                            if shot_index
                            else "No prepared Timeline shot is available to generate."
                        ),
                    }
                ],
                "status": "failed",
                "error": "Timeline shot not found.",
                "surface_type": "timeline_production",
                "plan_data": {"sceneProduction": True},
            }
        try:
            from ....film_timeline.dialogue_authority import apply_instruction

            blocked = _remember_ltx_intent(db, project_id, target[0], target[1], message)
            if blocked:
                return {
                    "job_ids": [f"timeline-ltx-{execution_id}"],
                    "child_jobs": [
                        {
                            "job_id": f"timeline-ltx-{execution_id}",
                            "label": "LTX mode",
                            "status": "failed",
                            "child_index": 0,
                            "error": blocked,
                        }
                    ],
                    "status": "failed",
                    "error": blocked,
                    "surface_type": "timeline_production",
                }
            apply_instruction(db, project_id, target[0], target[1], message)
            submitted = generate_prepared_scene(
                db, project_id=project_id, scene_id=target[0], shot_id=target[1]
            )
        except GenerationSubmissionError as exc:
            return {
                "job_ids": [f"timeline-generate-failed-{execution_id}"],
                "child_jobs": [
                    {
                        "job_id": f"timeline-generate-failed-{execution_id}",
                        "label": "Timeline generate failed",
                        "status": "failed",
                        "child_index": 0,
                        "error": exc.message,
                    }
                ],
                "status": "failed",
                "error": exc.message,
                "surface_type": "timeline_production",
            }
        return _generate_result(submitted, execution_id=execution_id, scene_id=target[0], shot_id=target[1])

    return prepare_handle(
        db,
        project_id,
        execution_id,
        prompt=prompt,
        user_instructions=user_instructions,
        scene_id=scene_id,
        plan_only=plan_only,
        plan_data=plan_data,
        **kwargs,
    )
