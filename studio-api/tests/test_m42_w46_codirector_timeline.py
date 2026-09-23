"""M42 W46 Co-Director Director Timeline tools — context, mutations, revision, preflight."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.codirector.errors import CONCURRENT_MODIFICATION, CoDirectorError
from app.codirector.tools.definitions import ToolContext
from app.codirector.tools.handlers import director_timeline_tools as dt
from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import orchestrator, service, store
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    SceneTimelineMaster,
    TimelinePromptSegment,
)


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="W46 CD Timeline", description=""))
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


def _ctx(db, pid, sid) -> ToolContext:
    return ToolContext(db=db, project_id=pid, scene_id=sid)


def _seed_window(db, pid, sid, *, duration: float = 5.0) -> str:
    """Plant a one-window SceneTimelineMaster (single store). Empty scenes no
    longer auto-mint a window — CD tools require real Master batchBlocks."""
    master = SceneTimelineMaster(
        sceneId=sid,
        batchBlocks=[
            BatchBlock(
                id="bb1",
                sceneId=sid,
                order=0,
                label="Window 1",
                duration=DurationState(plannedDuration=duration, timelineVisibleDuration=duration),
                # WAVE2: no scene-level prompt inheritance — batches carry text.
                promptSegments=[
                    TimelinePromptSegment(text="wide establishing shot", start=0.0, length=duration)
                ],
            )
        ],
    )
    store.save_master(db, pid, sid, master)
    return "bb1"


def _set_generator(db, pid, sid, batch_id: str, generator_id: str) -> None:
    """Set the batch generator directly on Master. service.patch_batch routes
    generatorId changes through the creator generator-switch handoff (Systems
    P5), which is a UX gate — not what these wiring tests exercise."""
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    batch.generatorId = generator_id
    store.save_master(db, pid, sid, master)


def test_build_timeline_context(db_scene):
    db, pid, sid = db_scene
    _seed_window(db, pid, sid)
    context = dt.build_timeline_context(db, pid, sid)
    assert context["ok"] is True
    assert context["playhead"] == 0.0
    assert context["guidancePriority"] == "visual_first"
    assert context["timelineRevision"] == 1
    assert context["batchCount"] >= 1
    assert "emptyTracks" in context
    assert context["optionalRefsPolicyNote"]


def test_set_playhead_preview_and_apply(db_scene):
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    preview = dt.preview_set_playhead(ctx, {"sceneId": sid, "playhead": 2.5})
    assert "2.50" in preview.summary
    context = dt.build_timeline_context(db, pid, sid)
    result = dt.apply_set_playhead(
        ctx,
        {"sceneId": sid, "playhead": 2.5, "timelineRevision": context["timelineRevision"]},
    )
    assert result["ok"] is True
    assert result["playhead"] == 2.5
    assert result["timelineRevision"] == context["timelineRevision"] + 1
    after = dt.build_timeline_context(db, pid, sid)
    assert after["playhead"] == 2.5


def test_remove_and_restore_batch(db_scene):
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    batch_id = _seed_window(db, pid, sid)
    revision = dt.build_timeline_context(db, pid, sid)["timelineRevision"]
    removed = dt.apply_remove_item(
        ctx,
        {
            "sceneId": sid,
            "itemKind": "batchBlock",
            "itemId": batch_id,
            "timelineRevision": revision,
        },
    )
    assert removed["ok"] is True
    after_remove = dt.build_timeline_context(db, pid, sid)
    assert after_remove["batchCount"] == 0
    restored = dt.apply_restore_removed_item(
        ctx,
        {
            "sceneId": sid,
            "removedItemId": removed["removedItemId"],
            "timelineRevision": removed["timelineRevision"],
        },
    )
    assert restored["ok"] is True
    after_restore = dt.build_timeline_context(db, pid, sid)
    assert after_restore["batchCount"] >= 1


def test_revision_stale_reject(db_scene):
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    with pytest.raises(CoDirectorError) as exc:
        dt.apply_set_playhead(
            ctx,
            {"sceneId": sid, "playhead": 1.0, "timelineRevision": 999},
        )
    assert exc.value.code == CONCURRENT_MODIFICATION


def test_guidance_priority_in_execution_snapshot(db_scene):
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    batch_id = _seed_window(db, pid, sid)
    revision = dt.build_timeline_context(db, pid, sid)["timelineRevision"]
    dt.apply_set_guidance_priority(
        ctx,
        {"sceneId": sid, "guidancePriority": "prompt_first", "timelineRevision": revision},
    )
    _set_generator(db, pid, sid, batch_id, "cert-stub-local")
    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        gen = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert gen["ok"] is True
    snap = service.snapshot_get(db, pid, sid, gen["executionSnapshotId"])
    assert snap["snapshot"]["settings"]["guidancePriority"] == "prompt_first"


def test_optional_ref_preflight_non_blocking(db_scene):
    db, pid, sid = db_scene
    _seed_window(db, pid, sid)
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.references = [{"role": "wardrobe", "required": False, "optional": True}]
    store.save_master(db, pid, sid, master)
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    findings = orchestrator.run_preflight(master)
    optional = [f for f in findings if f.get("code") == "missing_optional_reference"]
    assert optional
    assert all(f["severity"] in ("warning", "info") for f in optional)
    assert not any(f.get("severity") == "error" for f in optional)


def test_preflight_read_tool(db_scene):
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)

    out = asyncio.run(dt.preflight(ctx, {"sceneId": sid}))
    assert "findings" in out
    assert out["_evidence"]["toolId"] == "timeline.preflight"


def test_camera_tools_and_focus_receipt(db_scene):
    """PHASE0_CAMERA_LANE_REMOVED: propose_add/update_camera refuse.

    Timed Prompt is sole camera authority. Do not re-enable Camera-lane writes.
    """
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    revision = dt.build_timeline_context(db, pid, sid)["timelineRevision"]
    with pytest.raises(CoDirectorError) as add_exc:
        dt.apply_propose_add_camera(
            ctx,
            {
                "sceneId": sid,
                "motionId": "dolly_in",
                "rigId": "dolly",
                "timelineRevision": revision,
            },
        )
    msg = str(add_exc.value)
    assert "Timed Prompt" in msg or "disabled" in msg.lower()
    with pytest.raises(CoDirectorError) as upd_exc:
        dt.apply_propose_update_camera(
            ctx,
            {
                "sceneId": sid,
                "cameraClipId": "nonexistent",
                "motionId": "pan",
                "rigId": "gimbal",
                "timelineRevision": revision,
            },
        )
    umsg = str(upd_exc.value)
    assert "Timed Prompt" in umsg or "disabled" in umsg.lower()
    preview = dt.preview_propose_add_camera(ctx, {"sceneId": sid, "motionId": "dolly_in"})
    blob = " ".join([preview.summary or "", *list(preview.lines or [])])
    assert "Timed Prompt" in blob
    assert "Do not add a Camera clip" in blob or "no longer a creator surface" in blob


def test_layout_inspect_and_proposals(db_scene):
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    initial = asyncio.run(dt.inspect_layout(ctx, {"sceneId": sid}))
    assert initial["viewerPreset"] == "large"
    assert initial["trackDensity"] == "compact"
    revision = dt.build_timeline_context(db, pid, sid)["timelineRevision"]
    preset = dt.apply_propose_layout_preset(
        ctx,
        {"sceneId": sid, "preset": "balanced", "timelineRevision": revision},
    )
    assert preset["viewerPreset"] == "balanced"
    zoomed = dt.apply_propose_zoom(
        ctx,
        {"sceneId": sid, "delta": 0.5, "timelineRevision": preset["timelineRevision"]},
    )
    assert zoomed["zoom"] == 1.5
    reset = dt.apply_propose_layout_reset(
        ctx,
        {"sceneId": sid, "timelineRevision": zoomed["timelineRevision"]},
    )
    assert reset["viewerPreset"] == "large"
    assert reset["zoom"] == 1.0


def test_lipsync_inspect_owner_law_empty_default(db_scene):
    """OWNER LAW (TIMELINE_LIPSYNC_CREATOR_UI=false): never mint Lip Sync 1.

    Default state is zero tracks. The CD lipsync mutation chain is deferred —
    see test_lipsync_mutation_chain_deferred."""
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    inspect = asyncio.run(dt.inspect_lipsync(ctx, {"sceneId": sid}))
    assert inspect["trackCount"] == 0
    assert inspect["protectedTrackId"] is None


@pytest.mark.skip(
    reason="DEFERRED LEFTOVER: CD lipsync tools mutate director_tl.lipsync, which "
    "save_master (Master + workspace only) does not persist — a dead write. The "
    "creator Lip Sync surface is owner-forbidden/dormant, so the chain is parked "
    "until lipsync persistence is repaired against scene.lipsync_tracks_json. "
    "Tracked in reports/CLEAR_REMAINING_TIMELINE_CD_DUAL_STACK.md."
)
def test_lipsync_mutation_chain_deferred(db_scene):
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    inspect = asyncio.run(dt.inspect_lipsync(ctx, {"sceneId": sid}))
    assert inspect["trackCount"] == 1
    revision = dt.build_timeline_context(db, pid, sid)["timelineRevision"]
    added_track = dt.apply_propose_add_lipsync_track(
        ctx,
        {"sceneId": sid, "timelineRevision": revision},
    )
    added_clip = dt.apply_propose_add_lipsync_clip(
        ctx,
        {
            "sceneId": sid,
            "trackId": added_track["trackId"],
            "timelineRevision": added_track["timelineRevision"],
        },
    )
    validate_before = asyncio.run(dt.validate_lipsync(ctx, {"sceneId": sid}))
    assert validate_before["blockingCount"] >= 1
    bound = dt.apply_propose_bind_lipsync_clip(
        ctx,
        {
            "sceneId": sid,
            "clipId": added_clip["clipId"],
            "characterId": "char_001",
            "audioAssetId": "audio_001",
            "followPolicy": "manual",
            "timelineRevision": added_clip["timelineRevision"],
        },
    )
    validate_after = asyncio.run(dt.validate_lipsync(ctx, {"sceneId": sid}))
    assert validate_after["blockingCount"] == 0
    with pytest.raises(CoDirectorError):
        dt.apply_propose_remove_lipsync_track(
            ctx,
            {
                "sceneId": sid,
                "trackId": inspect["protectedTrackId"],
                "timelineRevision": bound["timelineRevision"],
            },
        )
    removed = dt.apply_propose_remove_lipsync_track(
        ctx,
        {
            "sceneId": sid,
            "trackId": added_track["trackId"],
            "timelineRevision": bound["timelineRevision"],
        },
    )
    assert removed["removedTrackId"] == added_track["trackId"]


def test_inpaint_mask_execute_approve_and_restore(db_scene):
    db, pid, sid = db_scene
    ctx = _ctx(db, pid, sid)
    batch_id = _seed_window(db, pid, sid)
    _set_generator(db, pid, sid, batch_id, "cert-stub-local")

    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        initial_job = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert initial_job["ok"] is True
    initial_complete = orchestrator.complete_batch_candidate(
        db,
        pid,
        sid,
        batch_id,
        asset_id="asset_prior",
        generated_duration=5.0,
        execution_snapshot_id=initial_job["executionSnapshotId"],
    )
    prior_candidate_id = initial_complete["candidate"]["id"]
    orchestrator.approve_candidate(db, pid, sid, batch_id, prior_candidate_id)

    revision = dt.build_timeline_context(db, pid, sid)["timelineRevision"]
    created = dt.apply_propose_create_inpaint_mask(
        ctx,
        {
            "sceneId": sid,
            "batchBlockId": batch_id,
            "start": 0.0,
            "length": 1.0,
            "prompt": "Repair the eyes and preserve the original blocking.",
            "maskType": "include",
            "activeTool": "brush",
            "maskRevision": 1,
            "maskStrokesJson": '[{"id":"stroke-1","tool":"brush","at":0.0,"x":0.4,"y":0.5}]',
            "requestedStrategy": "native",
            "timelineRevision": revision,
        },
    )
    assert created["resolvedStrategy"] == "range_replacement"

    executed = dt.apply_propose_execute_inpaint(
        ctx,
        {
            "sceneId": sid,
            "batchBlockId": batch_id,
            "repairId": created["repairId"],
            "timelineRevision": created["timelineRevision"],
        },
    )
    followup_complete = orchestrator.complete_batch_candidate(
        db,
        pid,
        sid,
        batch_id,
        asset_id="asset_inpaint",
        generated_duration=5.0,
        execution_snapshot_id=executed["executionSnapshotId"],
    )
    inpaint_candidate_id = followup_complete["candidate"]["id"]

    approved = dt.apply_propose_approve_inpaint(
        ctx,
        {
            "sceneId": sid,
            "batchBlockId": batch_id,
            "repairId": created["repairId"],
            "candidateId": inpaint_candidate_id,
            "timelineRevision": executed["timelineRevision"],
        },
    )
    restored = dt.apply_propose_restore_inpaint(
        ctx,
        {
            "sceneId": sid,
            "batchBlockId": batch_id,
            "repairId": created["repairId"],
            "timelineRevision": approved["timelineRevision"],
        },
    )
    assert restored["approvedClip"]["candidateId"] == prior_candidate_id
    bundle = service.load_timeline_bundle(db, pid, sid)
    batch = next(item for item in bundle["master"].batchBlocks if item.id == batch_id)
    repair = next(item for item in batch.repairRanges if item.id == created["repairId"])
    assert repair.status == "restored"
