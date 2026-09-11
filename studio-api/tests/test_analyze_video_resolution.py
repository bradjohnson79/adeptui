"""Regression: analyze.video must watch the scene's MASTERED render, not the first batch take.

Scene 10-style projects hold several full-length takes on batchBlocks[*].visualClips;
the first take is not necessarily the mastered one (scene.output_path). The resolver
must prefer the library asset whose path IS scene.output_path.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.orm import Session

from app.codirector.capabilities.handlers.analyze_video import _resolve_playable_video_asset_id
from app.db import Asset, Base, Project, Scene, SessionLocal, engine


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Analyze Resolution", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=8,
            name="Scene 10",
            prompt="corridor",
            duration_sec=10.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _video_asset(db, pid: str, path: str, tag: str = "") -> Asset:
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag=tag,
        kind="video",
        filename=path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1],
        path=path,
    )
    db.add(asset)
    db.commit()
    return asset


def _director_json_with_batch_take(asset_id: str) -> str:
    return json.dumps(
        {
            "timelineMaster": {
                "batchBlocks": [
                    {"id": "bb_1", "visualClips": [{"kind": "video", "assetId": asset_id}]}
                ]
            }
        }
    )


def test_mastered_render_asset_wins_over_first_batch_take(db_scene):
    db, pid, sid = db_scene
    master_path = f"C:\\renders\\scene_8_{uuid.uuid4().hex[:6]}.mp4"
    scene = db.get(Scene, sid)
    scene.output_path = master_path
    db.commit()

    wrong_take = _video_asset(db, pid, "C:\\assets\\take_a.mp4", tag="scene_8_batch")
    mastered = _video_asset(db, pid, master_path, tag="scene_8")
    scene.director_json = _director_json_with_batch_take(wrong_take.id)
    db.commit()

    resolved = _resolve_playable_video_asset_id(db, pid, sid)
    assert resolved == mastered.id, "resolver must prefer the mastered render over the first batch take"


def test_falls_back_to_batch_take_when_no_master_asset(db_scene):
    db, pid, sid = db_scene
    scene = db.get(Scene, sid)
    scene.output_path = "C:\\renders\\not_in_library.mp4"
    db.commit()

    take = _video_asset(db, pid, "C:\\assets\\take_b.mp4", tag="scene_8_batch")
    scene.director_json = _director_json_with_batch_take(take.id)
    db.commit()

    resolved = _resolve_playable_video_asset_id(db, pid, sid)
    assert resolved == take.id, "batch take fallback must be preserved when no mastered asset exists"
