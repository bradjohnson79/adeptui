"""P11 regression: an enqueue failure must NOT be swallowed silently.

Previously ``generate_images`` did ``except Exception: pass`` around
``schedule_job_queue_enqueue``, leaving the job stuck at "queued" / 0%
forever (the silent 1h hang). Now it marks the job failed with a clear
creator-facing message and logs.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, Job, Project


@pytest.fixture()
def db(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-img", name="Image Product Pin"))
    session.commit()
    yield session
    session.close()


def test_enqueue_failure_marks_job_failed_not_silent(db, monkeypatch):
    from app.image_product import service

    # Minimal compiled intent so generate_images reaches the enqueue step.
    compiled = {
        "imageIntent": {
            "prompt": "a red cube",
            "enginePreference": "zimage",
            "seed": 1,
            "width": 1024,
            "height": 1024,
            "metadata": {},
        },
        "imageRuntime": {"workflowKey": "zimage.txt2img", "provider": "comfy"},
        "recommendation": {},
        "promptIntel": {},
    }
    monkeypatch.setattr(service, "compile_image_request", lambda project_id, b: compiled)

    # Enqueue raises — the old code swallowed this; the job would hang at 0%.
    def _boom(_job_id):
        raise RuntimeError("queue loop unavailable")

    monkeypatch.setattr(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        _boom,
    )

    result = None
    raised = None
    try:
        result = service.generate_images(db, project_id="proj-img", body={"prompt": "a red cube"})
    except RuntimeError as exc:
        # Fail-loud contract: enqueue failure raises with the creator-facing
        # message. The job must ALSO be persisted as failed before raising —
        # never left silently stuck at "queued" / 0%.
        raised = str(exc)

    # The job must be marked failed (not stuck at "queued").
    jobs = db.query(Job).filter(Job.project_id == "proj-img").all()
    assert jobs, "a job should have been created"
    failed = [j for j in jobs if str(j.status).lower() == "failed"]
    assert failed, "enqueue failure must mark the job failed, not leave it queued"
    # Creator-facing failure message (must name the enqueue failure, never silent).
    assert any("never started" in str(j.message or "").lower() for j in failed)
    assert any("queue loop unavailable" in str(j.message or "") for j in failed), (
        "the enqueue exception detail must be visible to the creator"
    )
    # The failure is surfaced to the caller, not swallowed.
    assert raised and "never started" in raised, "generate_images must raise on enqueue failure"
