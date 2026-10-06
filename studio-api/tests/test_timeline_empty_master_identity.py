"""Empty-master reads must keep one window id, and the Library tray must persist."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import store


def _empty_scene(
    *, scene_generator_id: str | None = "minimax-h3", engine_id: str = "minimax-h3"
) -> tuple[Session, str, str]:
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    db.add(Project(id=pid, name="Empty Master Identity"))
    master = {
        "version": 1,
        "mode": "image_planning",
        "sceneGeneratorId": scene_generator_id,
        "migratedFromDirectorJson": True,
        "migration": {"completedAt": "2026-09-22T00:00:00+00:00", "version": 1, "source": "director_json"},
        "migrationNote": "Empty master: no Batch 1 mint; awaits CD rematerialize / SceneTake.",
        "batchBlocks": [],
        "executionSnapshots": {},
    }
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="",
            engine=engine_id,
            duration_sec=15.0,
            director_json=json.dumps({"timelineMaster": master, "timelineWorkspace": {"playhead": 0}}),
        )
    )
    db.commit()
    return db, pid, sid


def test_empty_master_bootstrap_persists_one_window_id():
    db, pid, sid = _empty_scene()
    try:
        first = store.load_master(db, pid, sid)
        second = store.load_master(db, pid, sid)
        assert first["ok"] is True
        blocks_a = first["master"]["batchBlocks"]
        blocks_b = second["master"]["batchBlocks"]
        assert len(blocks_a) == 1
        assert blocks_a[0]["id"] == blocks_b[0]["id"]
        seg_a = blocks_a[0]["promptSegments"][0]["id"]
        seg_b = blocks_b[0]["promptSegments"][0]["id"]
        assert seg_a == seg_b
        disk = json.loads(db.query(Scene).filter(Scene.id == sid).one().director_json)
        assert disk["timelineMaster"]["batchBlocks"][0]["id"] == blocks_a[0]["id"]
    finally:
        db.close()


def test_empty_master_bootstraps_from_scene_engine_when_generator_null():
    """New scenes store engine on Scene but leave master.sceneGeneratorId null.

    Timed Prompt / Visual writers need a window; GET /master must bootstrap from
    Scene.engine + duration without minting creator Batch CRUD.
    """
    db, pid, sid = _empty_scene(scene_generator_id=None, engine_id="minimax-h3")
    try:
        first = store.load_master(db, pid, sid)
        assert first["ok"] is True
        master = first["master"]
        assert master.get("sceneGeneratorId") == "minimax-h3"
        blocks = master.get("batchBlocks") or []
        assert len(blocks) == 1
        assert blocks[0].get("promptSegments")
        # Visual + Timed Prompt writers need a real window span.
        assert float((blocks[0].get("duration") or {}).get("plannedDuration") or 0) > 0

        second = store.load_master(db, pid, sid)
        assert second["master"]["batchBlocks"][0]["id"] == blocks[0]["id"]
        disk = json.loads(db.query(Scene).filter(Scene.id == sid).one().director_json)
        assert disk["timelineMaster"]["sceneGeneratorId"] == "minimax-h3"
        assert len(disk["timelineMaster"]["batchBlocks"]) == 1

        # Same hop the locked syncMasterClips / patchMasterPrompt writers use.
        from app.director_timeline_w46 import orchestrator

        batch_id = blocks[0]["id"]
        patched = orchestrator.touch_batch_config(
            db,
            pid,
            sid,
            batch_id,
            {
                "visualClips": [
                    {
                        "id": "clip_visual_writer",
                        "kind": "image",
                        "start": 0.0,
                        "length": 2.0,
                        "label": "Image 1",
                        "assetId": "asset-image-1",
                        "role": "guide",
                    }
                ],
                "promptSegments": [
                    {
                        **(blocks[0]["promptSegments"][0]),
                        "text": "hello timed prompt",
                    }
                ],
            },
        )
        assert patched.get("ok") is True
        reloaded = store.load_master(db, pid, sid)
        row = reloaded["master"]["batchBlocks"][0]
        assert len(row.get("visualClips") or []) == 1
        assert row["visualClips"][0]["assetId"] == "asset-image-1"
        assert "hello timed prompt" in str(row["promptSegments"][0].get("text") or "")
    finally:
        db.close()


def test_later_window_continuation_start_is_scene_time():
    """A continuation stored at 0 on window 2 must move to that window's start."""
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    db.add(Project(id=pid, name="Continuation Start"))
    master = {
        "version": 1,
        "mode": "image_planning",
        "sceneGeneratorId": "minimax-h3",
        "batchBlocks": [
            {
                "id": "bb_root",
                "sceneId": sid,
                "order": 0,
                "label": "Window 1",
                "generatorId": "minimax-h3",
                "duration": {"plannedDuration": 15.0, "timelineVisibleDuration": 15.0},
                "promptSegments": [
                    {"id": "ps_root", "start": 0.0, "length": 30.0, "text": "Opening line."}
                ],
            },
            {
                "id": "bb_ext",
                "sceneId": sid,
                "order": 1,
                "label": "Window 2",
                "generatorId": "minimax-h3",
                "duration": {"plannedDuration": 15.0, "timelineVisibleDuration": 15.0},
                "promptSegments": [
                    {
                        "id": "ps_ext",
                        "start": 0.0,
                        "length": 15.0,
                        "text": "[CONTINUATION window 2 | scene time 15s-30s] Continue from the prior window.",
                    }
                ],
            },
        ],
        "executionSnapshots": {},
    }
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="",
            engine="minimax-h3",
            duration_sec=30.0,
            director_json=json.dumps({"timelineMaster": master}),
        )
    )
    db.commit()
    try:
        loaded = store.load_master(db, pid, sid)
        blocks = loaded["master"]["batchBlocks"]
        ext = next(b for b in blocks if b["id"] == "bb_ext")
        assert float(ext["promptSegments"][0]["start"]) >= 14.95
        root = next(b for b in blocks if b["id"] == "bb_root")
        assert float(root["promptSegments"][0]["start"]) <= 0.05
        assert "Opening line." in root["promptSegments"][0]["text"]
        again = store.load_master(db, pid, sid)
        ext2 = next(b for b in again["master"]["batchBlocks"] if b["id"] == "bb_ext")
        assert float(ext2["promptSegments"][0]["start"]) < 16.0
    finally:
        db.close()


def test_new_scene_script_stays_on_window_one_and_ending_on_the_last():
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    script = "\n\n".join(
        [
            "Opening. The host lifts the thermos at the bar.",
            "The camera pans to the guest reading a menu.",
            "The host returns and sets the thermos down.",
            "Ending. The beans splash the lens and the scene cuts to black.",
        ]
    )
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    db.add(Project(id=pid, name="Script Split"))
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
            index=0,
            name="Scene",
            prompt=script,
            engine="minimax-h3",
            duration_sec=60.0,
            director_json=json.dumps({"timelineMaster": master}),
        )
    )
    db.commit()
    try:
        loaded = store.load_master(db, pid, sid)
        blocks = loaded["master"]["batchBlocks"]
        assert len(blocks) == 4
        root_text = blocks[0]["promptSegments"][0]["text"]
        last_text = blocks[-1]["promptSegments"][0]["text"]
        assert "Opening." in root_text
        assert "cuts to black" not in root_text
        assert "cuts to black" in last_text
        assert "Opening." not in last_text
        assert float(blocks[-1]["promptSegments"][0]["start"]) >= 44.95
    finally:
        db.close()


def test_library_asset_ids_survive_on_workspace():
    db, pid, sid = _empty_scene()
    try:
        saved = store.set_library_asset_ids(db, pid, sid, ["img-a", "img-b"])
        assert saved["ok"] is True
        assert saved["libraryAssetIds"] == ["img-a", "img-b"]
        loaded = store.load_master(db, pid, sid)
        disk = json.loads(db.query(Scene).filter(Scene.id == sid).one().director_json)
        assert disk["timelineWorkspace"]["libraryAssetIds"] == ["img-a", "img-b"]
        assert loaded["master"]["batchBlocks"][0]["id"]
    finally:
        db.close()
