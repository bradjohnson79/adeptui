"""Scene Creator Mini API children must overlap in the job worker.

Local / Comfy jobs stay one-at-a-time. A failed API sibling must not cancel
the other variant.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

import pytest


@pytest.fixture()
def db_session():
    from app.db import Job, SessionLocal, init_db

    init_db()
    db = SessionLocal()
    leftovers = (
        db.query(Job)
        .filter(Job.status == "queued", Job.params_json.contains("take-dispatch"))
        .all()
    )
    for row in leftovers:
        row.status = "done"
        row.stage = "complete"
    if leftovers:
        db.commit()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def project(db_session):
    from app.db import Project

    row = Project(id=str(uuid.uuid4()), name="Mini API dispatch project")
    db_session.add(row)
    db_session.commit()
    return row


def _job(db_session, project_id: str, *, mini: bool, hosted: bool, variation: str = "A"):
    from app.db import Job

    params = {
        "prompt": f"mini {variation}",
        "miniTakeId": "take-dispatch" if mini else None,
        "miniVariation": variation,
        "creativeContext": {"miniTakeId": "take-dispatch"} if mini else {},
    }
    if hosted:
        params["cloudPaid"] = True
        params["provider"] = "kie"
        params["kieImageModelId"] = "gpt-image-2"
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind="imagegen",
        status="queued",
        progress=0.0,
        params_json=json.dumps({k: v for k, v in params.items() if v is not None}),
    )
    db_session.add(job)
    db_session.commit()
    return job


def _close_jobs(db_session, *jobs) -> None:
    from app.db import Job

    ids = [job.id for job in jobs]
    if not ids:
        return
    rows = db_session.query(Job).filter(Job.id.in_(ids)).all()
    for row in rows:
        if str(row.status or "") in {"queued", "running"}:
            row.status = "done"
            row.stage = "complete"
    db_session.commit()


def _stop_queue(queue) -> None:
    for task in (queue._task, queue._drain_task, *list(getattr(queue, "_mini_api_tasks", set()))):
        if task is not None and not task.done():
            task.cancel()


def _silence_drain(monkeypatch) -> None:
    from app.queue_worker import JobQueue

    async def _no_drain(self):
        return {"started": [], "abandoned": [], "unboundFailed": []}

    monkeypatch.setattr(JobQueue, "drain_orphaned_queued", _no_drain)


def test_classifier_only_fans_out_hosted_mini_jobs(db_session, project):
    from app.queue_worker import JobQueue

    hosted_mini = _job(db_session, project.id, mini=True, hosted=True)
    local_mini = _job(db_session, project.id, mini=True, hosted=False)
    hosted_other = _job(db_session, project.id, mini=False, hosted=True)
    q = JobQueue()
    try:
        assert q._is_mini_api_concurrent_job(hosted_mini) is True
        assert q._is_mini_api_concurrent_job(local_mini) is False
        assert q._is_mini_api_concurrent_job(hosted_other) is False
    finally:
        _close_jobs(db_session, hosted_mini, local_mini, hosted_other)


def test_mini_api_children_start_together(db_session, project, monkeypatch):
    from app.queue_worker import JobQueue

    job_a = _job(db_session, project.id, mini=True, hosted=True, variation="A")
    job_b = _job(db_session, project.id, mini=True, hosted=True, variation="B")
    started: dict[str, float] = {}

    async def _fake_run(self, job_id: str) -> None:
        started[job_id] = time.monotonic()
        await asyncio.sleep(0.25)

    monkeypatch.setattr(JobQueue, "_run_job", _fake_run)
    _silence_drain(monkeypatch)
    queue = JobQueue()

    async def _go() -> None:
        queue.start()
        await queue.enqueue(job_a.id)
        await queue.enqueue(job_b.id)
        await asyncio.sleep(0.12)
        assert set(started) == {job_a.id, job_b.id}
        assert abs(started[job_a.id] - started[job_b.id]) < 0.1

    try:
        asyncio.run(_go())
    finally:
        _stop_queue(queue)
        _close_jobs(db_session, job_a, job_b)


def test_local_jobs_stay_serial(db_session, project, monkeypatch):
    from app.queue_worker import JobQueue

    job_a = _job(db_session, project.id, mini=True, hosted=False, variation="A")
    job_b = _job(db_session, project.id, mini=True, hosted=False, variation="B")
    started: list[tuple[str, float]] = []
    ended: list[tuple[str, float]] = []

    async def _fake_run(self, job_id: str) -> None:
        started.append((job_id, time.monotonic()))
        await asyncio.sleep(0.2)
        ended.append((job_id, time.monotonic()))

    monkeypatch.setattr(JobQueue, "_run_job", _fake_run)
    _silence_drain(monkeypatch)
    queue = JobQueue()

    async def _go() -> None:
        queue.start()
        await queue.enqueue(job_a.id)
        await queue.enqueue(job_b.id)
        await asyncio.sleep(0.1)
        assert len(started) == 1
        await asyncio.sleep(0.25)
        assert [row[0] for row in started] == [job_a.id, job_b.id]
        assert ended[0][1] <= started[1][1] + 0.02

    try:
        asyncio.run(_go())
    finally:
        _stop_queue(queue)
        _close_jobs(db_session, job_a, job_b)


def test_failed_api_sibling_does_not_cancel_the_other(db_session, project, monkeypatch):
    from app.queue_worker import JobQueue

    job_a = _job(db_session, project.id, mini=True, hosted=True, variation="A")
    job_b = _job(db_session, project.id, mini=True, hosted=True, variation="B")
    started: list[str] = []
    finished: list[str] = []

    async def _fake_run(self, job_id: str) -> None:
        started.append(job_id)
        if job_id == job_b.id:
            raise RuntimeError("provider failed B")
        await asyncio.sleep(0.15)
        finished.append(job_id)

    monkeypatch.setattr(JobQueue, "_run_job", _fake_run)
    _silence_drain(monkeypatch)
    queue = JobQueue()

    async def _go() -> None:
        queue.start()
        await queue.enqueue(job_a.id)
        await queue.enqueue(job_b.id)
        await asyncio.sleep(0.25)
        assert job_a.id in started
        assert job_b.id in started
        assert job_a.id in finished

    try:
        asyncio.run(_go())
        db_session.refresh(job_b)
        assert job_b.status == "failed"
        db_session.refresh(job_a)
        assert job_a.status != "cancelled"
    finally:
        _stop_queue(queue)
        _close_jobs(db_session, job_a, job_b)


def test_save_take_persists_children_before_dispatch(tmp_path, monkeypatch):
    from app.spatial_map import scene_creator_mini as mini

    order: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(mini, "_take_path", lambda _project, take_id: Path(tmp_path) / f"{take_id}.json")
    monkeypatch.setattr(mini, "_dispatch_mini_job_ids", lambda ids: order.append(("dispatch", list(ids))))

    take = {
        "id": "take-persist",
        "results": [
            {"id": "r-a", "variation": "A", "jobId": "job-a", "status": "queued"},
            {"id": "r-b", "variation": "B", "jobId": "job-b", "status": "queued"},
        ],
        "_dispatchJobIds": ["job-a", "job-b"],
    }
    mini.save_take("proj", take)
    saved = json.loads((Path(tmp_path) / "take-persist.json").read_text(encoding="utf-8"))
    assert saved["results"][0]["jobId"] == "job-a"
    assert saved["results"][1]["jobId"] == "job-b"
    assert "_dispatchJobIds" not in saved
    assert order == [("dispatch", ["job-a", "job-b"])]


def test_enqueue_variation_defers_worker_start() -> None:
    import inspect

    from app.spatial_map.scene_creator_mini import _enqueue_variation, save_take

    src = inspect.getsource(_enqueue_variation)
    assert '"deferEnqueue": True' in src
    save_src = inspect.getsource(save_take)
    assert "_dispatch_mini_job_ids" in save_src
