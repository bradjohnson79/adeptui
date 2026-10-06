"""New Scene stability regression — engine="auto" must never 500 GET /master.

Root cause of the Priority-One New Scene crash: FilmTimelineShell.createScene
posts engine="auto" (dynamic inheritance of the project default). The W46
empty-master bootstrap passed that raw marker into the Timeline generator
registry, which only accepts concrete ids — GeneratorValidationError escaped
as a 500 on GET /api/director-timeline/.../master for every new scene. The
frontend selection race then retried that 500 in a tight loop, and the
resulting transport errors tripped the global Studio API Offline banner.

These tests pin the repair in creator_scope.identity_converge: inheritance
markers resolve to the project engine default (then the local-first floor)
before the window planner is asked for a certified single-pass duration.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import store
from app.services.scene_service import SceneService


def _project(db: Session, name: str, engine_default: str | None = None) -> str:
    pid = str(uuid.uuid4())
    project = Project(id=pid, name=name)
    if engine_default is not None:
        project.engine_default = engine_default
    db.add(project)
    db.commit()
    return pid


def _scene_with_empty_master(
    db: Session,
    pid: str,
    *,
    engine_id: str,
    duration: float = 15.0,
    index: int = 0,
) -> str:
    sid = str(uuid.uuid4())
    master = {
        "version": 1,
        "mode": "image_planning",
        "sceneGeneratorId": None,
        "batchBlocks": [],
        "executionSnapshots": {},
    }
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=index,
            name=f"Scene {index + 1}",
            prompt="",
            engine=engine_id,
            duration_sec=duration,
            director_json=json.dumps({"timelineMaster": master}),
        )
    )
    db.commit()
    return sid


def test_auto_engine_scene_master_bootstraps_without_error():
    """The exact New Scene repro: engine='auto' + null sceneGeneratorId."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        pid = _project(db, "Auto Engine Regression")
        sid = _scene_with_empty_master(db, pid, engine_id="auto")

        loaded = store.load_master(db, pid, sid)
        assert loaded["ok"] is True
        master = loaded["master"]
        # Inheritance resolved to the project default (minimax-h3), never "auto".
        assert master.get("sceneGeneratorId") == "minimax-h3"
        blocks = master.get("batchBlocks") or []
        assert len(blocks) == 1
        assert float((blocks[0].get("duration") or {}).get("plannedDuration") or 0) > 0

        # Idempotent: the second read keeps the same window id (no re-mint).
        again = store.load_master(db, pid, sid)
        assert again["master"]["batchBlocks"][0]["id"] == blocks[0]["id"]
    finally:
        db.close()


def test_auto_engine_scene_with_hosted_project_default_uses_local_floor():
    """A hosted project default is valid for generation routing but unknown to
    the local window planner; empty-master window sizing must still succeed."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        pid = _project(db, "Hosted Default Regression", engine_default="fal_seedance_2_5")
        sid = _scene_with_empty_master(db, pid, engine_id="auto")

        loaded = store.load_master(db, pid, sid)
        assert loaded["ok"] is True
        master = loaded["master"]
        assert master.get("sceneGeneratorId") == "minimax-h3"
        assert len(master.get("batchBlocks") or []) == 1
    finally:
        db.close()


def test_create_then_read_race_and_previous_scene_intact():
    """Create-through-service → immediate master read must not observe a
    half-created scene, and the previously populated scene stays readable."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        pid = _project(db, "Create Read Race")
        # Populated existing scene: concrete engine + an existing window.
        old_sid = _scene_with_empty_master(db, pid, engine_id="minimax-h3", duration=20.0, index=0)
        first = store.load_master(db, pid, old_sid)
        assert first["ok"] is True
        old_window_id = first["master"]["batchBlocks"][0]["id"]

        # The exact New Scene write path (SceneService.create, engine="auto").
        created = SceneService.create(
            db,
            pid,
            {"name": "Scene 2", "engine": "auto", "duration_sec": 15.0, "prompt": ""},
        )
        db.commit()

        # Immediate canonical read of the new scene (the hydration hop).
        loaded_new = store.load_master(db, pid, created.id)
        assert loaded_new["ok"] is True
        assert loaded_new["master"].get("sceneGeneratorId") == "minimax-h3"
        assert len(loaded_new["master"].get("batchBlocks") or []) == 1

        # Previous scene untouched: same window id, same generator.
        loaded_old = store.load_master(db, pid, old_sid)
        assert loaded_old["ok"] is True
        assert loaded_old["master"]["batchBlocks"][0]["id"] == old_window_id
        assert loaded_old["master"].get("sceneGeneratorId") == "minimax-h3"
    finally:
        db.close()
