"""Timeline Preflight reconnects Co-Director Production Readiness (no second engine)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.codirector.production_lifecycle.service import (
    assess_scene_readiness_from_project,
    scene_production_package,
)
from app.db import Base, Project, Scene, SessionLocal, engine


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Preflight Readiness", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="wide establishing",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def test_unassessed_scene_has_no_lifecycle_row(db_scene):
    db, pid, sid = db_scene
    pkg = scene_production_package(db, pid, sid)
    assert pkg.get("ok") is False
    assert pkg.get("error") == "Scene not found"


def test_assess_writes_lifecycle_row_through_existing_upsert(db_scene):
    db, pid, sid = db_scene
    result = assess_scene_readiness_from_project(db, pid, sid)
    assert result.get("ok") is True
    scene = result.get("scene") or {}
    assert scene.get("sceneId") == sid
    assert scene.get("liveComputed") is True
    assert scene.get("generationPlanReady") is True
    assert scene.get("status") in {"BLOCKED", "PARTIAL", "READY"}
    live = result.get("live") or {}
    cast = next(d for d in (live.get("departments") or []) if d["category"] == "cast")
    assert cast["status"] == "not_required"
    pkg = scene_production_package(db, pid, sid)
    assert pkg.get("error") != "Scene not found"
    assert (pkg.get("scene") or pkg.get("package") or {}).get("sceneId") == sid or (
        pkg.get("scene") or {}
    ).get("sceneId") == sid
