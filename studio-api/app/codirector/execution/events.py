"""Execution event contracts — SSE events for live execution state.

Spec §17: "Use/reuse: WebSocket or Server-Sent Events for live execution state.
Avoid repeated aggressive polling."

Event types (spec §17):
- execution.started | execution.updated | execution.completed | execution.failed
- job.queued | job.running | job.preview | job.completed | job.failed
- artifact.created
- collection.created | collection.updated

These events are published to the existing status SSE bus
(studio-api/app/codirector/status/router.py:67) and consumed by the frontend
Live Agent Work Surface.

FROZEN CONTRACT — Law #16. Event type names are stable.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from ...db import Job


class ExecutionEventType(str, Enum):
    """SSE event types for the Live Agent Work Surface."""

    # Parent execution lifecycle.
    EXECUTION_STARTED = "execution.started"
    EXECUTION_UPDATED = "execution.updated"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"

    # Per-child job lifecycle (bridges Studio JobQueue → SSE).
    JOB_QUEUED = "job.queued"
    JOB_RUNNING = "job.running"
    JOB_PREVIEW = "job.preview"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"

    # Artifact + collection lifecycle.
    ARTIFACT_CREATED = "artifact.created"
    COLLECTION_CREATED = "collection.created"
    COLLECTION_UPDATED = "collection.updated"


class ExecutionEvent(BaseModel):
    """One SSE event for the Live Agent Work Surface.

    Published to the status event bus. The frontend subscribes via
    `GET /api/status/events` (existing endpoint) and dispatches based on
    `event_type`.
    """

    event_type: ExecutionEventType
    project_id: str
    execution_id: str

    # Child job context (present for job.* events).
    job_id: Optional[str] = None
    child_index: Optional[int] = None
    child_label: str = ""

    # Asset context (present for artifact.created / job.completed).
    asset_id: Optional[str] = None

    # Collection context.
    collection_id: Optional[str] = None

    # Status + progress.
    status: str = ""
    progress: float = 0.0
    stage: str = ""

    # Error (present for job.failed / execution.failed).
    error: Optional[str] = None

    # Surface type hint for the frontend.
    surface_type: str = ""

    # Completed/total counts for parent progress.
    completed: Optional[int] = None
    total: Optional[int] = None

    # Timestamp.
    timestamp: str = ""

    def to_sse_data(self) -> dict[str, Any]:
        """Serialize for the SSE bus (the status router wraps in `data:` lines)."""
        return self.model_dump(mode="json", exclude_none=True)


def make_job_completed_event(
    project_id: str,
    execution_id: str,
    job_id: str,
    *,
    child_index: int = 0,
    child_label: str = "",
    asset_id: Optional[str] = None,
    surface_type: str = "",
    completed: int = 0,
    total: int = 0,
    timestamp: str = "",
) -> ExecutionEvent:
    """Helper to construct a job.completed event."""
    return ExecutionEvent(
        event_type=ExecutionEventType.JOB_COMPLETED,
        project_id=project_id,
        execution_id=execution_id,
        job_id=job_id,
        child_index=child_index,
        child_label=child_label,
        asset_id=asset_id,
        status="completed",
        surface_type=surface_type,
        completed=completed,
        total=total,
        timestamp=timestamp,
    )


def make_execution_completed_event(
    project_id: str,
    execution_id: str,
    *,
    result_asset_ids: Optional[list[str]] = None,
    collection_id: Optional[str] = None,
    surface_type: str = "",
    completed: int = 0,
    total: int = 0,
    timestamp: str = "",
) -> ExecutionEvent:
    """Helper to construct an execution.completed event."""
    return ExecutionEvent(
        event_type=ExecutionEventType.EXECUTION_COMPLETED,
        project_id=project_id,
        execution_id=execution_id,
        status="completed",
        progress=1.0 if total > 0 and completed == total else 0.0,
        surface_type=surface_type,
        collection_id=collection_id,
        completed=completed,
        total=total,
        timestamp=timestamp,
    )


def publish_event(event: ExecutionEvent) -> None:
    """Publish an ``ExecutionEvent`` on the existing Co-Director status SSE bus.

    Reuses the in-process event bus in ``codirector/status/runner.py`` — the
    same one the status router serves at ``GET /api/status/events``. We do
    *not* create a parallel event system (Law #18, spec §17). The import is
    lazy so the execution contracts module stays free of runtime cycles and
    so callers that never publish (e.g. tests) do not require the status bus.

    Failures are swallowed deliberately: event publishing must never take down
    a job-completion path. The bus is in-process and best-effort — the pack
    store remains the source of truth for execution state.
    """
    try:
        from ..status import runner as _status_runner

        payload = {
            "type": event.event_type.value,
            **event.to_sse_data(),
        }
        _status_runner._publish(payload)
    except Exception:
        # Event bus unavailable — do not fail the caller. The pack store
        # remains authoritative; clients can still poll the REST endpoints.
        return


def emit_job_status(
    project_id: str,
    execution_id: str,
    job_id: str,
    *,
    job_status: str,
    child_index: int = 0,
    child_label: str = "",
    asset_id: Optional[str] = None,
    stage: str = "",
    error: Optional[str] = None,
    surface_type: str = "",
    completed: int = 0,
    total: int = 0,
    timestamp: str = "",
) -> None:
    """Bridge a Studio ``Job`` status transition into the SSE bus.

    Called from ``queue_worker._set_status`` (when bridged) and from
    ``advance_execution_pack`` to publish ``job.*`` events. Maps the raw
    ``Job.status`` vocabulary (queued/running/done/failed/cancelled/preview)
    onto ``ExecutionEventType``. No-op if the status doesn't map.
    """
    event_type: Optional[ExecutionEventType] = None
    s = (job_status or "").lower()
    if s == "queued":
        event_type = ExecutionEventType.JOB_QUEUED
    elif s == "running":
        event_type = ExecutionEventType.JOB_RUNNING
    elif s == "preview":
        event_type = ExecutionEventType.JOB_PREVIEW
    elif s == "done":
        event_type = ExecutionEventType.JOB_COMPLETED
    elif s == "failed":
        event_type = ExecutionEventType.JOB_FAILED
    if event_type is None:
        return
    publish_event(
        ExecutionEvent(
            event_type=event_type,
            project_id=project_id,
            execution_id=execution_id,
            job_id=job_id,
            child_index=child_index,
            child_label=child_label,
            asset_id=asset_id,
            status=s,
            stage=stage,
            error=error,
            surface_type=surface_type,
            completed=completed if event_type == ExecutionEventType.JOB_COMPLETED else None,
            total=total if event_type == ExecutionEventType.JOB_COMPLETED else None,
            timestamp=timestamp,
        )
    )


def bridge_job_status_change(
    db: "Session",
    job_id: str,
    job_status: str,
    stage: str = "",
    message: str = "",
) -> None:
    """Bridge a Studio ``JobQueue._set_status`` transition to the SSE bus.

    Called from ``queue_worker.JobQueue._set_status`` after the ``Job`` row is
    committed. Resolves the owning execution pack + child view by reading
    ``executionId`` from ``Job.params_json`` (stamped by capability handlers
    when they enqueue child jobs), then emits the matching ``job.*`` event.

    No-op for non-Co-Director jobs (no ``executionId`` in params). All
    failures are swallowed — the bus is best-effort and must never take down
    the job-completion path. The pack store remains the source of truth.
    """
    try:
        from ...db import ProjectTraitRow  # local import avoids cycle
        import json as _json

        job = db.get(Job, job_id) if hasattr(db, "get") else None
        if job is None:
            return
        params: dict = {}
        try:
            params = _json.loads(job.params_json) if job.params_json else {}
        except Exception:
            params = {}
        execution_id = params.get("executionId") or params.get("execution_id")
        if not execution_id:
            return
        project_id = job.project_id
        # Find the pack + child view.
        row = (
            db.query(ProjectTraitRow)
            .filter(
                ProjectTraitRow.project_id == project_id,
                ProjectTraitRow.category == "execution_pack",
                ProjectTraitRow.key == execution_id,
            )
            .order_by(ProjectTraitRow.id.desc())
            .first()
        )
        if not row:
            return
        try:
            plan = ExecutionPlan.model_validate_json(row.value)
        except Exception:
            return
        child_index = 0
        child_label = ""
        child_asset_id: Optional[str] = None
        for idx, c in enumerate(plan.child_jobs):
            if c.job_id == job_id:
                child_index = idx
                child_label = c.label
                child_asset_id = c.asset_id
                break
        asset_id = (
            params.get("output_asset_id")
            or params.get("outputAssetId")
            or child_asset_id
        )
        emit_job_status(
            project_id=project_id,
            execution_id=execution_id,
            job_id=job_id,
            job_status=job_status,
            child_index=child_index,
            child_label=child_label,
            asset_id=asset_id if job_status == "done" else None,
            stage=stage or job.stage or "",
            error=(message or None) if job_status == "failed" else None,
            surface_type=plan.surface_type,
            completed=plan.completed_children,
            total=plan.total_children,
            timestamp="",
        )
    except Exception:
        # Best-effort bridge — never fail the job-completion path.
        return


