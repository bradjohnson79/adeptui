from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Any, Callable

from .schema import InstallJob

_LOCK = threading.RLock()
_SUBSCRIBERS: list[Callable[[dict[str, Any]], None]] = []
_RECENT: deque[dict[str, Any]] = deque(maxlen=200)
_EVENT_SEQ = 0


def publish_job(job: InstallJob | dict[str, Any]) -> dict[str, Any]:
    global _EVENT_SEQ
    if isinstance(job, InstallJob):
        payload = job.model_dump(mode="json", by_alias=True)
    else:
        payload = dict(job)
    with _LOCK:
        _EVENT_SEQ += 1
        event = {
            "id": str(_EVENT_SEQ),
            "type": "install_job",
            "ts": time.time(),
            "job": payload,
        }
        _RECENT.append(event)
        subscribers = list(_SUBSCRIBERS)
    for callback in subscribers:
        try:
            callback(event)
        except Exception:
            continue
    return event


def subscribe(callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
    with _LOCK:
        _SUBSCRIBERS.append(callback)

    def unsubscribe() -> None:
        with _LOCK:
            if callback in _SUBSCRIBERS:
                _SUBSCRIBERS.remove(callback)

    return unsubscribe


def recent_events(*, after_id: int | None = None) -> list[dict[str, Any]]:
    with _LOCK:
        events = list(_RECENT)
    if after_id is None:
        return events
    return [event for event in events if int(event.get("id") or 0) > after_id]


def encode_sse(event: dict[str, Any]) -> str:
    event_id = event.get("id")
    data = json.dumps(event, ensure_ascii=False)
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event.get('type') or 'install_job'}")
    lines.append(f"data: {data}")
    lines.append("")
    return "\n".join(lines) + "\n"
