"""Single-store remainder regression tests — live-cert Defects 1-4 (2026-09-20).

Defect 1 (FE): Timed Prompt modal edits persist to Master — FE vitest covers
    (masterTimelineMutate.test.ts). Backend coverage here is the patchBatch
    round-trip the modal relies on.
Defect 2 (FE): clip removal persists via syncMasterClips — FE vitest covers.
Defect 3: Co-Director add-prompt duration fence reads SceneTimelineMaster
    window durations, never the frozen legacy director_json duration_sec.
Defect 4: generation/readiness paths read Master clip/prompt arrays as SoT
    (visual_range / orchestrator preflight / completion / _scene_director_dict).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.orm import Session

from app.codirector.errors import CoDirectorError
from app.codirector.tools.definitions import ToolContext
from app.codirector.tools.handlers import director_timeline_tools as dt
from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import store
from app.director_timeline_w46.contracts import (
    ApprovedClip,
    BatchBlock,
    BatchClip,
    DurationState,
    SceneTake,
    SceneTakeBatchMember,
    SceneTimelineMaster,
    TimelinePromptSegment,
)


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Single Store Remainder", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="wide establishing",
            duration_sec=45.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _ctx(db, pid, sid) -> ToolContext:
    return ToolContext(db=db, project_id=pid, scene_id=sid)


def _master_45(scene_id: str) -> SceneTimelineMaster:
    """3 windows: b1 0-10, b2 10-25, b3 25-45 (mirrors disposable cert scene)."""
    return SceneTimelineMaster(
        sceneId=scene_id,
        sceneGeneratorId="minimax-h3",
        batchBlocks=[
            BatchBlock(
                id="bb1",
                sceneId=scene_id,
                order=0,
                label="Window 1",
                duration=DurationState(plannedDuration=10),
            ),
            BatchBlock(
                id="bb2",
                sceneId=scene_id,
                order=1,
                label="Window 2",
                duration=DurationState(plannedDuration=15),
            ),
            BatchBlock(
                id="bb3",
                sceneId=scene_id,
                order=2,
                label="Window 3",
                duration=DurationState(plannedDuration=20),
            ),
        ],
    )


def _plant_master_with_stale_legacy(db: Session, pid: str, sid: str) -> SceneTimelineMaster:
    """Save the 45s Master, then poison the leftover legacy keys (COW audit
    leftovers) with a frozen 5s duration — the pre-fix fence authority."""
    master = _master_45(sid)
    store.save_master(db, pid, sid, master)
    scene = store.get_scene(db, pid, sid)
    blob = json.loads(scene.director_json)
    # Legacy COW leftovers: frozen 5s duration + stale clip arrays that must
    # never be read as authority after migration.
    blob["duration_sec"] = 5.0
    blob["prompt_segments"] = [{"id": "legacy_ps", "start": 0, "length": 5, "text": "STALE LEGACY"}]
    blob["video_clips"] = [{"id": "legacy_vc", "start": 0, "length": 5, "asset_id": "stale"}]
    blob["camera_clips"] = [{"id": "legacy_cc", "start": 0, "length": 5, "motion_type": "custom"}]
    scene.director_json = json.dumps(blob)
    db.commit()
    return master


# ---------------------------------------------------------------- Defect 3


def test_add_prompt_fence_reads_master_duration_not_legacy_frozen(db_scene):
    """45s Master scene + frozen 5s legacy duration: add-prompt at 30s must
    succeed on the deterministic path with verified:true (pre-fix: fenced at 5s)."""
    db, pid, sid = db_scene
    _plant_master_with_stale_legacy(db, pid, sid)
    ctx = _ctx(db, pid, sid)

    result = dt.apply_propose_add_prompt_segment(
        ctx,
        {
            "sceneId": sid,
            "text": "Korri crosses the bar as the lights flicker.",
            "start": 30.0,
            "length": 10.0,
        },
    )
    assert result["ok"] is True
    assert result["verified"] is True

    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    b3 = next(b for b in master.batchBlocks if b.id == "bb3")
    texts = [s.text for s in b3.promptSegments]
    assert any("Korri crosses the bar" in t for t in texts)
    # Zero legacy write: the poisoned legacy prompt_segments stay untouched.
    scene = store.get_scene(db, pid, sid)
    blob = json.loads(scene.director_json)
    assert blob["prompt_segments"] == [{"id": "legacy_ps", "start": 0, "length": 5, "text": "STALE LEGACY"}]


def test_add_prompt_fence_still_refuses_beyond_master_duration(db_scene):
    """The fence still bites — against the real 45s Master duration."""
    db, pid, sid = db_scene
    _plant_master_with_stale_legacy(db, pid, sid)
    ctx = _ctx(db, pid, sid)

    with pytest.raises(CoDirectorError):
        dt.apply_propose_add_prompt_segment(
            ctx,
            {
                "sceneId": sid,
                "text": "This prompt requests coverage past the end of the scene.",
                "start": 40.0,
                "length": 10.0,  # 50s > 45s Master duration
            },
        )


def test_get_playhead_reports_master_duration(db_scene):
    import asyncio

    db, pid, sid = db_scene
    _plant_master_with_stale_legacy(db, pid, sid)
    ctx = _ctx(db, pid, sid)
    out = asyncio.run(dt.get_playhead(ctx, {"sceneId": sid}))
    assert abs(float(out["durationSec"]) - 45.0) < 1e-6


# ---------------------------------------------------------------- Defect 4


def test_scene_director_dict_reads_master_not_legacy_blob(db_scene):
    """Chat context summary derives from embedded Master, never legacy keys."""
    from app.codirector.service import _scene_director_dict

    db, pid, sid = db_scene
    master = _master_45(sid)
    master.batchBlocks[0].promptSegments = [
        TimelinePromptSegment(text="Master prompt one", start=0, length=5),
        TimelinePromptSegment(text="Master prompt two", start=5, length=5),
    ]
    master.batchBlocks[1].audioClips = [
        BatchClip(kind="audio", assetId="aud1", start=0, length=10, label="Bar ambience")
    ]
    store.save_master(db, pid, sid, master)
    scene = store.get_scene(db, pid, sid)
    blob = json.loads(scene.director_json)
    blob["duration_sec"] = 5.0
    blob["prompt_segments"] = [{"id": "legacy_ps", "start": 0, "length": 5, "text": "STALE"}] * 9
    blob["video_clips"] = [{"id": "legacy_vc"}] * 7
    scene.director_json = json.dumps(blob)
    db.commit()

    scene = store.get_scene(db, pid, sid)
    summary = _scene_director_dict(scene)
    assert abs(float(summary["duration_sec"]) - 45.0) < 1e-6
    assert len(summary["prompt_segments"]) == 2  # Master count, not legacy 9
    assert len(summary["audio_clips"]) == 1


def test_preflight_camera_reads_master_camera_instructions(db_scene):
    """run_preflight camera findings come from Master batch.cameraInstructions;
    legacy director_json camera_clips are never readiness authority."""
    from app.director_timeline_w46.orchestrator import run_preflight

    db, pid, sid = db_scene
    master = _master_45(sid)
    # Master camera instruction with a real contradiction (custom motion, no label).
    master.batchBlocks[0].cameraInstructions = [
        BatchClip(kind="camera", start=0, length=5, motion_type="custom", label="Cam")
    ]
    store.save_master(db, pid, sid, master)
    scene = store.get_scene(db, pid, sid)
    blob = json.loads(scene.director_json)
    scene.director_json = json.dumps(blob)
    db.commit()

    payload = store.load_master(db, pid, sid)
    reloaded = SceneTimelineMaster.model_validate(payload["master"])
    findings = run_preflight(reloaded)
    codes = [f["code"] for f in findings]
    assert "camera_custom_motion_missing_label" in codes

    # Legacy-only camera clips (Master cameraInstructions empty) → no camera findings.
    master2 = _master_45(sid)
    store.save_master(db, pid, sid, master2)
    scene = store.get_scene(db, pid, sid)
    blob = json.loads(scene.director_json)
    blob["camera_clips"] = [{"id": "legacy_cc", "start": 0, "length": 5, "motion_type": "custom"}]
    scene.director_json = json.dumps(blob)
    db.commit()
    payload = store.load_master(db, pid, sid)
    reloaded2 = SceneTimelineMaster.model_validate(payload["master"])
    findings2 = run_preflight(reloaded2)
    assert "camera_custom_motion_missing_label" not in [f["code"] for f in findings2]


def test_place_approved_batches_writes_master_visual_clips(db_scene):
    """completion.place_approved_batches_on_timeline upserts the managed
    bbvclip_ take into Master batch.visualClips at batch-local start 0."""
    from app.director_timeline_w46.generation.completion import place_approved_batches_on_timeline

    db, pid, sid = db_scene
    master = _master_45(sid)
    master.batchBlocks[1].approvedClip = ApprovedClip(
        assetId="take_asset_b2",
        executionSnapshotId="snap_b2",
        playable=True,
    )
    master.batchBlocks[1].status = "Approved"
    store.save_master(db, pid, sid, master)

    result = place_approved_batches_on_timeline(db, pid, sid)
    assert result.get("ok") is not False

    payload = store.load_master(db, pid, sid)
    reloaded = SceneTimelineMaster.model_validate(payload["master"])
    b2 = next(b for b in reloaded.batchBlocks if b.id == "bb2")
    managed = [c for c in b2.visualClips if c.id == "bbvclip_bb2"]
    assert managed, "managed bbvclip_ take must exist in Master visualClips"
    assert managed[0].assetId == "take_asset_b2"
    assert abs(float(managed[0].start) - 0.0) < 1e-6  # batch-local

    # Zero legacy write: no video_clips key appeared in director_json.
    scene = store.get_scene(db, pid, sid)
    blob = json.loads(scene.director_json)
    legacy = blob.get("video_clips") or []
    assert all("take_asset_b2" not in json.dumps(c) for c in legacy)


def test_place_approved_skips_a_video_the_creator_removed(db_scene):
    """Removing a Visual video keeps that asset off the lane until a new one exists."""
    from app.director_timeline_w46.generation.completion import place_approved_batches_on_timeline

    db, pid, sid = db_scene
    master = _master_45(sid)
    master.batchBlocks[1].approvedClip = ApprovedClip(
        assetId="take_asset_b2",
        executionSnapshotId="snap_b2",
        playable=True,
    )
    master.batchBlocks[1].dismissedVisualAssetId = "take_asset_b2"
    master.batchBlocks[1].status = "Approved"
    store.save_master(db, pid, sid, master)

    place_approved_batches_on_timeline(db, pid, sid)
    payload = store.load_master(db, pid, sid)
    reloaded = SceneTimelineMaster.model_validate(payload["master"])
    b2 = next(b for b in reloaded.batchBlocks if b.id == "bb2")
    assert b2.dismissedVisualAssetId == "take_asset_b2"
    assert all(c.id != "bbvclip_bb2" for c in b2.visualClips)

    b2.approvedClip = ApprovedClip(
        assetId="take_asset_b2_new",
        executionSnapshotId="snap_b2b",
        playable=True,
    )
    store.save_master(db, pid, sid, reloaded)
    place_approved_batches_on_timeline(db, pid, sid)
    payload = store.load_master(db, pid, sid)
    again = SceneTimelineMaster.model_validate(payload["master"])
    b2b = next(b for b in again.batchBlocks if b.id == "bb2")
    assert b2b.dismissedVisualAssetId in (None, "")
    placed = [c for c in b2b.visualClips if c.id == "bbvclip_bb2"]
    assert placed and placed[0].assetId == "take_asset_b2_new"


def test_rendering_take_places_its_own_clip_and_clears_the_previous_bar(db_scene):
    """The take being rendered owns Visual. A window it has not finished yet
    does not keep the previous take's video."""
    from app.director_timeline_w46.generation.completion import place_approved_batches_on_timeline

    db, pid, sid = db_scene
    master = _master_45(sid)
    master.batchBlocks[0].visualClips = [
        BatchClip(id="bbvclip_bb1", kind="video", assetId="old-1", start=0, length=10, role="take")
    ]
    master.batchBlocks[1].visualClips = [
        BatchClip(id="bbvclip_bb2", kind="video", assetId="old-2", start=0, length=15, role="take")
    ]
    current = SceneTake(
        id="stk_old",
        label="A",
        letterIndex=1,
        status="incomplete",
        batches=[
            SceneTakeBatchMember(batchId="bb1", order=0, assetId="old-1"),
            SceneTakeBatchMember(batchId="bb2", order=1, assetId="old-2"),
        ],
    )
    rendering = SceneTake(
        id="stk_new",
        label="B",
        letterIndex=2,
        status="rendering",
        batches=[
            SceneTakeBatchMember(batchId="bb1", order=0, assetId="new-1"),
            SceneTakeBatchMember(batchId="bb2", order=1, assetId=None),
        ],
    )
    master.sceneTakes = [current, rendering]
    master.currentSceneTakeId = current.id
    master.activeSceneTakeId = rendering.id
    store.save_master(db, pid, sid, master)

    place_approved_batches_on_timeline(db, pid, sid)
    payload = store.load_master(db, pid, sid)
    reloaded = SceneTimelineMaster.model_validate(payload["master"])
    w1 = next(b for b in reloaded.batchBlocks if b.id == "bb1")
    w2 = next(b for b in reloaded.batchBlocks if b.id == "bb2")
    assert [c.assetId for c in w1.visualClips if c.id == "bbvclip_bb1"] == ["new-1"]
    assert all(c.id != "bbvclip_bb2" for c in w2.visualClips)


def test_append_master_clip_stores_batch_local_start():
    """BATCH-LOCAL COORDINATE LAW: CD tool payloads arrive scene-absolute;
    Master stores batch-local (window 25-45, payload start=30 → stored 5)."""
    master = _master_45("s1")
    clip = BatchClip(kind="image", assetId="a1", start=30.0, length=4, label="Still")
    target = dt._append_master_clip(master, clip, 30.0, "visualClips")
    assert target.id == "bb3"
    stored = master.batchBlocks[2].visualClips[-1]
    assert abs(float(stored.start) - 5.0) < 1e-6


def test_adopt_legacy_retakes_scans_master_visual_clips():
    """scene_takes.adopt_legacy_retakes reads Master visualClips metadata,
    never the retired legacy video_clips array."""
    from app.director_timeline_w46.contracts import SceneTake
    from app.director_timeline_w46.scene_takes import adopt_legacy_retakes

    master = _master_45("s1")
    master.batchBlocks[0].visualClips = [
        BatchClip(
            id="rtclip_1",
            kind="video",
            assetId="retake_asset",
            start=2,
            length=3,
            metadata={"retakeId": "rt_1", "role": "retake", "sourceBatchId": "bb1"},
        )
    ]
    master.sceneTakes = [SceneTake(letterIndex=1, label="Take A")]
    changed = adopt_legacy_retakes(master)
    assert changed is True
    assert "rt_1" in (master.sceneTakes[0].retakeIds or [])
