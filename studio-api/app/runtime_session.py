"""Identity of this Studio API process.

A render belongs to the process that started it. After a crash or restart the
new process has a new id, and rows stamped with the old one are not live.
"""

from __future__ import annotations

from uuid import uuid4

_SESSION_ID = uuid4().hex


def current_runtime_session_id() -> str:
    return _SESSION_ID


def stamp_runtime_session(params: dict) -> dict:
    if not str(params.get("runtimeSessionId") or "").strip():
        params["runtimeSessionId"] = _SESSION_ID
    return params


def job_in_current_session(params: dict | None) -> bool:
    stored = str((params or {}).get("runtimeSessionId") or "").strip()
    return bool(stored) and stored == _SESSION_ID
