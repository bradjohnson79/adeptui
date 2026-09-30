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
#
# CERTIFIED CONTRACT (2026-09-26 pre-simplification backup + ORDER 8B): creator
# Batch mutation is RETIRED. service.add_batch / duplicate_batch / delete_batch
# early-return CREATOR_BATCH_MUTATION_DISABLED. Proof:
#   app/director_timeline_w46/creator_batch_surface.py:62  (constant)
#   app/director_timeline_w46/service.py:265-278           (add_batch gate)
#   tests/test_order8b_no_batch_mint.py:110-115            (gate assertion)
#   tests/test_timeline_architecture_guard_p4.py:35-43     (gate assertion)
# The duration-seed intent below is preserved on the paths that remain legal:
#   SceneService.create -> legal_canvas.seed_new_scene_duration_sec (scene seed)
#   service.rematerialize_execution_windows -> CD plan windows (execution)
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


def _assert_creator_batch_mutation_disabled(res: dict) -> None:
    """CERTIFIED GATE: creator Batch CRUD is retired (ORDER 8B / Systems P5).

    Proof (certified contract, not a regression):
      app/director_timeline_w46/creator_batch_surface.py:62  CREATOR_BATCH_MUTATION_DISABLED
      app/director_timeline_w46/service.py:265-278           add_batch early-returns the gate
      tests/test_order8b_no_batch_mint.py:110-115            asserts the same gate
      tests/test_timeline_architecture_guard_p4.py:35-43     asserts the same gate
      backups/timeline-pre-simplification/2026-09-26-.../backend-director_timeline_w46/creator_batch_surface.py:62
    """
    assert res["ok"] is False
    assert res["error"] == "CREATOR_BATCH_MUTATION_DISABLED"
    assert "Co-Director plan" in res["message"]
    assert res["mock"] is False


def _window_planned_total(master: dict) -> float:
    """Planned duration sum of the LEGAL CD-plan Execution Windows."""
    return sum(
        float((b.get("duration") or {}).get("plannedDuration") or 0.0)
        for b in (master.get("batchBlocks") or [])
    )


def test_add_batch_h3_default_seeds_fifteen(db_scene):
    """H3 with no creator duration seeds 15s on the canonical scene owner.

    Creator add_batch / W46 rematerialize stay retired. The seed law is
    legal_canvas.seed_new_scene_duration_sec plus SceneService.create.
    """
    from app.services.scene_service import SceneService
    from app.video_runtime.legal_canvas import seed_new_scene_duration_sec

    db, pid, _sid = db_scene
    assert seed_new_scene_duration_sec("minimax-h3") == 15.0
    scene = SceneService.create(db, pid, {"engine": "minimax-h3", "prompt": "seed"})
    assert scene.duration_sec == 15.0


def test_add_batch_explicit_duration_never_overridden(db_scene):
    """An explicit creator duration is kept. The 15s H3 seed does not replace it."""
    from app.services.scene_service import SceneService
    from app.video_runtime.legal_canvas import seed_new_scene_duration_sec

    db, pid, _sid = db_scene
    assert seed_new_scene_duration_sec("minimax-h3") == 15.0
    scene = SceneService.create(db, pid, {"engine": "minimax-h3", "duration_sec": 8.0})
    assert scene.duration_sec == 8.0


def test_add_batch_non_h3_keeps_legacy_seed(db_scene):
    """Non-H3 engines keep the legacy 5s seed on the canonical scene-create path."""
    from app.services.scene_service import SceneService
    from app.video_runtime.legal_canvas import seed_new_scene_duration_sec

    db, pid, _sid = db_scene
    assert seed_new_scene_duration_sec("wan-t2v-local") == 5.0
    scene = SceneService.create(db, pid, {"engine": "wan-t2v-local", "prompt": "w"})
    assert scene.duration_sec == 5.0


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
