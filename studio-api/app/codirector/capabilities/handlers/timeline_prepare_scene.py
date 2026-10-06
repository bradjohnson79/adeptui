"""Capability handler: timeline.prepare_scene

Prepares a real Timeline BatchBlock. Does not start generation.
Approve / Generate in Timeline calls the shared Timeline generate service.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...production.errors import GenerationSubmissionError
from ...production.orchestrator import generate_prepared_scene, prepare_production_request


def _events_payload(events) -> list[dict[str, Any]]:
    return [item.model_dump() for item in events]


def _ready_result(prepared, *, execution_id: str) -> dict[str, Any]:
    spec = prepared.spec
    plan_data = {
        "sceneProduction": True,
        "preparationReady": True,
        "sceneId": prepared.scene_id,
        "shotId": prepared.shot_id,
        "sceneIndex": prepared.scene_index,
        "shotLabel": prepared.shot_label,
        "generatorId": spec.generator_id,
        "durationSeconds": spec.duration_seconds,
        "aspectRatio": spec.aspect_ratio,
        "quality": spec.quality,
        "megapixels": spec.megapixels,
        "batchCount": spec.batch_count,
        "compiledPrompt": prepared.compiled_prompt,
        "events": _events_payload(prepared.events),
        "references": [item.model_dump() for item in spec.references],
        "scaleRelationships": [item.model_dump() for item in spec.scale_relationships],
        "directorIntent": spec.director_intent.model_dump() if spec.director_intent else None,
    }
    return {
        "job_ids": [f"timeline-ready-{execution_id}"],
        "child_jobs": [
            {
                "job_id": f"timeline-ready-{execution_id}",
                "label": "Timeline shot ready",
                "status": "preview",
                "child_index": 0,
                "metadata": {
                    "owner": "timeline",
                    "preparationReady": True,
                    "sceneId": prepared.scene_id,
                    "shotId": prepared.shot_id,
                },
            }
        ],
        "status": "preview",
        "preparationReady": True,
        "message": "Timeline shot ready.",
        "surface_type": "timeline_production",
        "plan_data": plan_data,
    }


def _failed_result(prepared, *, execution_id: str) -> dict[str, Any]:
    return {
        "job_ids": [f"timeline-prepare-failed-{execution_id}"],
        "child_jobs": [
            {
                "job_id": f"timeline-prepare-failed-{execution_id}",
                "label": "Timeline preparation failed",
                "status": "failed",
                "child_index": 0,
                "error": prepared.error,
                "metadata": {"owner": "timeline"},
            }
        ],
        "status": "failed",
        "error": prepared.error,
        "message": prepared.error,
        "surface_type": "timeline_production",
        "plan_data": {
            "sceneProduction": True,
            "events": _events_payload(prepared.events),
            "error": prepared.error,
            "errorCode": prepared.error_code,
        },
    }


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
    **_: Any,
) -> dict[str, Any]:
    saved = plan_data if isinstance(plan_data, dict) else {}
    if saved.get("sceneProduction") and saved.get("shotId") and plan_only is False:
        try:
            from ....film_timeline.dialogue_authority import apply_instruction

            apply_instruction(
                db,
                project_id,
                str(saved.get("sceneId") or scene_id or ""),
                str(saved.get("shotId") or ""),
                user_instructions or prompt,
            )
            submitted = generate_prepared_scene(
                db,
                project_id=project_id,
                scene_id=str(saved.get("sceneId") or ""),
                shot_id=str(saved.get("shotId") or ""),
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
                "plan_data": {**saved, "error": exc.message},
            }
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
                    "metadata": {
                        "owner": "timeline",
                        "sceneId": saved.get("sceneId"),
                        "shotId": saved.get("shotId"),
                        "queueJobId": submitted.get("queueJobId"),
                    },
                }
            ],
            "status": "queued",
            "surface_type": "timeline_production",
            "plan_data": {**saved, "generationJobId": job_id, "submitted": True},
        }

    message = user_instructions or prompt
    prepared = prepare_production_request(
        db,
        project_id=project_id,
        message=message,
        scene_id=scene_id,
    )
    if not prepared.ok:
        return _failed_result(prepared, execution_id=execution_id)
    from ....film_timeline.dialogue_authority import apply_instruction

    apply_instruction(db, project_id, prepared.scene_id, prepared.shot_id, message)
    return _ready_result(prepared, execution_id=execution_id)
