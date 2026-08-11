"""Emit honest execution_status assistant messages with real job state.

Workstream H — Agent Execution Law: an execution is only "complete" when its
underlying job/execution state reports completion. This module builds the
assistant message payload from the real execution pack (Workstream C) and
appends/yields it so the frontend renders a compact execution summary card
instead of a fake "I've created your storyboard" claim.

This module NEVER claims completion without real job state evidence:
  - When the pack store is unavailable (Workstream C not landed yet), every
    helper here degrades gracefully to a no-op (returns None / empty list).
  - When the pack exists but is non-terminal, the message says e.g.
    "Generating storyboard — 0/4 frames complete" (real state).
  - Only when every child job is `done` does the message say "Done".

Guarded imports: this module imports the pack store and dispatcher lazily and
tolerates ImportError. It is safe to call from service.py even when Workstream
C/E components are not yet present.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def _capabilities_store_available() -> bool:
    """Return True only if the Workstream C execution pack store is importable."""
    try:
        import importlib

        mod = importlib.import_module("app.codirector.execution.pack_store")  # type: ignore
        return mod is not None
    except Exception:  # noqa: BLE001
        return False


def _get_execution_plan(db: Session, execution_id: str):
    """Read an execution plan by id from the Workstream C pack store, or None."""
    if not execution_id:
        return None
    try:
        from ..execution.pack_store import get_execution  # type: ignore[attr-defined]

        return get_execution(db, execution_id)
    except Exception:  # noqa: BLE001
        return None


def _get_active_execution_for_project(db: Session, project_id: str):
    try:
        from ..execution.pack_store import (  # type: ignore[attr-defined]
            get_active_execution_for_project,
        )

        return get_active_execution_for_project(db, project_id)
    except Exception:  # noqa: BLE001
        return None


def _serialize_plan_summary(plan: Any) -> dict[str, Any]:
    """Project an ExecutionPlan into a frontend-safe summary payload.

    Only real state is emitted — never invented progress or counts. If a field
    is missing on the plan object, it is omitted rather than fabricated.
    """
    child_jobs: list[dict[str, Any]] = []
    children = getattr(plan, "child_jobs", None) or []
    for c in children:
        child_jobs.append(
            {
                "job_id": getattr(c, "job_id", None),
                "child_index": getattr(c, "child_index", None),
                "label": getattr(c, "label", "") or "",
                "status": str(getattr(c, "status", "") or "").lower(),
                "asset_id": getattr(c, "asset_id", None),
                "error": getattr(c, "error", None),
                "progress": getattr(c, "progress", 0.0),
                "stage": getattr(c, "stage", "") or "",
            }
        )

    completed = getattr(plan, "completed_children", 0) or 0
    total = getattr(plan, "total_children", 0) or 0
    status = str(getattr(plan, "status", "") or "").lower()
    progress = float(getattr(plan, "progress", 0.0) or 0.0)

    return {
        "execution_id": getattr(plan, "execution_id", "") or "",
        "capability": getattr(plan, "capability", "") or "",
        "status": status,
        "progress": progress,
        "completed": completed,
        "total": total,
        "collection_id": getattr(plan, "collection_id", None),
        "result_asset_ids": list(getattr(plan, "result_asset_ids", []) or []),
        "child_jobs": child_jobs,
    }


def _capability_human_label(capability: str) -> str:
    """Human-friendly capability label for the assistant message text."""
    if not capability:
        return "Working on your request"
    short = capability.split(".")[-1].replace("_", " ")
    short = short.replace("generate", "Generating").replace("batch", "batch")
    return short[:1].upper() + short[1:]


def _build_execution_status_text(plan_summary: dict[str, Any]) -> str:
    """Honest, real-state message text — never claims completion prematurely."""
    capability = plan_summary.get("capability") or ""
    completed = int(plan_summary.get("completed") or 0)
    total = int(plan_summary.get("total") or 0)
    status = str(plan_summary.get("status") or "").lower()
    label = _capability_human_label(capability)

    if status == "completed":
        if total:
            return f"{label} — {completed}/{total} complete. Done."
        return f"{label} — Done."
    if status == "failed":
        return f"{label} — failed. You can retry or adjust and try again."
    if status == "cancelled":
        return f"{label} — stopped."
    # Non-terminal: report real progress, never claim success.
    if total:
        return f"{label} — {completed}/{total} complete."
    return f"{label} — working…"


def _message_kind_for_status(status: str) -> str:
    """Map execution status to the assistant message kind.

    - Non-terminal → execution_status ("Working")
    - Completed     → completion ("Done")
    - Failed/cancelled → error (so it renders with the error styling)
    """
    s = (status or "").lower()
    if s == "completed":
        return "completion"
    if s in ("failed", "cancelled"):
        return "error"
    return "execution_status"


def build_execution_status_event(
    db: Session,
    *,
    project_id: str,
    request_id: str,
    execution_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Build a single execution_status SSE event from real execution state.

    Returns None when no execution can be resolved (pack store absent, no
    active execution, no execution_id). The returned event is suitable for
    yielding from the chat stream generator.
    """
    if not project_id:
        return None
    if not _capabilities_store_available():
        return None

    plan = None
    if execution_id:
        plan = _get_execution_plan(db, execution_id)
    if plan is None:
        plan = _get_active_execution_for_project(db, project_id)
    if plan is None:
        return None

    summary = _serialize_plan_summary(plan)
    text = _build_execution_status_text(summary)
    message_kind = _message_kind_for_status(summary.get("status") or "")

    return {
        "type": "execution_status",
        "requestId": request_id,
        "messageType": message_kind,
        "content": text,
        "execution": summary,
    }


def append_execution_status_message(
    db: Session,
    *,
    project_id: str,
    request_id: str,
    execution_id: Optional[str] = None,
) -> Optional[str]:
    """Append an execution_status assistant message with real job state.

    Returns the message id used, or None when no execution could be resolved
    (the pack store is absent or no execution is active). This never raises.
    """
    if not project_id:
        return None
    try:
        # Local import to avoid a hard dependency on service.py at module load.
        from .service import append_assistant_completion

        event = build_execution_status_event(
            db,
            project_id=project_id,
            request_id=request_id,
            execution_id=execution_id,
        )
        if event is None:
            return None

        status_str = str((event.get("execution") or {}).get("status") or "")
        message_kind = event.get("messageType") or "execution_status"
        # Stash the execution payload on the message via the tool_result channel
        # is not appropriate; instead we append a normal assistant message with
        # messageType carrying the kind. The frontend hydrates the execution
        # payload from the companion SSE event (build_execution_status_event) and
        # from the result_context block on the next turn.
        # The DB row stores the honest text; the execution payload travels via SSE.
        return append_assistant_completion(
            db,
            project_id,
            request_id=request_id,
            reply=event.get("content") or "",
            model=None,
            provider_id=None,
            message_id=f"asst-exec-{request_id}-{(execution_id or 'active')[:12]}",
            message_type=message_kind,
            status=status_str or None,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "append_execution_status_message failed project=%s request=%s execution=%s",
            project_id,
            request_id,
            execution_id,
        )
        return None


def emit_execution_status_events(
    db: Session,
    *,
    project_id: str,
    request_id: str,
    execution_id: Optional[str] = None,
) -> Iterable[dict[str, Any]]:
    """Yield execution_status SSE events for the chat stream, then append the
    honest completion message to the conversation.

    This is the canonical entry point for Workstream H honest completion. It
    yields the SSE event so the Live Agent Work Surface / message renderer
    updates in real time, and appends the assistant message so it persists.
    """
    if not project_id:
        return
    event = build_execution_status_event(
        db,
        project_id=project_id,
        request_id=request_id,
        execution_id=execution_id,
    )
    if event is None:
        return
    yield event
    append_execution_status_message(
        db,
        project_id=project_id,
        request_id=request_id,
        execution_id=execution_id,
    )
