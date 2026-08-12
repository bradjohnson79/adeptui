"""Optional-source circuit breakers — skip flaky retrieval without blocking chat."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

_LOCK = Lock()
_FAILURES: dict[str, list[float]] = {}
_OPEN_UNTIL: dict[str, float] = {}

_WINDOW_SEC = 120.0
_THRESHOLD = 3
_COOLDOWN_SEC = 60.0


def record_failure(source: str) -> None:
    now = time.monotonic()
    with _LOCK:
        hist = [t for t in _FAILURES.get(source, []) if now - t < _WINDOW_SEC]
        hist.append(now)
        _FAILURES[source] = hist
        if len(hist) >= _THRESHOLD:
            _OPEN_UNTIL[source] = now + _COOLDOWN_SEC


def record_success(source: str) -> None:
    with _LOCK:
        _FAILURES.pop(source, None)
        _OPEN_UNTIL.pop(source, None)


def is_open(source: str) -> bool:
    now = time.monotonic()
    with _LOCK:
        until = _OPEN_UNTIL.get(source)
        if until is None:
            return False
        if now >= until:
            _OPEN_UNTIL.pop(source, None)
            return False
        return True


def snapshot() -> dict[str, Any]:
    now = time.monotonic()
    with _LOCK:
        return {
            "open": {k: max(0.0, v - now) for k, v in _OPEN_UNTIL.items() if v > now},
            "recentFailures": {k: len(v) for k, v in _FAILURES.items()},
        }
