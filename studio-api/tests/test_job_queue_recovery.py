"""Studio job queue restart recovery.

M3.0a recorded, as condition C3, that `queue_worker.JobQueue` is an in-process asyncio
queue with nothing reading back the `Job` rows an earlier process left behind. These tests
cover the recovery pass added for M3.0b: queued work is re-enqueued, running work is closed
as interrupted rather than silently re-submitted, and terminal rows are never touched.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta

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

    row = Project(id=str(uuid.uuid4()), name="Queue recovery project")
    db_session.add(row)
    db_session.commit()
    return row


def _make_job(db_session, project_id: str, *, status: str, age_hours: float = 0.0, kind: str = "render_scene"):
    from app.db import Job

    created = datetime.utcnow() - timedelta(hours=age_hours)
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind=kind,
        status=status,
        progress=0.4 if status == "running" else 0.0,
        message="In flight" if status == "running" else "Queued",
        created_at=created,
        updated_at=created,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _fresh_queue():
    from app.queue_worker import JobQueue

    return JobQueue()


def _run_recovery(queue) -> dict[str, list[str]]:
    return asyncio.run(queue.recover_interrupted())


def test_running_job_is_closed_as_interrupted(db_session, project):
    """A render the process was carrying when it died must not stay non-terminal."""
    from app.db import Job
    from app.queue_worker import INTERRUPTED_MESSAGE

    job = _make_job(db_session, project.id, status="running")
    queue = _fresh_queue()

    result = _run_recovery(queue)

    assert job.id in result["interrupted"]
    assert job.id not in result["resumed"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "failed"
    assert row.stage == "interrupted"
    assert row.message == INTERRUPTED_MESSAGE
    assert queue._q.empty()


def test_previous_session_job_is_cancelled_without_touching_comfy(db_session, project, monkeypatch):
    """A crashed session must not be observed, resumed, or sent back to the GPU."""
    from app.db import Job
    from app.queue_worker import SESSION_INTERRUPTED_MESSAGE, JobQueue

    job = _make_job(db_session, project.id, status="running", kind="render_scene")
    job.comfy_prompt_id = "prompt-from-dead-session"
    job.params_json = json.dumps(
        {
            "runtimeSessionId": "previous-session",
            "engine": "minimax-h3",
            "mechanism": "h3_ref2va",
            "output_asset_id": "asset-kept",
        }
    )
    job.output_path = "C:/kept/partial.mp4"
    db_session.commit()

    def _forbid_comfy(_prompt_id):
        raise AssertionError("startup reconciliation contacted Comfy")

    monkeypatch.setattr(JobQueue, "_comfy_prompt_activity", staticmethod(_forbid_comfy))
    result = _run_recovery(_fresh_queue())

    assert job.id in result["interrupted"]
    assert job.id not in result["resumed"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "cancelled"
    assert row.stage == "interrupted"
    assert row.message == SESSION_INTERRUPTED_MESSAGE
    assert row.output_path == "C:/kept/partial.mp4"


def test_recent_queued_job_is_re_enqueued(db_session, project):
    """Queued work never reached a provider, so resuming it repeats nothing."""
    from app.db import Job

    job = _make_job(db_session, project.id, status="queued", kind="imagegen")
    queue = _fresh_queue()

    result = _run_recovery(queue)

    assert job.id in result["resumed"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "queued"
    drained = [queue._q.get_nowait() for _ in range(queue._q.qsize())]
    assert job.id in drained


def test_stale_running_comfy_job_is_failed_when_prompt_already_done(db_session, project, monkeypatch):
    from app.db import Job
    from app.queue_worker import RESULT_NOT_REGISTERED_MESSAGE, JobQueue

    job = _make_job(db_session, project.id, status="running", kind="imagegen")
    job.comfy_prompt_id = "prompt-done"
    job.updated_at = datetime.utcnow() - timedelta(seconds=120)
    db_session.commit()
    queue = _fresh_queue()
    monkeypatch.setattr(JobQueue, "_comfy_prompt_activity", staticmethod(lambda _pid: "done"))
    monkeypatch.setattr(JobQueue, "_harvest_completed_local_comfy_job", lambda self, db, row: False)

    failed = queue.fail_stale_running_comfy(older_than_sec=60)

    assert job.id in failed
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "failed"
    assert row.message == RESULT_NOT_REGISTERED_MESSAGE


def test_stale_running_harvests_completed_comfy_output(db_session, project, monkeypatch):
    from app.db import Job
    from app.queue_worker import JobQueue

    job = _make_job(db_session, project.id, status="running", kind="render_scene")
    job.comfy_prompt_id = "prompt-done"
    job.updated_at = datetime.utcnow() - timedelta(seconds=120)
    db_session.commit()
    queue = _fresh_queue()
    monkeypatch.setattr(JobQueue, "_comfy_prompt_activity", staticmethod(lambda _pid: "done"))

    def _harvest(self, db, row):
        row.status = "done"
        row.stage = "complete"
        row.message = "Scene render complete"
        row.output_path = "C:/tmp/reconciled.mp4"
        row.progress = 1.0
        return True

    monkeypatch.setattr(JobQueue, "_harvest_completed_local_comfy_job", _harvest)

    failed = queue.fail_stale_running_comfy(older_than_sec=60)

    assert job.id not in failed
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "done"
    assert row.output_path == "C:/tmp/reconciled.mp4"


def test_stale_running_idle_with_live_comfy_is_worker_lost(db_session, project, monkeypatch):
    from app.db import Job
    from app.queue_worker import WORKER_LOST_PROMPT_MESSAGE, JobQueue

    job = _make_job(db_session, project.id, status="running", kind="render_scene")
    job.comfy_prompt_id = "prompt-idle"
    job.updated_at = datetime.utcnow() - timedelta(seconds=120)
    db_session.commit()
    queue = _fresh_queue()
    monkeypatch.setattr(JobQueue, "_comfy_prompt_activity", staticmethod(lambda _pid: "idle"))
    monkeypatch.setattr(JobQueue, "_comfy_runtime_reachable", staticmethod(lambda: True))

    failed = queue.fail_stale_running_comfy(older_than_sec=60)

    assert job.id in failed
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "failed"
    assert row.message == WORKER_LOST_PROMPT_MESSAGE


def test_stale_running_idle_with_dead_comfy_uses_picture_engine_message(db_session, project, monkeypatch):
    from app.db import Job
    from app.queue_worker import STALE_RUNNING_MESSAGE, JobQueue

    job = _make_job(db_session, project.id, status="running", kind="render_scene")
    job.comfy_prompt_id = "prompt-idle"
    job.updated_at = datetime.utcnow() - timedelta(seconds=120)
    db_session.commit()
    queue = _fresh_queue()
    monkeypatch.setattr(JobQueue, "_comfy_prompt_activity", staticmethod(lambda _pid: "idle"))
    monkeypatch.setattr(JobQueue, "_comfy_runtime_reachable", staticmethod(lambda: False))

    failed = queue.fail_stale_running_comfy(older_than_sec=60)

    assert job.id in failed
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "failed"
    assert row.message == STALE_RUNNING_MESSAGE


def test_recover_observes_active_local_comfy_instead_of_interrupting(db_session, project, monkeypatch):
    from app.db import Job
    from app.queue_worker import JobQueue

    job = _make_job(db_session, project.id, status="running", kind="render_scene")
    job.comfy_prompt_id = "prompt-live"
    from app.runtime_session import current_runtime_session_id

    job.params_json = json.dumps(
        {
            "runtimeSessionId": current_runtime_session_id(),
            "engine": "minimax-h3",
            "mechanism": "h3_ref2va",
            "runtime": "adept-comfy-8188",
        }
    )
    db_session.commit()
    monkeypatch.setattr(JobQueue, "_comfy_prompt_activity", staticmethod(lambda _pid: "active"))

    result = _run_recovery(_fresh_queue())

    assert job.id not in result["interrupted"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "running"
    row.status = "cancelled"
    row.stage = "cancelled"
    db_session.commit()


def test_queued_image_never_dispatched_is_failed_on_recovery(db_session, project):
    """A job that sat queued for hours never reached a provider — do not start it now."""
    from app.db import Job
    from app.queue_worker import NEVER_STARTED_MESSAGE

    job = _make_job(db_session, project.id, status="queued", age_hours=2, kind="imagegen")
    job.stage = "Queued"
    db_session.commit()
    queue = _fresh_queue()

    result = _run_recovery(queue)

    assert job.id in result["interrupted"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "failed"
    assert row.message == NEVER_STARTED_MESSAGE


def test_stale_queued_job_is_failed_rather_than_started(db_session, project):
    """A day-old queued row is a leftover, not a pending request."""
    from app.db import Job
    from app.queue_worker import STALE_MESSAGE

    job = _make_job(db_session, project.id, status="queued", age_hours=72)
    queue = _fresh_queue()

    result = _run_recovery(queue)

    assert job.id in result["interrupted"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "failed"
    assert row.stage == "interrupted"
    assert row.message == STALE_MESSAGE


def test_terminal_jobs_are_left_alone(db_session, project):
    from app.db import Job

    done = _make_job(db_session, project.id, status="done")
    failed = _make_job(db_session, project.id, status="failed")
    cancelled = _make_job(db_session, project.id, status="cancelled")
    queue = _fresh_queue()

    result = _run_recovery(queue)

    touched = set(result["resumed"]) | set(result["interrupted"])
    assert touched.isdisjoint({done.id, failed.id, cancelled.id})
    db_session.expire_all()
    assert db_session.get(Job, done.id).status == "done"
    assert db_session.get(Job, failed.id).status == "failed"
    assert db_session.get(Job, cancelled.id).status == "cancelled"


def test_recovery_is_recorded_in_job_history(db_session, project):
    """The audit trail has to say a restart did this, not the provider."""
    from app.db import Job

    running = _make_job(db_session, project.id, status="running")
    queued = _make_job(db_session, project.id, status="queued")

    _run_recovery(_fresh_queue())

    db_session.expire_all()
    for job_id, action, previous in (
        (running.id, "interrupted", "running"),
        (queued.id, "resumed", "queued"),
    ):
        history = json.loads(db_session.get(Job, job_id).history_json or "{}")
        entries = history.get("recovery") or []
        assert entries, f"no recovery entry for {action} job"
        assert entries[-1]["action"] == action
        assert entries[-1]["previousStatus"] == previous


def test_recovery_max_age_is_configurable(db_session, project, monkeypatch):
    from app.db import Job

    monkeypatch.setenv("STUDIO_JOB_RECOVERY_MAX_AGE_HOURS", "0.001")
    job = _make_job(db_session, project.id, status="queued", age_hours=1)

    result = _run_recovery(_fresh_queue())

    assert job.id in result["interrupted"]
    db_session.expire_all()
    assert db_session.get(Job, job.id).status == "failed"


def test_drain_starts_orphaned_queued_jobs(db_session, project):
    from app.db import Job
    from app.queue_worker import JobQueue

    orphan = _make_job(db_session, project.id, status="queued", kind="imagegen")
    queue = _fresh_queue()
    assert queue._q.empty()

    result = asyncio.run(queue.drain_orphaned_queued())

    assert orphan.id in result["started"]
    drained = [queue._q.get_nowait() for _ in range(queue._q.qsize())]
    assert orphan.id in drained
    db_session.expire_all()
    assert db_session.get(Job, orphan.id).status == "queued"


def test_recover_skips_approved_character_sheet(db_session, project, monkeypatch):
    from app.db import Job
    from app.queue_worker import STALE_APPROVED_CRS_MESSAGE, JobQueue

    job = _make_job(db_session, project.id, status="queued", kind="imagegen")
    from app.runtime_session import current_runtime_session_id

    job.params_json = json.dumps(
        {
            "runtimeSessionId": current_runtime_session_id(),
            "purpose": "character_sheet",
            "tag": "korri_four_view",
            "creativeContext": {"characterId": "char-korri"},
        }
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.queue_worker.queued_job_is_stale_approved_crs",
        lambda row, db=None: row.id == job.id,
    )
    result = _run_recovery(_fresh_queue())
    assert job.id in result["interrupted"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "failed"
    assert row.message == STALE_APPROVED_CRS_MESSAGE


def test_recovery_runs_on_api_startup(db_session, project, monkeypatch):
    """Booting the real app through its lifespan closes the row a dead process left."""
    from unittest.mock import AsyncMock

    from fastapi.testclient import TestClient

    from app.db import Job
    from app.main import app, job_queue
    from app.routers import api

    job = _make_job(db_session, project.id, status="running")
    monkeypatch.setattr(job_queue, "start", lambda: None)
    monkeypatch.setattr(api.job_queue, "enqueue", AsyncMock())

    with TestClient(app):
        pass

    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "failed"
    assert row.stage == "interrupted"


def test_bound_route_a_queued_job_is_not_re_enqueued(db_session, project):
    """A Route A prompt already on :8192 must not be submitted a second time."""
    from app.db import Job
    from app.queue_worker import JobQueue

    job = _make_job(db_session, project.id, status="queued")
    from app.runtime_session import current_runtime_session_id

    job.params_json = json.dumps(
        {
            "runtimeSessionId": current_runtime_session_id(),
            "engine": "minimax-h3",
            "width": 1280,
            "height": 704,
        }
    )
    job.comfy_prompt_id = "26c6d762-ad6b-4fea-bf4f-58630c47feb1"
    job.stage = "preparing"
    db_session.commit()
    queue = _fresh_queue()

    result = _run_recovery(queue)

    assert job.id not in result["resumed"]
    assert job.id not in result["interrupted"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "running"
    assert row.stage == "processing"
    queued = []
    while not queue._q.empty():
        queued.append(queue._q.get_nowait())
    assert job.id not in queued
    assert JobQueue._job_skips_comfy_bind(row)


def test_bound_route_a_running_job_is_not_interrupted(db_session, project):
    from app.db import Job

    job = _make_job(db_session, project.id, status="running")
    from app.runtime_session import current_runtime_session_id

    job.params_json = json.dumps(
        {"runtimeSessionId": current_runtime_session_id(), "engine": "minimax-h3"}
    )
    job.comfy_prompt_id = "26c6d762-ad6b-4fea-bf4f-58630c47feb1"
    db_session.commit()
    queue = _fresh_queue()

    result = _run_recovery(queue)

    assert job.id not in result["interrupted"]
    assert job.id not in result["resumed"]
    db_session.expire_all()
    row = db_session.get(Job, job.id)
    assert row.status == "running"
