"""Execution cancellation — cancel remaining child jobs via cancel_and_halt.

Spec §47: "Where generation backend supports cancellation: provide Cancel.
Completed assets remain unless user requests deletion."
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..execution.contracts import ChildJobStatus, ExecutionPlan, ExecutionStatus
from ..execution.events import ExecutionEvent, ExecutionEventType
from .pack_store import load_pack, save_pack

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _publish_event(event: ExecutionEvent) -> None:
    try:
        from ..status.runner import publish_event as _publish

        _publish(event.to_sse_data())
    except Exception as exc:
        logger.debug("Failed to publish execution event: %s", exc)


def cancel_execution(db: Session, project_id: str, execution_id: str) -> ExecutionPlan | None:
    """Cancel remaining child jobs. Completed assets remain (spec §47)."""
    plan = load_pack(db, project_id, execution_id)
    if not plan:
        return None

    if plan.is_terminal:
        return plan

    any_cancelled = False

    for child in plan.child_jobs:
        if child.status in (ChildJobStatus.COMPLETED, ChildJobStatus.FAILED, ChildJobStatus.CANCELLED):
            continue

        try:
            _cancel_job(child.job_id)
            child.status = ChildJobStatus.CANCELLED
            child.stage = "cancelled"
            any_cancelled = True
        except Exception as exc:
            logger.warning("Failed to cancel job %s: %s", child.job_id, exc)
            # Mark as cancelled anyway since we can't reach the backend.
            child.status = ChildJobStatus.CANCELLED
            any_cancelled = True

    if any_cancelled:
        plan.status = ExecutionStatus.CANCELLED
        plan.recompute_progress()
        save_pack(db, project_id, plan)

        _publish_event(ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_FAILED,
            project_id=project_id,
            execution_id=execution_id,
            status="cancelled",
            completed=plan.completed_children,
            total=plan.total_children,
            surface_type=plan.surface_type,
            timestamp=_now(),
        ))

    return plan


def _cancel_job(job_id: str) -> None:
    """Cancel a job via JobQueue.cancel_and_halt (Comfy halt), not a DB-only mark."""
    import asyncio

    from ...queue_worker import job_queue

    if job_queue is None or not hasattr(job_queue, "cancel_and_halt"):
        _mark_job_cancelled_direct(job_id)
        return
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            loop.create_task(job_queue.cancel_and_halt(job_id))
        else:
            asyncio.run(job_queue.cancel_and_halt(job_id))
    except Exception as exc:
        logger.warning("cancel_and_halt failed for %s: %s", job_id, exc)
        _mark_job_cancelled_direct(job_id)


def _mark_job_cancelled_direct(job_id: str) -> None:
    """Direct DB cancellation fallback."""
    try:
        from ...db import Job
        from ...db_utils import get_db_session

        db = next(get_db_session())
        job = db.get(Job, job_id)
        if job and job.status not in ("done", "failed", "cancelled"):
            job.status = "cancelled"
            db.commit()
    except Exception as exc:
        logger.error("Direct job cancellation failed for %s: %s", job_id, exc)
