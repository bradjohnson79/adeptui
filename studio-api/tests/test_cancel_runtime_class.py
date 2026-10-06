"""Cancel runtime classification — no live Comfy interrupt."""

from __future__ import annotations

import asyncio
import json
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

    row = Project(id=str(uuid.uuid4()), name="Cancel class project")
    db_session.add(row)
    db_session.commit()
    return row


def _job(db_session, project_id: str, *, params: dict, prompt_id: str | None = None):
    from app.db import Job

    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind="txt2vid",
        status="running",
        progress=0.2,
        message="Running",
        stage="processing",
        params_json=json.dumps(params),
        comfy_prompt_id=prompt_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(job)
    db_session.commit()
    return job


def test_runtime_class_route_a_and_hosted(db_session, project):
    from app.queue_worker import JobQueue

    h3 = _job(db_session, project.id, params={"engine": "minimax-h3"}, prompt_id="p-8192")
    hosted = _job(
        db_session,
        project.id,
        params={"engine": "fal_seedance", "useFal": True},
        prompt_id="bytedance/seedance-2.5/text-to-video",
    )
    local = _job(db_session, project.id, params={"engine": "ltx-2.5"}, prompt_id="p-8188")
    assert JobQueue._job_runtime_class(h3) == "route_a"
    assert JobQueue._job_runtime_class(hosted) == "hosted"
    assert JobQueue._job_runtime_class(local) == "local_comfy"
    assert JobQueue._looks_like_provider_model_id(hosted.comfy_prompt_id) is True
    assert JobQueue._looks_like_provider_model_id("abc-prompt") is False


def test_hosted_cancel_never_touches_comfy(db_session, project, monkeypatch):
    from app.queue_worker import JobQueue

    job = _job(
        db_session,
        project.id,
        params={"provider": "fal_seedance", "useFal": True},
        prompt_id="bytedance/seedance-2.0/text-to-video",
    )
    q = JobQueue()
    called = {"halt": 0}

    def boom(*_a, **_k):
        called["halt"] += 1
        raise AssertionError("hosted cancel must not build a Comfy halt client")

    monkeypatch.setattr(q, "_halt_client_for", boom)
    result = asyncio.run(q.cancel_and_halt(job.id))
    assert result["cancelRejected"] is True
    assert result["cancelReason"] == "PROVIDER_CANCEL_UNSUPPORTED"
    assert called["halt"] == 0
    db_session.expire_all()
    from app.db import Job

    row = db_session.get(Job, job.id)
    assert row.status == "running"


def test_route_a_cancel_uses_8192_client(db_session, project, monkeypatch):
    from app.queue_worker import JobQueue

    job = _job(db_session, project.id, params={"engine": "minimax-h3"}, prompt_id="route-a-prompt")
    q = JobQueue()
    q._active_prompt[job.id] = "route-a-prompt"
    q._heavy_local_active = job.id
    seen = {"base": None, "free": None}

    class _FakeClient:
        def __init__(self, base_url: str):
            seen["base"] = base_url

        async def delete_queue_prompt(self, prompt_id: str):
            return {"ok": True}

        async def halt_prompt(self, prompt_id, *, confirm_timeout_sec=20.0, request_free_memory=True):
            seen["free"] = request_free_memory
            return {"confirmedStopped": True, "interrupt": True}

    def factory(runtime_class: str):
        assert runtime_class == "route_a"
        return _FakeClient("http://127.0.0.1:8192")

    monkeypatch.setattr(q, "_halt_client_for", factory)
    result = asyncio.run(q.cancel_and_halt(job.id))
    assert result["ok"] is True
    assert result["runtimeClass"] == "route_a"
    assert seen["base"] == "http://127.0.0.1:8192"
    assert seen["free"] is False
    db_session.expire_all()
    from app.db import Job

    row = db_session.get(Job, job.id)
    assert row.status == "cancelled"


def test_timeline_h3_ref2v_is_local_comfy_not_route_a(db_session, project):
    from app.queue_worker import JobQueue
    from app.video_runtime.job_model import merge_video_runtime_history

    job = _job(db_session, project.id, params={"engine": "minimax-h3"}, prompt_id="p-8188-h3")
    job.history_json = merge_video_runtime_history(
        job.history_json,
        {
            "r2v": {
                "mechanism": "h3_ref2va",
                "runtime": "adept-comfy-8188",
            }
        },
    )
    db_session.commit()
    assert JobQueue._job_is_timeline_h3_local(job) is True
    assert JobQueue._job_is_route_a_job(job) is False
    assert JobQueue._job_is_bound_route_a(job) is False
    assert JobQueue._job_skips_comfy_bind(job) is False
    assert JobQueue._job_runtime_class(job) == "local_comfy"
    job.status = "cancelled"
    job.stage = "cancelled"
    db_session.commit()


def test_timeline_h3_cancel_uses_8188_client(db_session, project, monkeypatch):
    from app.queue_worker import JobQueue
    from app.video_runtime.job_model import merge_video_runtime_history

    job = _job(db_session, project.id, params={"engine": "minimax-h3"}, prompt_id="p-8188-h3")
    job.history_json = merge_video_runtime_history(
        job.history_json,
        {"r2v": {"mechanism": "h3_ref2va", "runtime": "adept-comfy-8188"}},
    )
    db_session.commit()
    q = JobQueue()
    q._active_prompt[job.id] = "p-8188-h3"
    q._heavy_local_active = job.id
    seen = {"runtime": None, "base": None}

    class _FakeClient:
        def __init__(self, base_url: str):
            seen["base"] = base_url

        async def delete_queue_prompt(self, prompt_id: str):
            return {"ok": True}

        async def halt_prompt(self, prompt_id, *, confirm_timeout_sec=20.0, request_free_memory=True):
            return {"confirmedStopped": True, "interrupt": True}

    def factory(runtime_class: str):
        seen["runtime"] = runtime_class
        assert runtime_class == "local_comfy"
        return _FakeClient("http://127.0.0.1:8188")

    monkeypatch.setattr(q, "_halt_client_for", factory)
    result = asyncio.run(q.cancel_and_halt(job.id))
    assert result["ok"] is True
    assert result["runtimeClass"] == "local_comfy"
    assert seen["runtime"] == "local_comfy"
    assert seen["base"] == "http://127.0.0.1:8188"
    db_session.expire_all()
    from app.db import Job

    row = db_session.get(Job, job.id)
    assert row.status == "cancelled"
