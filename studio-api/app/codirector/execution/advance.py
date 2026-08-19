"""Advance execution pack — poll real job state and update the pack.

Mirrors `advance_visual_sheet_pack` (character_identity/visual_sheet.py:407) but
for generic execution packs. The client calls `POST /executions/{id}/advance`
which calls this function.

Spec §20: "Every visible Generating/Processing/Saving/Completed/Failed must
correspond to actual backend/task state." This function reads real `Job` rows.

Spec §16: "One failure must not destroy completed siblings." The
`recompute_progress()` in the contract handles this.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..execution.contracts import ChildJobStatus, ExecutionPlan, ExecutionStatus
from ..execution.events import (
    ExecutionEvent,
    ExecutionEventType,
    make_execution_completed_event,
    make_job_completed_event,
)
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


def _get_job_status(db: Session, job_id: str) -> dict[str, Any] | None:
    """Read the real Job row status from the database."""
    try:
        from ...db import Job

        job = db.get(Job, job_id)
        if not job:
            return None
        return {
            "status": job.status,
            "stage": getattr(job, "stage", "") or "",
            "progress": float(getattr(job, "progress", 0.0) or 0.0),
            "message": getattr(job, "message", "") or "",
            "preview_json": getattr(job, "preview_json", "") or "",
            "error": getattr(job, "error_message", None) or getattr(job, "error", None),
            "asset_id": _extract_asset_id(job),
        }
    except Exception as exc:
        logger.warning("Failed to read job %s: %s", job_id, exc)
        return None


def _extract_asset_id(job: Any) -> str | None:
    """Extract the output asset_id from a completed job."""
    try:
        import json
        params = json.loads(job.params_json) if job.params_json else {}
        return params.get("output_asset_id") or params.get("outputAssetId")
    except Exception:
        return None


def _persist_asset(db: Session, project_id: str, asset_id: str, metadata: dict | None = None) -> None:
    """Ensure the asset is persisted to the Library (spec §41)."""
    try:
        from .artifact_persist import ensure_asset_persisted

        ensure_asset_persisted(db, project_id, asset_id, metadata=metadata or {})
    except Exception as exc:
        logger.debug("Asset persist skipped: %s", exc)


def _build_collection(
    db: Session,
    project_id: str,
    plan: ExecutionPlan,
) -> str | None:
    """Build a Library collection for completed assets (spec §38)."""
    try:
        from .collection_builder import create_storyboard_collection

        completed_assets = [
            (i, cj.asset_id)
            for i, cj in enumerate(plan.child_jobs)
            if cj.status == ChildJobStatus.COMPLETED and cj.asset_id
        ]
        if not completed_assets:
            return None

        ordered_ids = [aid for _, aid in completed_assets]
        title = f"Storyboard — {plan.execution_id[:8]}"
        if plan.scene_id:
            title += f" — {plan.scene_id}"

        return create_storyboard_collection(
            project_id,
            title=title,
            ordered_asset_ids=ordered_ids,
            metadata={"execution_id": plan.execution_id, "capability": plan.capability},
        )
    except Exception as exc:
        logger.debug("Collection build skipped: %s", exc)
        return None


ZERO_JOB_ERROR_MESSAGE = "Scene generation could not start. No valid shots were queued."


def heal_zero_job_plan(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    reason: str = "advance",
) -> ExecutionPlan | None:
    """Terminally fail a non-terminal plan that has zero child jobs.

    Shared by the advance endpoint, active-latest hydration, and Cancel
    callers so the zero-job phantom state is healed identically everywhere.
    """
    plan = load_pack(db, project_id, execution_id)
    if not plan or plan.is_terminal or plan.child_jobs:
        return plan
    plan.status = ExecutionStatus.FAILED
    plan.error = ZERO_JOB_ERROR_MESSAGE
    plan.progress = 0.0
    save_pack(db, project_id, plan)
    _publish_event(ExecutionEvent(
        event_type=ExecutionEventType.EXECUTION_FAILED,
        project_id=project_id,
        execution_id=execution_id,
        status="failed",
        error=plan.error,
        surface_type=plan.surface_type,
        total=0,
        timestamp=_now(),
    ))
    return plan


def advance_execution_pack(db: Session, project_id: str, execution_id: str) -> ExecutionPlan | None:
    """Poll real job state and update the execution pack."""
    plan = load_pack(db, project_id, execution_id)
    if not plan:
        return None

    if plan.is_terminal:
        return plan

    # ZERO-JOBS LAW: a non-terminal plan with no child jobs is a stuck
    # phantom generation (0/0 surface). There is no async job
    # materialization contract, so zero jobs means the generation never
    # started — transition to a terminal failure immediately. This also
    # self-heals any packs stranded before this fix.
    if not plan.child_jobs:
        return heal_zero_job_plan(db, project_id, execution_id, reason="advance")

    any_changed = False

    for child in plan.child_jobs:
        if child.status in (ChildJobStatus.COMPLETED, ChildJobStatus.FAILED, ChildJobStatus.CANCELLED):
            continue

        job_state = _get_job_status(db, child.job_id)
        if job_state is None:
            # Job row not found — mark as failed (honest reporting, spec §46).
            child.status = ChildJobStatus.FAILED
            child.error = "JOB_NOT_FOUND"
            any_changed = True
            _publish_event(ExecutionEvent(
                event_type=ExecutionEventType.JOB_FAILED,
                project_id=project_id,
                execution_id=execution_id,
                job_id=child.job_id,
                child_index=child.child_index,
                child_label=child.label,
                error="JOB_NOT_FOUND",
                surface_type=plan.surface_type,
                timestamp=_now(),
            ))
            continue

        raw_status = job_state.get("status", "").lower()

        # Map Studio Job status → ChildJobStatus.
        if raw_status in ("done", "completed", "succeeded"):
            child.status = ChildJobStatus.COMPLETED
            child.asset_id = job_state.get("asset_id")
            child.stage = "completed"
            any_changed = True

            # Persist the asset to Library (spec §41).
            if child.asset_id:
                _persist_asset(db, project_id, child.asset_id, metadata={
                    "execution_id": execution_id,
                    "capability": plan.capability,
                    "frame_index": child.child_index,
                })
                if child.asset_id not in plan.result_asset_ids:
                    plan.result_asset_ids.append(child.asset_id)

            _publish_event(make_job_completed_event(
                project_id=project_id,
                execution_id=execution_id,
                job_id=child.job_id,
                child_index=child.child_index,
                child_label=child.label,
                asset_id=child.asset_id,
                surface_type=plan.surface_type,
                completed=plan.completed_children + 1,
                total=plan.total_children,
                timestamp=_now(),
            ))

        elif raw_status in ("failed", "error"):
            child.status = ChildJobStatus.FAILED
            child.error = job_state.get("error") or "GENERATION_FAILED"
            child.stage = "failed"
            any_changed = True
            _publish_event(ExecutionEvent(
                event_type=ExecutionEventType.JOB_FAILED,
                project_id=project_id,
                execution_id=execution_id,
                job_id=child.job_id,
                child_index=child.child_index,
                child_label=child.label,
                error=child.error,
                surface_type=plan.surface_type,
                timestamp=_now(),
            ))

        elif raw_status in ("running", "processing", "generating"):
            child.status = ChildJobStatus.RUNNING
            child.stage = job_state.get("stage", "running")
            child.progress = job_state.get("progress", 0.0)
            child.message = job_state.get("message", "") or ""
            if job_state.get("preview_json"):
                child.metadata = {**dict(child.metadata or {}), "preview_json": job_state.get("preview_json")}
            any_changed = True
            _publish_event(ExecutionEvent(
                event_type=ExecutionEventType.JOB_RUNNING,
                project_id=project_id,
                execution_id=execution_id,
                job_id=child.job_id,
                child_index=child.child_index,
                child_label=child.label,
                status="running",
                stage=child.stage,
                progress=child.progress,
                surface_type=plan.surface_type,
                timestamp=_now(),
            ))

        elif raw_status in ("queued", "pending", "waiting"):
            child.status = ChildJobStatus.QUEUED
            child.stage = "queued"
            any_changed = True

        elif raw_status in ("preview", "ready_for_review"):
            child.status = ChildJobStatus.PREVIEW
            child.stage = "preview"
            child.asset_id = job_state.get("asset_id")
            any_changed = True

        elif raw_status in ("cancelled", "canceled"):
            child.status = ChildJobStatus.CANCELLED
            child.stage = "cancelled"
            any_changed = True

    if any_changed:
        plan.recompute_progress()

        # Build collection when all children are resolved.
        if plan.is_terminal and not plan.collection_id and plan.surface_type == "storyboard_generation":
            col_id = _build_collection(db, project_id, plan)
            if col_id:
                plan.collection_id = col_id

        save_pack(db, project_id, plan)

        # Publish terminal events.
        if plan.status == ExecutionStatus.COMPLETED:
            _publish_event(make_execution_completed_event(
                project_id=project_id,
                execution_id=execution_id,
                collection_id=plan.collection_id,
                surface_type=plan.surface_type,
                completed=plan.completed_children,
                total=plan.total_children,
                timestamp=_now(),
            ))
        elif plan.status == ExecutionStatus.FAILED:
            _publish_event(ExecutionEvent(
                event_type=ExecutionEventType.EXECUTION_FAILED,
                project_id=project_id,
                execution_id=execution_id,
                status="failed",
                completed=plan.completed_children,
                total=plan.total_children,
                surface_type=plan.surface_type,
                timestamp=_now(),
            ))

    return plan
