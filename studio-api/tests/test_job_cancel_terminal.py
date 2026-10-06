"""Cancelled is terminal: refuse queued/done walk-backs. No live Comfy."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

import pytest


@pytest.fixture()
def db_session():
    from app.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def project(db_session):
    from app.db import Project

    row = Project(id=str(uuid.uuid4()), name="Cancel terminal project")
    db_session.add(row)
    db_session.commit()
    return row


def _make_job(db_session, project_id: str, *, status: str, kind: str = "imagegen", stage: str = ""):
    from app.db import Job

    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind=kind,
        status=status,
        progress=0.4 if status == "running" else 0.0,
        message="Cancelled leftover" if status == "cancelled" else "Queued",
        stage=stage or ("cancelled" if status == "cancelled" else ""),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(job)
    db_session.commit()
    return job


def test_set_status_done_refuses_cancelled(db_session, project):
    from app.db import Job
    from app.queue_worker import JobQueue

    job = _make_job(db_session, project.id, status="cancelled", stage="cancelled")
    q = JobQueue()
    q._set_status(job.id, "done", 1.0, "Scene render complete")
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "cancelled"
    assert row.stage == "cancelled"
    assert "Scene render complete" not in (row.message or "")


def test_set_status_queued_refuses_cancelled(db_session, project):
    from app.db import Job
    from app.queue_worker import JobQueue

    job = _make_job(db_session, project.id, status="cancelled", stage="cancelled")
    q = JobQueue()
    q._set_status(job.id, "queued", 0.05, "Claimed")
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "cancelled"


def test_drain_orphaned_queued_does_not_requeue_cancelled(db_session, project):
    from app.db import Job
    from app.queue_worker import JobQueue

    cancelled = _make_job(db_session, project.id, status="cancelled", stage="cancelled")
    flagged = _make_job(db_session, project.id, status="queued")
    q = JobQueue()
    q._cancel.add(flagged.id)

    result = asyncio.run(q.drain_orphaned_queued())
    started = set(result["started"])
    assert cancelled.id not in started
    assert flagged.id not in started
    # Do not leave a queued row for later recovery tests sharing this SQLite file.
    row = db_session.get(Job, flagged.id)
    row.status = "cancelled"
    row.stage = "cancelled"
    db_session.commit()


def test_drain_skips_in_flight_queued_job(db_session, project):
    from app.db import Job
    from app.queue_worker import JobQueue

    inflight = _make_job(db_session, project.id, status="queued", stage="claimed")
    q = JobQueue()
    q._in_flight.add(inflight.id)
    result = asyncio.run(q.drain_orphaned_queued())
    assert inflight.id not in result["started"]
    row = db_session.get(Job, inflight.id)
    row.status = "cancelled"
    row.stage = "cancelled"
    db_session.commit()


def test_run_job_does_not_reset_cancelled_to_queued(db_session, project):
    from app.db import Job
    from app.queue_worker import JobQueue

    job = _make_job(db_session, project.id, status="cancelled", stage="cancelled")
    q = JobQueue()
    asyncio.run(q._run_job(job.id))
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "cancelled"
    assert row.stage == "cancelled"


def test_queue_prompt_for_job_raises_when_cancelled(db_session, project, monkeypatch):
    from app.comfy_client import JobCancelledError
    from app.db import Job
    from app.queue_worker import JobQueue

    job = _make_job(db_session, project.id, status="cancelled", stage="cancelled")
    q = JobQueue()
    called = {"n": 0}

    async def boom(*a, **k):
        called["n"] += 1
        return "should-not-submit"

    monkeypatch.setattr("app.queue_worker.comfy.queue_prompt", boom)
    with pytest.raises(JobCancelledError):
        asyncio.run(q._queue_prompt_for_job(job, {"1": {"class_type": "X"}}))
    assert called["n"] == 0
