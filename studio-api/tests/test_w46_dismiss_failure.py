"""Dismiss-failure regressions (Live Drift False-Positive Closure, UX repair).

A terminal job failure pins the scene's Preview Monitor to a red "Render
failed" overlay until a successful re-render replaces it. For a failure the
creator has read and understood (e.g. a stale failure from a since-repaired
bug) there must be a lightweight, persistent acknowledgment path:

- dismiss_failure records the job id on the scene master (idempotent),
- the dismissal survives reload (it is server-persisted master state),
- the job row and batch status are untouched (history stays honest),
- the save does NOT touch batch updatedAt provenance (touch_batches=False),
- arbitrary / foreign / non-failed job ids are rejected,
- a NEW failure (different job id) still surfaces the overlay (composer-side
  behavior is pinned in TimelinePreviewComposer.test.ts).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Job, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import service, store


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Dismiss Failure Cert", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="dismiss failure",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    yield db, pid, sid
    db.close()


def _add_job(db: Session, pid: str, sid: str, *, status: str = "failed") -> str:
    job_id = str(uuid.uuid4())
    db.add(
        Job(
            id=job_id,
            project_id=pid,
            scene_id=sid,
            kind="render_scene",
            status=status,
            progress=0.0,
            message="simulated failure" if status == "failed" else "job",
            stage=status,
        )
    )
    db.commit()
    return job_id


def test_dismiss_failure_persists_on_master(db_scene):
    db, pid, sid = db_scene
    job_id = _add_job(db, pid, sid)

    result = service.dismiss_failure(db, pid, sid, job_id)
    assert result["ok"] is True
    assert job_id in result["master"]["dismissedFailureJobIds"]

    # Survives a fresh load (server-persisted, not session state).
    loaded = store.load_master(db, pid, sid)
    assert loaded["ok"] is True
    assert job_id in loaded["master"]["dismissedFailureJobIds"]


def test_dismiss_failure_is_idempotent(db_scene):
    db, pid, sid = db_scene
    job_id = _add_job(db, pid, sid)

    service.dismiss_failure(db, pid, sid, job_id)
    service.dismiss_failure(db, pid, sid, job_id)

    loaded = store.load_master(db, pid, sid)
    assert loaded["master"]["dismissedFailureJobIds"].count(job_id) == 1


def test_dismiss_failure_accumulates_multiple_job_ids(db_scene):
    db, pid, sid = db_scene
    ids = [_add_job(db, pid, sid) for _ in range(3)]
    for job_id in ids:
        service.dismiss_failure(db, pid, sid, job_id)

    loaded = store.load_master(db, pid, sid)
    assert sorted(loaded["master"]["dismissedFailureJobIds"]) == sorted(ids)


def test_dismiss_failure_rejects_unknown_foreign_or_nonfailed_jobs(db_scene):
    db, pid, sid = db_scene

    unknown = service.dismiss_failure(db, pid, sid, str(uuid.uuid4()))
    assert unknown["ok"] is False
    assert unknown["error"] == "JOB_NOT_FOUND"

    # Job belonging to a DIFFERENT scene must not be dismissable here.
    other_sid = str(uuid.uuid4())
    db.add(
        Scene(
            id=other_sid,
            project_id=pid,
            index=1,
            name="Scene 2",
            prompt="other",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    foreign_id = _add_job(db, pid, other_sid)
    foreign = service.dismiss_failure(db, pid, sid, foreign_id)
    assert foreign["ok"] is False
    assert foreign["error"] == "JOB_NOT_FOUND"

    running_id = _add_job(db, pid, sid, status="running")
    not_failed = service.dismiss_failure(db, pid, sid, running_id)
    assert not_failed["ok"] is False
    assert not_failed["error"] == "JOB_NOT_FAILED"


def test_dismiss_failure_requires_job_id_and_scene(db_scene):
    db, pid, sid = db_scene
    blank = service.dismiss_failure(db, pid, sid, "  ")
    assert blank["ok"] is False
    assert blank["error"] == "JOB_ID_REQUIRED"

    missing = service.dismiss_failure(db, pid, str(uuid.uuid4()), str(uuid.uuid4()))
    assert missing["ok"] is False


def test_dismiss_failure_does_not_touch_batch_updated_at(db_scene):
    """A dismissal is a master-level acknowledgment, not a batch edit — batch
    updatedAt provenance must be left exactly as it was."""
    db, pid, sid = db_scene
    job_id = _add_job(db, pid, sid)

    before = store.load_master(db, pid, sid)["master"]
    before_stamps = {b["id"]: b.get("updatedAt") for b in before["batchBlocks"]}
    assert before_stamps, "fixture scene must have at least one batch"

    result = service.dismiss_failure(db, pid, sid, job_id)
    assert result["ok"] is True

    after = store.load_master(db, pid, sid)["master"]
    after_stamps = {b["id"]: b.get("updatedAt") for b in after["batchBlocks"]}
    assert after_stamps == before_stamps


def test_master_defaults_to_no_dismissals(db_scene):
    db, pid, sid = db_scene
    loaded = store.load_master(db, pid, sid)
    assert loaded["ok"] is True
    assert loaded["master"]["dismissedFailureJobIds"] == []
