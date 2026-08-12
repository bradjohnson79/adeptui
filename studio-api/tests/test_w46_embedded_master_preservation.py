"""Regression: non-PUT/director writers must preserve the embedded W46 timelineMaster.

Audit: docs/release-gate/timeline-full-audit/TIMELINE_STATE_PERSISTENCE_AUDIT.md
Defects D1/D2 â€” assistant.apply_scene_setup, m29 editing execute_job (+undo/redo),
m29 timeline apply, and m29 audio _write_scene_clip previously persisted
scene.director_json with the plain DirectorTimeline serializer, wiping the embedded
timelineMaster; the next load_master re-migrated and collapsed multi-batch state.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline import (
    dumps_director_timeline,
    dumps_director_timeline_preserving_embedded,
    parse_director_timeline,
)


def _master_dict(batch_ids: list[str]) -> dict:
    return {
        "sceneId": "scene-x",
        "version": 1,
        "migratedFromDirectorJson": True,
        "orchestratorMode": "sequential_continuity",
        "batchBlocks": [
            {
                "id": bid,
                "sceneId": "scene-x",
                "order": i,
                "label": f"Batch {i + 1}",
                "status": "Ready",
                "duration": {"plannedDuration": 5.0},
                "promptSegments": [],
                "sourceAnchors": [],
                "references": [],
                "repairRanges": [],
                "visualClips": [],
                "audioClips": [],
                "sfxClips": [],
                "cameraInstructions": [],
                "candidateVersions": [],
            }
            for i, bid in enumerate(batch_ids)
        ],
        "executionSnapshots": {},
    }


def _blob_with_master(director: dict, batch_ids: list[str]) -> str:
    blob = dict(director)
    blob["timelineMaster"] = _master_dict(batch_ids)
    blob["timelineWorkspace"] = {"selectedBatchId": batch_ids[0]}
    return json.dumps(blob)


def _director_dict() -> dict:
    return {
        "media_mode": "image",
        "duration_sec": 10.0,
        "image_clips": [{"id": "img1", "role": "start", "start": 0, "length": 5, "asset_id": "a1"}],
        "prompt_segments": [{"id": "p1", "start": 0, "length": 5, "text": "wide shot"}],
        "camera_clips": [],
        "video_clips": [],
        "audio_clips": [],
        "sfx_clips": [],
    }


def test_preserving_embedded_keeps_master_and_workspace():
    raw = _blob_with_master(_director_dict(), ["bb_a", "bb_b"])
    tl = parse_director_timeline(raw, fallback_duration=10.0, fallback_prompt="")
    out = json.loads(dumps_director_timeline_preserving_embedded(tl, raw))
    assert out["timelineMaster"]["batchBlocks"][1]["id"] == "bb_b"
    assert out["timelineWorkspace"]["selectedBatchId"] == "bb_a"
    # DirectorTimeline fields are fully replaced by the serialized timeline
    assert out["prompt_segments"][0]["text"] == "wide shot"


def test_plain_serializer_drops_master_documents_the_defect():
    raw = _blob_with_master(_director_dict(), ["bb_a", "bb_b"])
    tl = parse_director_timeline(raw, fallback_duration=10.0, fallback_prompt="")
    out = json.loads(dumps_director_timeline(tl))
    assert "timelineMaster" not in out  # the collapse mechanism the fix avoids


@pytest.fixture()
def db_scene_with_master():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Embedded Master Cert", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="wide establishing",
            duration_sec=10.0,
            director_json=_blob_with_master(_director_dict(), ["bb_a", "bb_b"]),
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _assert_master_survives(db: Session, sid: str, pid: str) -> None:
    db.expire_all()
    scene = db.get(Scene, sid)
    blob = json.loads(scene.director_json)
    master = blob.get("timelineMaster")
    assert master is not None, "timelineMaster wiped from director_json"
    assert [b["id"] for b in master["batchBlocks"]] == ["bb_a", "bb_b"]

    # The next load_master must NOT collapse to a single re-migrated Batch 1.
    from app.director_timeline_w46 import store

    loaded = store.load_master(db, pid, sid)
    assert loaded["ok"] is True
    assert len(loaded["master"]["batchBlocks"]) == 2


def test_m29_editing_execute_job_preserves_embedded_master(db_scene_with_master):
    from app.codirector.m29.editing.service import EditingService

    db, pid, sid = db_scene_with_master
    EditingService.execute_job(
        db,
        {
            "approved": True,
            "sceneId": sid,
            "ops": [{"op": "trim", "clipId": "img1", "length": 4.0}],
        },
        pid,
    )
    db.commit()
    _assert_master_survives(db, sid, pid)


def test_m29_editing_undo_redo_preserves_embedded_master(db_scene_with_master):
    from app.codirector.m29.editing.service import EditingService

    db, pid, sid = db_scene_with_master
    EditingService.execute_job(
        db,
        {"approved": True, "sceneId": sid, "ops": [{"op": "trim", "clipId": "img1", "length": 4.0}]},
        pid,
    )
    db.commit()
    EditingService.execute_job(db, {"approved": True, "sceneId": sid, "ops": [{"op": "undo"}]}, pid)
    db.commit()
    _assert_master_survives(db, sid, pid)
    EditingService.execute_job(db, {"approved": True, "sceneId": sid, "ops": [{"op": "redo"}]}, pid)
    db.commit()
    _assert_master_survives(db, sid, pid)


def test_m29_audio_write_scene_clip_preserves_embedded_master(db_scene_with_master):
    from app.codirector.m29.audio.service import _write_scene_clip

    db, pid, sid = db_scene_with_master
    ok = _write_scene_clip(
        db,
        project_id=pid,
        scene_id=sid,
        kind="audio",
        asset_id="aud-1",
        start_sec=0.0,
        duration_sec=5.0,
        volume=1.0,
    )
    assert ok is True
    _assert_master_survives(db, sid, pid)


def test_assistant_apply_scene_setup_preserves_embedded_master(db_scene_with_master):
    from app.assistant import SceneSetupProposal, apply_scene_setup

    db, pid, sid = db_scene_with_master
    project = db.get(Project, pid)
    scene = db.get(Scene, sid)
    result = apply_scene_setup(
        project=project,
        scene=scene,
        setup=SceneSetupProposal(negative_prompt="no text"),
        assets=[],
    )
    db.commit()
    assert result.ok is True
    _assert_master_survives(db, sid, pid)

