"""Stale browser director_json must never overwrite newer timelineMaster."""

from __future__ import annotations

import json
import uuid

from app.db import Project, Scene, SessionLocal, init_db
from app.director_timeline_w46.store import patch_scene_metadata
from app.services.scene_service import SceneService


def _db():
    init_db()
    return SessionLocal()


def test_scene_update_strips_wholesale_director_json():
    db = _db()
    try:
        pid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        master = {"schemaVersion": 1, "sceneId": sid, "batchBlocks": [{"id": "bb_keep", "order": 0}]}
        db.add(Project(id=pid, name="Meta", description=""))
        db.add(
            Scene(
                id=sid,
                project_id=pid,
                index=0,
                name="S",
                prompt="p",
                duration_sec=15.0,
                director_json=json.dumps({"timelineMaster": master, "promptIntelligence": {}}),
            )
        )
        db.commit()
        SceneService.update(
            db,
            pid,
            sid,
            {"prompt": "new", "director_json": json.dumps({"timelineMaster": {"wiped": True}})},
        )
        row = db.get(Scene, sid)
        blob = json.loads(row.director_json)
        assert blob["timelineMaster"]["batchBlocks"][0]["id"] == "bb_keep"
        assert row.prompt == "new"
    finally:
        db.close()


def test_prompt_intelligence_merge_preserves_newer_master():
    db = _db()
    try:
        pid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        db.add(Project(id=pid, name="Meta", description=""))
        stale = {"timelineMaster": {"schemaVersion": 1, "sceneId": sid, "batchBlocks": [{"id": "bb_old", "order": 0}]}}
        newer = {
            "timelineMaster": {
                "schemaVersion": 1,
                "sceneId": sid,
                "batchBlocks": [{"id": "bb_new", "order": 0, "promptSegments": [{"id": "ps_1", "start": 0, "length": 2, "text": "live"}]}],
            }
        }
        db.add(
            Scene(
                id=sid,
                project_id=pid,
                index=0,
                name="S",
                prompt="p",
                duration_sec=15.0,
                director_json=json.dumps(stale),
            )
        )
        db.commit()
        row = db.get(Scene, sid)
        row.director_json = json.dumps(newer)
        db.commit()
        before = json.loads(db.get(Scene, sid).director_json)["timelineMaster"]
        result = patch_scene_metadata(db, pid, sid, {"promptIntelligence": {"engineId": "test"}})
        assert result["ok"] is True
        after = json.loads(db.get(Scene, sid).director_json)
        assert json.dumps(after["timelineMaster"], sort_keys=True) == json.dumps(before, sort_keys=True)
        assert after["promptIntelligence"]["engineId"] == "test"
        blocked = patch_scene_metadata(db, pid, sid, {"timelineMaster": {"wiped": True}})
        assert blocked["ok"] is False
    finally:
        db.close()
