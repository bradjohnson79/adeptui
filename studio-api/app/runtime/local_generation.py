"""Active Local (GPU / Comfy) generation — one at a time.

Hosted API jobs (Kie / fal / cloudPaid) are excluded. Creators see a chrome
attention bar until the current Local job finishes or is cancelled.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..db import Job

LOCAL_BUSY_STATUSES = frozenset({"queued", "running", "cancelling", "cancel_requested"})
SKIP_KINDS = frozenset({"export"})
AWAITING_DISPATCH = "awaiting_dispatch"


def _params(job: Job) -> dict[str, Any]:
    try:
        data = json.loads(job.params_json or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def job_is_hosted_api(job: Job) -> bool:
    from ..queue_worker import JobQueue

    return JobQueue._job_skips_comfy_bind(job)


def creator_feature_label(params: dict[str, Any]) -> str:
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    if params.get("miniTakeId") or ctx.get("miniTakeId"):
        return "Scene Creator Mini"
    purpose = str(params.get("purpose") or ctx.get("objective") or "").lower()
    tag = str(params.get("tag") or "")
    if purpose == "character_sheet" or "visual-sheet" in tag or tag.startswith("korri_"):
        return "Character look"
    if "environment_reference" in purpose or "ers" in tag.lower():
        return "Environment Reference Sheet"
    if purpose in {"atlas_shot", "environment_supplementary_view"}:
        return "Environment picture"
    return "local generation"


def _rank(job: Job) -> tuple[int, datetime]:
    status = str(job.status or "")
    if status == "running":
        order = 0
    elif status in {"cancelling", "cancel_requested"}:
        order = 1
    else:
        order = 2
    return order, job.created_at or datetime.utcnow()


def active_local_generation(db: Session) -> dict[str, Any]:
    rows = (
        db.query(Job)
        .filter(Job.status.in_(tuple(LOCAL_BUSY_STATUSES)))
        .all()
    )
    candidates: list[Job] = []
    for job in rows:
        if str(job.kind or "") in SKIP_KINDS:
            continue
        if str(job.stage or "") == AWAITING_DISPATCH:
            continue
        if job_is_hosted_api(job):
            continue
        candidates.append(job)
    if not candidates:
        return {
            "active": False,
            "jobId": None,
            "projectId": None,
            "feature": None,
            "cancelable": False,
        }
    job = sorted(candidates, key=_rank)[0]
    params = _params(job)
    return {
        "active": True,
        "jobId": job.id,
        "projectId": job.project_id,
        "feature": creator_feature_label(params),
        "cancelable": str(job.status or "") in {"queued", "running"},
    }
