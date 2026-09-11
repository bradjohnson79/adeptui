"""Timeline MiniMax H3 duration: Inspector request, 15s max, 17k+5 snap."""

from __future__ import annotations

import pytest

from app.director_timeline_w46.capabilities import validate_duration
from app.director_timeline_w46.generation.request_builder import _h3_duration_for_request
from app.video_runtime.legal_canvas import snap_h3_timeline_duration


def test_snap_five_eight_twelve_fifteen():
    five = snap_h3_timeline_duration(5.0)
    assert five["ok"] is True
    assert five["frames"] == 124
    assert five["snapped"] is True
    assert five["durationSec"] == 5.0  # creator request stays clean
    assert abs(five["legalDurationSec"] - (124 / 24)) < 1e-9

    eight = snap_h3_timeline_duration(8.0)
    assert eight["ok"] is True
    assert eight["frames"] == 192
    assert eight["durationSec"] == 8.0
    assert eight["snapped"] is False

    twelve = snap_h3_timeline_duration(12.0)
    assert twelve["ok"] is True
    assert twelve["frames"] == 294
    assert twelve["snapped"] is True
    assert twelve["durationSec"] == 12.0
    assert abs(twelve["legalDurationSec"] - (294 / 24)) < 1e-9

    fifteen = snap_h3_timeline_duration(15.0)
    assert fifteen["ok"] is True
    assert fifteen["frames"] == 362
    assert fifteen["snapped"] is True
    assert fifteen["durationSec"] == 15.0


def test_sixteen_seconds_blocked():
    out = snap_h3_timeline_duration(16.0)
    assert out["ok"] is False
    assert out["durationSec"] is None
    assert out["maxDurationSec"] == 15.0
    assert "15" in (out.get("message") or "")


def test_validate_duration_h3_twelve_ok_sixteen_blocked():
    ok = validate_duration("minimax-h3", 12.0)
    assert ok["ok"] is True
    assert ok["maxDurationSec"] == 15.0
    assert ok["legalDurationSec"] == 294 / 24

    blocked = validate_duration("minimax-h3-t2v-local", 16.0)
    assert blocked["ok"] is False
    assert blocked["maxDurationSec"] == 15.0


def test_request_builder_snaps_and_discloses():
    legal, extras = _h3_duration_for_request("minimax-h3", 12.0)
    assert abs(legal - (294 / 24)) < 1e-6
    assert extras["durationSnapDisclosed"] is True
    assert extras["requestedDurationSec"] == 12.0
    assert extras["legalFrameCount"] == 294


def test_snap_default_is_h3_seed_fifteen():
    out = snap_h3_timeline_duration(None)
    assert out["ok"] is True
    assert out["defaulted"] is True
    assert out["durationSec"] == 15.0
    assert out["requestedDurationSec"] == 15.0
    assert out["frames"] == 362


def test_seed_new_scene_duration_h3_and_ltx():
    from app.video_runtime.legal_canvas import seed_new_scene_duration_sec, sanitize_creator_duration_sec

    assert seed_new_scene_duration_sec("minimax-h3") == 15.0
    assert seed_new_scene_duration_sec("auto") == 15.0
    assert seed_new_scene_duration_sec(None) == 15.0
    assert seed_new_scene_duration_sec("ltx-2.5") == 20.0
    assert seed_new_scene_duration_sec("ltx-2.5-distilled") == 20.0
    assert seed_new_scene_duration_sec("wan") == 5.0
    assert sanitize_creator_duration_sec(5.166666666666667) == 5.2
    assert sanitize_creator_duration_sec(15.000000000000002) == 15.0
    assert sanitize_creator_duration_sec(15.0) == 15.0
    assert sanitize_creator_duration_sec(7.291666666666667) == 7.3


# ---------------------------------------------------------------------------
# Layer 2 — batch-creation + scene-creation seeding (creator choice wins)
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_scene():
    import uuid

    from app.db import Base, Project, Scene, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="H3 Seed Cert", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="seed",
            duration_sec=15.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _batch_planned(res: dict) -> float:
    batch = res.get("batch") or {}
    if not batch and res.get("batchBlockId"):
        return -1.0
    return float(batch["duration"]["plannedDuration"])


def test_add_batch_h3_default_seeds_fifteen(db_scene):
    from app.director_timeline_w46 import service

    db, pid, sid = db_scene
    service.workspace(db, pid, sid)
    res = service.add_batch(db, pid, sid, label="Batch H3", generator_id="minimax-h3")
    assert _batch_planned(res) == 15.0


def test_add_batch_explicit_duration_never_overridden(db_scene):
    from app.director_timeline_w46 import service

    db, pid, sid = db_scene
    service.workspace(db, pid, sid)
    res = service.add_batch(db, pid, sid, label="Batch H3 explicit", planned_duration=8.0, generator_id="minimax-h3")
    assert _batch_planned(res) == 8.0


def test_add_batch_non_h3_keeps_legacy_seed(db_scene):
    from app.director_timeline_w46 import service

    db, pid, sid = db_scene
    service.workspace(db, pid, sid)
    res = service.add_batch(db, pid, sid, label="Batch WAN", generator_id="wan-t2v-local")
    assert _batch_planned(res) == 5.0


def test_scene_service_create_seeds_h3_fifteen(db_scene):
    from app.services.scene_service import SceneService

    db, pid, _sid = db_scene
    scene = SceneService.create(db, pid, {"engine": "minimax-h3", "prompt": "x"})
    assert scene.duration_sec == 15.0


def test_scene_service_create_explicit_duration_respected(db_scene):
    from app.services.scene_service import SceneService

    db, pid, _sid = db_scene
    scene = SceneService.create(db, pid, {"engine": "minimax-h3", "duration_sec": 9.0})
    assert scene.duration_sec == 9.0


def test_codirector_create_scene_no_hardcoded_five():
    """Co-Director create_scene must not hardcode 5.0 — None lets the seed law fire."""

    import inspect

    from app.codirector.tools.handlers import scenes

    src = inspect.getsource(scenes.apply_create_scene)
    assert 'or 5.0' not in src
    assert 'is not None else None' in src
