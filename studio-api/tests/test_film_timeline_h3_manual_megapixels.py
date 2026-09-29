"""Timeline V2 Slice A1 (F1): manual MiniMax H3 megapixels drive generate dims.

D1: a manual h3Resolution.megapixels tier overrides the Auto 0.7 MP policy at a
new generation boundary. D2: Continue/Retake with a prior completed segment
preserves the prior segment legalCanvas — a manual MP change never resizes an
existing continuity chain.

No Comfy / network: the H3 adapter keeps its real capabilities + validate, and
only submit is stubbed.
"""

from __future__ import annotations

import uuid

import pytest

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.director_timeline_w46.generation.contracts import NormalizedJobSubmission
from app.film_timeline import orchestrator
from app.film_timeline.contracts import ReferenceAsset
from app.film_timeline.store import require_film, save_film

H3 = "minimax-h3-i2v-local"


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="H3 Manual MP", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="prompt",
            duration_sec=10.0,
            aspect_ratio="21:9",
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


@pytest.fixture()
def h3(monkeypatch):
    """Real H3 capabilities/validate; submit never reaches Comfy."""
    adapter = MiniMaxH3I2VLocalAdapter()
    calls: list = []

    def _submit(request):
        calls.append(request)
        return NormalizedJobSubmission(
            generatorId=request.generatorId,
            providerJobId="provider-1",
            queueJobId="queue-1",
        )

    monkeypatch.setattr(adapter, "submit", _submit)
    monkeypatch.setattr(orchestrator, "_adapter", lambda generator_id: adapter)
    # Continue must not probe media from a nonexistent asset during a unit test.
    monkeypatch.setattr(
        "app.film_timeline.continuity.ensure_segment_continuity",
        lambda db, project_id, scene_id, shot, segment: {},
    )
    return calls


def _new_shot(db, pid, sid) -> str:
    created = orchestrator.create_shot(db, pid, sid, name="Shot 01", duration_sec=10.0, generator_id=H3)
    shot_id = created["shot"]["id"]
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    shot.state.firstFrameAssetId = "asset-still"
    shot.state.references = [
        ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")
    ]
    save_film(db, pid, sid, film)
    return shot_id


def _set_aspect(db, sid: str, aspect: str) -> None:
    scene = db.get(Scene, sid)
    scene.aspect_ratio = aspect
    db.commit()


def _resolved(result: dict) -> dict:
    return result["segment"]["generationMetadata"]["resolvedGeneration"]


def test_manual_12_mp_21x9_generate_is_1728x736(db_scene, h3):
    db, pid, sid = db_scene
    shot_id = _new_shot(db, pid, sid)
    result = orchestrator.generate_shot(
        db,
        pid,
        sid,
        shot_id,
        timed_prompt="wide",
        provider_options={"h3Resolution": {"mode": "manual", "megapixels": 1.2}},
    )
    assert result["ok"] is True, result
    resolved = _resolved(result)
    assert (resolved["width"], resolved["height"]) == (1728, 736)
    assert resolved["aspect"] == "21:9"
    assert resolved["megapixels"] == 1.2
    assert result["segment"]["generationMetadata"]["legalCanvas"]["width"] == 1728
    assert len(h3) == 1


def test_manual_12_mp_16x9_generate_is_1504x832(db_scene, h3):
    db, pid, sid = db_scene
    _set_aspect(db, sid, "16:9")
    shot_id = _new_shot(db, pid, sid)
    result = orchestrator.generate_shot(
        db,
        pid,
        sid,
        shot_id,
        timed_prompt="wide",
        provider_options={"h3Resolution": {"mode": "manual", "megapixels": 1.2}},
    )
    assert result["ok"] is True, result
    resolved = _resolved(result)
    assert (resolved["width"], resolved["height"]) == (1504, 832)
    assert resolved["aspect"] == "16:9"
    assert resolved["megapixels"] == 1.2


@pytest.mark.parametrize(
    "h3_resolution",
    [None, {"mode": "auto", "megapixels": 1.2}],
)
def test_auto_21x9_generate_is_1312x576(db_scene, h3, h3_resolution):
    db, pid, sid = db_scene
    shot_id = _new_shot(db, pid, sid)
    provider_options = {"h3Resolution": h3_resolution} if h3_resolution is not None else None
    result = orchestrator.generate_shot(
        db,
        pid,
        sid,
        shot_id,
        timed_prompt="wide",
        provider_options=provider_options,
    )
    assert result["ok"] is True, result
    resolved = _resolved(result)
    assert (resolved["width"], resolved["height"]) == (1312, 576)
    assert resolved["aspect"] == "21:9"
    assert resolved["megapixels"] == 0.7


def test_continue_keeps_prior_legal_canvas_when_manual_12(db_scene, h3):
    db, pid, sid = db_scene
    shot_id = _new_shot(db, pid, sid)
    first = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="wide")
    assert first["ok"] is True, first
    prior_canvas = dict(first["segment"]["generationMetadata"]["legalCanvas"])
    assert (prior_canvas["width"], prior_canvas["height"]) == (1312, 576)

    # Finish the first segment so the next call is a real Continue.
    film = require_film(db, pid, sid)
    prior_segment = next(item for shot in film.shots for item in shot.segments if item.id == first["segment"]["id"])
    prior_segment.status = "completed"
    prior_segment.assetId = "asset-prior"
    save_film(db, pid, sid, film)

    result = orchestrator.continue_shot(
        db,
        pid,
        sid,
        shot_id,
        duration_sec=5.0,
        timed_prompt="she turns",
        provider_options={"h3Resolution": {"mode": "manual", "megapixels": 1.2}},
    )
    assert result["ok"] is True, result
    resolved = _resolved(result)
    assert (resolved["width"], resolved["height"]) == (prior_canvas["width"], prior_canvas["height"])
    assert (resolved["width"], resolved["height"]) != (1728, 736)
    assert result["segment"]["generationMetadata"]["legalCanvas"] == prior_canvas


def test_illegal_manual_megapixels_fails_closed_without_submission(db_scene, h3):
    db, pid, sid = db_scene
    shot_id = _new_shot(db, pid, sid)
    result = orchestrator.generate_shot(
        db,
        pid,
        sid,
        shot_id,
        timed_prompt="wide",
        provider_options={"h3Resolution": {"mode": "manual", "megapixels": 0.99}},
    )
    assert result["ok"] is False, result
    assert result["error"] == "H3_ILLEGAL_MEGAPIXELS"
    assert "0.99 MP is not a supported MiniMax H3 canvas" in result["message"]
    segment = next(item for shot in result["film"]["shots"] for item in shot["segments"] if item["status"] == "failed")
    assert segment["status"] == "failed"
    assert segment["error"] == result["message"]
    assert "submission" not in segment["generationMetadata"]
    assert h3 == []
