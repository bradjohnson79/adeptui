"""Notifications derived from Production Executive events (separate from audit)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .events import event_bus
from .store import JobStore

_NOTIFY_TYPES = frozenset(
    {
        "job.status_changed",
        "job.blocked",
        "job.failed",
        "job.completed",
        "job.needs_review",
        "provider.unavailable",
    }
)


def _level_for(event_type: str, payload: dict[str, Any]) -> str:
    to = str(payload.get("to") or "")
    if event_type in ("job.failed", "provider.unavailable") or to == "Failed":
        return "error"
    if event_type in ("job.blocked", "job.needs_review") or to in (
        "Blocked",
        "NeedsReview",
    ):
        return "warn"
    if to == "Completed" or event_type == "job.completed":
        return "success"
    return "info"


def _title_for(event_type: str, payload: dict[str, Any]) -> str:
    to = payload.get("to")
    if to:
        return f"Job → {to}"
    return event_type.replace(".", " ").title()


def derive_notification(db: Session, message: dict[str, Any]) -> None:
    event_type = str(message.get("eventType") or "")
    if event_type not in _NOTIFY_TYPES and not (
        event_type == "job.status_changed"
        and message.get("payload", {}).get("to")
        in ("Blocked", "Failed", "Completed", "NeedsReview", "Paused", "Cancelled")
    ):
        return
    payload = dict(message.get("payload") or {})
    JobStore.create_notification(
        db,
        project_id=str(message["projectId"]),
        job_id=message.get("jobId"),
        event_id=message.get("id"),
        level=_level_for(event_type, payload),
        title=_title_for(event_type, payload),
        body=str(payload.get("reason") or payload.get("message") or event_type),
    )


def wire_notification_subscribers() -> None:
    """Idempotent wiring of event → notification derivation."""
    if getattr(wire_notification_subscribers, "_wired", False):
        return

    def _handler(message: dict[str, Any]) -> None:
        # Notifications use a fresh session path via JobStore.create_notification
        # which commits; callers already pass committed event ids.
        from ...db import SessionLocal

        db = SessionLocal()
        try:
            derive_notification(db, message)
        finally:
            db.close()

    event_bus.subscribe_all(_handler)
    wire_notification_subscribers._wired = True  # type: ignore[attr-defined]


wire_notification_subscribers()
