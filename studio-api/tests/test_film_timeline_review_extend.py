"""Review & Extend is a second entry into Continue Shot, after Omni review."""

from __future__ import annotations

import inspect
import uuid

import pytest

from app.db import Base, Project, Scene, SessionLocal, engine
from app.film_timeline import orchestrator
from app.film_timeline.contracts import Segment
from app.film_timeline.store import require_film, save_film


@pytest.fixture()
def scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Project(id=pid, name="Review extend", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="prompt",
            duration_sec=5.0,
            aspect_ratio="16:9",
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _completed_shot(db, pid, sid):
    created = orchestrator.create_shot(db, pid, sid, timed_prompt="She reaches the door", generator_id="minimax-h3-i2v-local")
    shot_id = created["shot"]["id"]
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    segment = Segment(status="completed", assetId="asset-base", durationSec=5, timedPrompt="She reaches the door")
    shot.segments = [segment]
    shot.state.segmentIds = [segment.id]
    shot.state.modelId = "minimax-h3-i2v-local"
    save_film(db, pid, sid, film)
    return shot_id, segment.id


def test_review_extend_records_omni_then_uses_continue_shot(scene, monkeypatch):
    db, pid, sid = scene
    shot_id, segment_id = _completed_shot(db, pid, sid)
    calls = []

    def _packet(*_args, **_kwargs):
        return {"omni": {"status": "reviewed", "rangeStartSec": 4.0, "rangeEndSec": 5.0}}

    def _submit(*_args, **kwargs):
        calls.append(kwargs.get("continue_from"))
        return {"ok": True, "executor": "continue_shot"}

    monkeypatch.setattr("app.film_timeline.continuity.ensure_segment_continuity", _packet)
    monkeypatch.setattr(orchestrator, "_submit_plan", _submit)
    result = orchestrator.review_extend(db, pid, sid, shot_id, duration_sec=5, timed_prompt="She opens the door")
    assert result["ok"] is True
    assert calls and calls[0] is not None
    assert calls[0].id == segment_id
    reloaded = require_film(db, pid, sid)
    shot = next(item for item in reloaded.shots if item.id == shot_id)
    marker = shot.segments[0].generationMetadata["reviewExtend"]
    assert marker["reviewed"] is True
    assert marker["omniStatus"] == "reviewed"
    source = inspect.getsource(orchestrator.review_extend)
    assert "continue_shot(" in source
    assert "_build_and_run_h3_ref2v" not in source
    assert "directorTimelineExtend" not in source


def test_continue_shot_stays_independent_of_review_extend(scene, monkeypatch):
    db, pid, sid = scene
    shot_id, segment_id = _completed_shot(db, pid, sid)

    def _submit(*_args, **kwargs):
        assert kwargs.get("continue_from").id == segment_id
        return {"ok": True, "executor": "continue_shot"}

    monkeypatch.setattr(orchestrator, "_submit_plan", _submit)
    result = orchestrator.continue_shot(db, pid, sid, shot_id, duration_sec=5, timed_prompt="She opens the door")
    assert result["executor"] == "continue_shot"
    reloaded = require_film(db, pid, sid)
    shot = next(item for item in reloaded.shots if item.id == shot_id)
    assert "reviewExtend" not in (shot.segments[0].generationMetadata or {})
