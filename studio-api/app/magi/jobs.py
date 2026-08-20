"""MAGI long-running job helpers — no optimistic running, no duplicate actives."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from ..db import Job, SessionLocal

TERMINAL = frozenset({"done", "failed", "cancelled", "timed_out", "canceled"})
ACTIVE = frozenset({"queued", "running", "submitted"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_active_duplicate(db: Session, project_id: str, kind: str, fingerprint: str) -> Job | None:
    rows = (
        db.query(Job)
        .filter(Job.project_id == project_id, Job.kind == kind)
        .order_by(Job.created_at.desc())
        .limit(20)
        .all()
    )
    for job in rows:
        if job.status not in ACTIVE:
            continue
        try:
            params = json.loads(job.params_json or "{}")
        except json.JSONDecodeError:
            params = {}
        if str(params.get("fingerprint") or "") == fingerprint:
            return job
    return None


def enqueue_job(
    db: Session,
    *,
    project_id: str,
    kind: str,
    params: dict[str, Any],
    message: str,
) -> Job:
    fingerprint = str(params.get("fingerprint") or "")
    if fingerprint:
        existing = find_active_duplicate(db, project_id, kind, fingerprint)
        if existing is not None:
            return existing
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind=kind,
        status="queued",
        progress=0.0,
        stage="Queued",
        message=message,
        params_json=json.dumps(params),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_job(db: Session, job: Job, *, stage: str = "Dispatching") -> bool:
    if job.status != "queued":
        return False
    job.status = "running"
    job.stage = stage
    job.progress = max(float(job.progress or 0), 0.05)
    job.message = stage
    db.commit()
    return True


def finish_job(db: Session, job: Job, *, ok: bool, message: str, result: dict[str, Any] | None = None) -> None:
    if job.status in {"cancelled", "canceled"}:
        return
    job.status = "done" if ok else "failed"
    job.stage = "Completed" if ok else "Failed"
    job.progress = 1.0
    job.message = message[:1000]
    if result:
        job.output_path = str(result.get("outputPath") or job.output_path or "") or job.output_path
        history = {}
        try:
            history = json.loads(job.history_json or "{}")
        except json.JSONDecodeError:
            history = {}
        history.update(result)
        job.history_json = json.dumps(history)
    db.commit()


def job_cancelled(db: Session, job_id: str) -> bool:
    row = db.get(Job, job_id)
    return bool(row and row.status in {"cancelled", "canceled"})


def start_background(job_id: str, runner: Callable[[str], None]) -> None:
    thread = threading.Thread(target=runner, args=(job_id,), daemon=True, name=f"magi-job-{job_id[:8]}")
    thread.start()


def run_with_session(job_id: str, handler: Callable[[Session, Job], dict[str, Any]]) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        if job.status in TERMINAL:
            return
        if not claim_job(db, job):
            return
        try:
            result = handler(db, job)
            finish_job(
                db,
                job,
                ok=bool(result.get("ok")),
                message=str(result.get("message") or ("Ready" if result.get("ok") else "Failed")),
                result=result,
            )
        except Exception as exc:
            finish_job(db, job, ok=False, message=str(exc)[:800], result={"ok": False, "error": str(exc)})
    finally:
        db.close()
