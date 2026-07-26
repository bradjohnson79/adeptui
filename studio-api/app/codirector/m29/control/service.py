"""M2.9 Co-Director production control — decompose multi-step requests into jobs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..db import ensure_m29_tables
from ..fixtures import fixture_control_plan
from ..store import enqueue_executive_job


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


_JOB_TYPE_MAP = {
    "image_generate": JobType.IMAGE_GENERATE,
    "frame_generate": JobType.FRAME_GENERATE,
    "frame_sequence": JobType.FRAME_SEQUENCE,
    "video_generate": JobType.VIDEO_GENERATE,
    "lipsync_generate": JobType.LIPSYNC_GENERATE,
    "mouth_track_generate": JobType.MOUTH_TRACK_GENERATE,
    "audio_generate": JobType.AUDIO_GENERATE,
    "audio_process": JobType.AUDIO_PROCESS,
    "timeline_render": JobType.TIMELINE_RENDER,
    "scene_render": JobType.SCENE_RENDER,
    "edit_apply": JobType.EDIT_APPLY,
}


class ControlService:
    @staticmethod
    def decompose(
        db: Session,
        *,
        project_id: str,
        request_text: str,
        enqueue: bool = False,
        owner: str = "user",
        scene_id: str | None = None,
    ) -> dict[str, Any]:
        ensure_m29_tables()
        plan = fixture_control_plan(request_text)
        # Mark plan provenance: deterministic planner (not LLM discovery).
        plan["planner"] = "m29_deterministic"
        plan["fixture"] = fixture_mode_enabled()
        plan_id = plan.get("planId") or uuid.uuid4().hex
        plan["planId"] = plan_id
        db.execute(
            text(
                "INSERT INTO m29_control_plans "
                "(id, project_id, status, request_text, plan_json, created_at) "
                "VALUES (:id, :pid, :status, :rt, :pj, :c)"
            ),
            {
                "id": plan_id,
                "pid": project_id,
                "status": "proposed",
                "rt": request_text,
                "pj": json.dumps(plan),
                "c": _now(),
            },
        )
        db.commit()
        jobs: list[dict[str, Any]] = []
        if enqueue:
            for step in plan["steps"]:
                jt = _JOB_TYPE_MAP.get(step["jobType"])
                if jt is None:
                    continue
                payload = dict(step.get("payload") or {})
                payload["m29"] = True
                if fixture_mode_enabled():
                    payload["fixtureComplete"] = True
                if jt == JobType.EDIT_APPLY:
                    payload["approved"] = False  # never silent apply
                job = enqueue_executive_job(
                    db,
                    project_id=project_id,
                    job_type=jt,
                    payload=payload,
                    scene_id=scene_id,
                    owner=owner,
                )
                jobs.append(
                    {
                        "jobId": job.id,
                        "jobType": step["jobType"],
                        "capability": step["capability"],
                    }
                )
            db.execute(
                text("UPDATE m29_control_plans SET status = :s WHERE id = :id"),
                {"s": "enqueued", "id": plan_id},
            )
            db.commit()
        return {
            "planId": plan_id,
            "projectId": project_id,
            "requestText": request_text,
            "steps": plan["steps"],
            "jobs": jobs,
            "requiresApproval": True,
            "fixture": fixture_mode_enabled(),
            "status": "enqueued" if jobs else "proposed",
        }

    @staticmethod
    def get_plan(db: Session, plan_id: str) -> dict[str, Any] | None:
        ensure_m29_tables()
        row = db.execute(
            text(
                "SELECT id, project_id, status, request_text, plan_json, created_at "
                "FROM m29_control_plans WHERE id = :id"
            ),
            {"id": plan_id},
        ).mappings().first()
        if not row:
            return None
        plan = json.loads(row["plan_json"] or "{}")
        return {
            "planId": row["id"],
            "projectId": row["project_id"],
            "status": row["status"],
            "requestText": row["request_text"],
            "steps": plan.get("steps") or [],
            "createdAt": row["created_at"],
            "requiresApproval": True,
        }

    @staticmethod
    def resume(db: Session, plan_id: str, *, owner: str = "user") -> dict[str, Any]:
        """Resume a proposed/enqueued plan by enqueueing remaining non-gated steps."""
        plan = ControlService.get_plan(db, plan_id)
        if not plan:
            raise KeyError(plan_id)
        return ControlService.decompose(
            db,
            project_id=plan["projectId"],
            request_text=plan["requestText"],
            enqueue=True,
            owner=owner,
        )
