"""Local generation chrome attention — Local jobs raise it, hosted API does not."""

from __future__ import annotations

import json
import uuid

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

    row = Project(id=str(uuid.uuid4()), name="Local attention project")
    db_session.add(row)
    db_session.commit()
    return row


def _job(db_session, project_id: str, *, hosted: bool, mini: bool = False, status: str = "running"):
    from app.db import Job

    params = {"prompt": "still"}
    if hosted:
        params["cloudPaid"] = True
        params["provider"] = "kie"
    if mini:
        params["miniTakeId"] = "take-1"
        params["creativeContext"] = {"miniTakeId": "take-1"}
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind="imagegen",
        status=status,
        progress=0.2,
        params_json=json.dumps(params),
    )
    db_session.add(job)
    db_session.commit()
    return job


def _close(db_session, *jobs) -> None:
    from app.db import Job

    ids = [job.id for job in jobs]
    for row in db_session.query(Job).filter(Job.id.in_(ids)).all():
        row.status = "done"
        row.stage = "complete"
    db_session.commit()


def test_hosted_api_job_does_not_raise_attention(db_session, project):
    from app.runtime.local_generation import active_local_generation

    job = _job(db_session, project.id, hosted=True, mini=True)
    try:
        snap = active_local_generation(db_session)
        assert snap["active"] is False
    finally:
        _close(db_session, job)


def test_local_running_job_raises_attention(db_session, project):
    from app.runtime.local_generation import active_local_generation

    job = _job(db_session, project.id, hosted=False, mini=True)
    try:
        snap = active_local_generation(db_session)
        assert snap["active"] is True
        assert snap["jobId"] == job.id
        assert snap["projectId"] == project.id
        assert snap["feature"] == "Scene Creator Mini"
        assert snap["cancelable"] is True
    finally:
        _close(db_session, job)


def test_running_local_wins_over_queued_local(db_session, project):
    from app.runtime.local_generation import active_local_generation

    queued = _job(db_session, project.id, hosted=False, status="queued")
    running = _job(db_session, project.id, hosted=False, mini=True, status="running")
    try:
        snap = active_local_generation(db_session)
        assert snap["jobId"] == running.id
        assert snap["jobId"] != queued.id
    finally:
        _close(db_session, queued, running)


def test_awaiting_dispatch_is_ignored(db_session, project):
    from app.runtime.local_generation import active_local_generation

    job = _job(db_session, project.id, hosted=False)
    job.stage = "awaiting_dispatch"
    db_session.commit()
    try:
        snap = active_local_generation(db_session)
        assert snap["active"] is False
    finally:
        _close(db_session, job)


def test_local_generation_http_route_is_idle(client):
    resp = client.get("/api/runtime/local-generation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is False
    assert data["jobId"] is None
    assert data["cancelable"] is False


def test_creator_feature_labels():
    from app.runtime.local_generation import creator_feature_label

    assert creator_feature_label({"miniTakeId": "t"}) == "Scene Creator Mini"
    assert creator_feature_label({"purpose": "character_sheet"}) == "Character look"
    assert creator_feature_label({"purpose": "environment_reference_sheet"}) == "Environment Reference Sheet"
    assert creator_feature_label({}) == "local generation"
