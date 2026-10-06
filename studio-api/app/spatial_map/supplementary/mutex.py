"""One supplementary Qwen view at a time. Do not overlap heavy GPU work."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .contracts import SUPPLEMENTARY_PURPOSE, ViewSlot

HEAVY_PURPOSES = frozenset(
    {
        SUPPLEMENTARY_PURPOSE,
        "environment_reference_sheet",
        "atlas_shot",
    }
)


def _active_jobs(db: Session, project_id: str) -> list[Any]:
    from ...db import Job

    rows = (
        db.query(Job)
        .filter(Job.project_id == project_id, Job.status.in_(["queued", "running", "pending"]))
        .all()
    )
    return list(rows)


def assert_can_start(
    db: Session,
    *,
    project_id: str,
    state_in_flight: ViewSlot | None,
    slot: ViewSlot,
) -> None:
    from fastapi import HTTPException

    if state_in_flight:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SUPPLEMENTARY_VIEW_IN_FLIGHT",
                "message": "Wait for the current additional view to finish before starting another.",
                "inFlightSlot": state_in_flight,
            },
        )
    for job in _active_jobs(db, project_id):
        purpose = ""
        try:
            import json

            params = json.loads(job.params_json or "{}")
            purpose = str(params.get("purpose") or "")
        except Exception:
            purpose = ""
        if purpose in HEAVY_PURPOSES or str(getattr(job, "kind", "") or "") in {"moge2", "vggt"}:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "HEAVY_GPU_JOB_ACTIVE",
                    "message": "Another heavy image or geometry job is already running. Wait, then try again.",
                    "jobId": getattr(job, "id", ""),
                },
            )
    _ = slot
