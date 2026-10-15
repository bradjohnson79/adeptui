"""In-process event bus with persisted Production Executive events."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from sqlalchemy.orm import Session

from .store import JobStore

Subscriber = Callable[[dict[str, Any]], None]


class ProductionEventBus:
    """Publish typed events: persist first, then notify in-process subscribers."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Subscriber]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Subscriber) -> None:
        self._subs[event_type].append(handler)

    def subscribe_all(self, handler: Subscriber) -> None:
        self._subs["*"].append(handler)

    def publish(
        self,
        db: Session,
        *,
        project_id: str,
        event_type: str,
        job_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_row = JobStore._event(
            db,
            job_id=job_id,
            project_id=project_id,
            event_type=event_type,
            payload=payload or {},
        )
        db.commit()
        message = {
            "id": event_row.id,
            "jobId": job_id,
            "projectId": project_id,
            "eventType": event_type,
            "payload": payload or {},
        }
        for handler in list(self._subs.get(event_type, [])):
            handler(message)
        for handler in list(self._subs.get("*", [])):
            handler(message)
        return message


event_bus = ProductionEventBus()
