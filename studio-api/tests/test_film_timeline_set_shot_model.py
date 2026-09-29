"""Timeline V2 Slice C / C7: persist shot model selection via the Film Timeline authority.

D6: model choice is Timeline-owned shot state. set_shot_generator mutates
shot.state.modelId only — it never submits, plans, or starts a job.

No Comfy / network: the adapter boundary is stubbed so nothing can reach a runtime.
"""

from __future__ import annotations

import uuid

import pytest

from app.db import Base, Job, Project, Scene, SessionLocal, engine
from app.film_timeline import orchestrator
from app.film_timeline.orchestrator import FilmTimelineError, set_shot_generator
from app.film_timeline.store import require_film

H3 = "minimax-h3-i2v-local"


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Set Shot Model", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="prompt",
            duration_sec=10.0,
            aspect_ratio="16:9",
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


@pytest.fixture()
def adapter(monkeypatch):
    """Stub the adapter boundary: resolving must not reach a real runtime."""

    class _Stub:
        capabilities = None

    stub = _Stub()
    monkeypatch.setattr(orchestrator, "_adapter", lambda generator_id: stub)
    return stub


def _new_shot(db, pid, sid) -> str:
    created = orchestrator.create_shot(db, pid, sid, name="Shot 01", duration_sec=10.0)
    return created["shot"]["id"]


def _shot(db, pid, sid, shot_id):
    film = require_film(db, pid, sid)
    return next(item for item in film.shots if item.id == shot_id)


def test_set_shot_generator_persists_and_reloads(db_scene, adapter):
    db, pid, sid = db_scene
    shot_id = _new_shot(db, pid, sid)

    result = set_shot_generator(db, pid, sid, shot_id, H3)

    assert result["ok"] is True
    assert result["shot"]["state"]["modelId"] == H3
    assert _shot(db, pid, sid, shot_id).state.modelId == H3

    # Durable across a fresh session — the model choice survives a project reopen.
    other = SessionLocal()
    try:
        assert _shot(other, pid, sid, shot_id).state.modelId == H3
    finally:
        other.close()


@pytest.mark.parametrize("generator_id", ["not-a-real-generator-xyz", "wan-2.1-text-to-video"])
def test_set_shot_generator_unknown_fails_closed(db_scene, adapter, generator_id):
    db, pid, sid = db_scene
    shot_id = _new_shot(db, pid, sid)
    before = _shot(db, pid, sid, shot_id).state.modelId

    with pytest.raises(FilmTimelineError) as exc:
        set_shot_generator(db, pid, sid, shot_id, generator_id)

    assert exc.value.code == "MODEL_UNAVAILABLE"
    # Fail-closed: the rejection changed nothing on disk.
    assert _shot(db, pid, sid, shot_id).state.modelId == before


def test_set_shot_generator_creates_no_job_or_segment(db_scene, adapter):
    db, pid, sid = db_scene
    shot_id = _new_shot(db, pid, sid)

    result = set_shot_generator(db, pid, sid, shot_id, H3)

    assert result["ok"] is True
    assert result["shot"]["segments"] == []
    assert result["shot"]["generationPlan"] == []
    assert result["shot"]["state"]["segmentIds"] == []
    shot = _shot(db, pid, sid, shot_id)
    assert shot.segments == []
    assert shot.generationPlan == []
    assert db.query(Job).filter(Job.project_id == pid).count() == 0
