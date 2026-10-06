"""One queued/running Studio job per scene, take, batch, and snapshot.

Repeated workspace loads observe that job. They do not enqueue another.
"""

from __future__ import annotations

import json
import threading
from typing import Any

LIVE_JOB_STATUSES = frozenset({"queued", "running", "pending", "submitted", "cancelling"})

_locks: dict[tuple[str, str, str, str], threading.Lock] = {}
_scene_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def tuple_key(scene_id: str, take_id: str, batch_id: str, snapshot_id: str) -> tuple[str, str, str, str]:
    return (str(scene_id or ""), str(take_id or ""), str(batch_id or ""), str(snapshot_id or ""))


def scene_flight(scene_id: str) -> threading.Lock:
    """One provider submit at a time for the whole scene."""
    key = str(scene_id or "")
    with _locks_guard:
        lock = _scene_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _scene_locks[key] = lock
        return lock


def single_flight(scene_id: str, take_id: str, batch_id: str, snapshot_id: str) -> threading.Lock:
    key = tuple_key(scene_id, take_id, batch_id, snapshot_id)
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def job_matches_tuple(
    params: dict[str, Any] | None,
    *,
    take_id: str,
    batch_id: str,
    snapshot_id: str,
) -> bool:
    row = params or {}
    if str(row.get("batchBlockId") or row.get("batchId") or "") != str(batch_id or ""):
        return False
    if str(row.get("executionSnapshotId") or row.get("snapshotId") or "") != str(snapshot_id or ""):
        return False
    stored_take = str(row.get("sceneTakeId") or "")
    wanted = str(take_id or "")
    if wanted and stored_take and stored_take != wanted:
        return False
    return True


def live_job_id(
    rows: list[dict[str, Any]],
    *,
    take_id: str,
    batch_id: str,
    snapshot_id: str,
) -> str | None:
    """Earliest queued/running job for the tuple. Later duplicates are not a second owner."""
    matches = []
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status not in LIVE_JOB_STATUSES:
            continue
        if not job_matches_tuple(
            row.get("params") if isinstance(row.get("params"), dict) else {},
            take_id=take_id,
            batch_id=batch_id,
            snapshot_id=snapshot_id,
        ):
            continue
        matches.append(row)
    if not matches:
        return None
    matches.sort(key=lambda row: str(row.get("created_at") or ""))
    return str(matches[0].get("id") or "") or None


def claim_scene_slot(
    rows: list[dict[str, Any]],
    *,
    take_id: str,
    batch_id: str,
    snapshot_id: str,
) -> dict[str, str]:
    """Multi-batch renders one window at a time.

    reuse — this window already has a queued/running job.
    defer — a different window is still queued/running; do not enqueue.
    submit — the scene has no live provider job.
    """
    same = live_job_id(rows, take_id=take_id, batch_id=batch_id, snapshot_id=snapshot_id)
    if same:
        return {"action": "reuse", "jobId": same}
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status not in LIVE_JOB_STATUSES:
            continue
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        if job_matches_tuple(params, take_id=take_id, batch_id=batch_id, snapshot_id=snapshot_id):
            continue
        job_id = str(row.get("id") or "")
        if job_id:
            return {"action": "defer", "jobId": job_id}
    return {"action": "submit", "jobId": ""}


def _live_rows_from_db(scene_id: str) -> list[dict[str, Any]]:
    from ...db import Job, SessionLocal

    db = SessionLocal()
    try:
        rows = (
            db.query(Job)
            .filter(Job.scene_id == scene_id, Job.status.in_(tuple(LIVE_JOB_STATUSES)))
            .all()
        )
        parsed: list[dict[str, Any]] = []
        for row in rows:
            try:
                params = json.loads(row.params_json or "{}")
            except Exception:
                params = {}
            if not isinstance(params, dict):
                params = {}
            parsed.append(
                {
                    "id": row.id,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "params": params,
                }
            )
        return parsed
    finally:
        db.close()


def find_live_studio_job(
    *,
    scene_id: str,
    take_id: str,
    batch_id: str,
    snapshot_id: str,
) -> str | None:
    return live_job_id(
        _live_rows_from_db(scene_id),
        take_id=take_id,
        batch_id=batch_id,
        snapshot_id=snapshot_id,
    )


def live_scene_batch_ids(scene_id: str, db=None) -> set[str]:
    """Batch ids that already have a queued or running Studio job.

    Callers without a persistence session (unit tests) have no live queue.
    """
    if db is None:
        return set()
    found: set[str] = set()
    for row in _live_rows_from_db(scene_id):
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        found.add(str(params.get("batchBlockId") or ""))
    return found


def scene_slot_for(
    *,
    scene_id: str,
    take_id: str,
    batch_id: str,
    snapshot_id: str,
) -> dict[str, str]:
    return claim_scene_slot(
        _live_rows_from_db(scene_id),
        take_id=take_id,
        batch_id=batch_id,
        snapshot_id=snapshot_id,
    )
