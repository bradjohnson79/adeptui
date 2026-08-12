"""Track active Co-Director inference so Production Assurance can report BUSY."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Iterator, Optional


@dataclass
class InferenceActivitySnapshot:
    activeCount: int
    busy: bool
    startedAt: Optional[str] = None
    label: Optional[str] = None


_LOCK = RLock()
_ACTIVE = 0
_STARTED_AT: Optional[str] = None
_LABEL: Optional[str] = None


def begin_inference(label: str = "active_turn") -> None:
    global _ACTIVE, _STARTED_AT, _LABEL
    with _LOCK:
        _ACTIVE += 1
        if _ACTIVE == 1:
            _STARTED_AT = datetime.now(timezone.utc).isoformat()
            _LABEL = label


def end_inference() -> None:
    global _ACTIVE, _STARTED_AT, _LABEL
    with _LOCK:
        _ACTIVE = max(0, _ACTIVE - 1)
        if _ACTIVE == 0:
            _STARTED_AT = None
            _LABEL = None


@contextmanager
def track_inference(label: str = "active_turn") -> Iterator[None]:
    begin_inference(label)
    try:
        yield
    finally:
        end_inference()


def snapshot() -> InferenceActivitySnapshot:
    with _LOCK:
        return InferenceActivitySnapshot(
            activeCount=_ACTIVE,
            busy=_ACTIVE > 0,
            startedAt=_STARTED_AT,
            label=_LABEL,
        )
