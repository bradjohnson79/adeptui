"""Retake / Timeline R2V gate repair — H3 is R2V, not T2V-via-I2V-false."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db import Asset, Base, Project, Scene, SessionLocal, engine
from app.director_timeline import TimelineClip, parse_director_timeline
from app.director_timeline_w46 import orchestrator, service, store
from app.director_timeline_w46.contracts import (
    ApprovedClip,
    BatchBlock,
    CandidateVersion,
    DurationState,
    ExecutionSnapshot,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.adapters.minimax_h3_local import MiniMaxH3LocalAdapter
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.generation.retake_context_package import build_retake_context_package
from app.director_timeline_w46.visual_range import place_visual_image_range
from app.production_control.generator_authority import _capability_from_row


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Retake R2V Gates", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="corridor walk",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _seed_active_take(db, pid, sid, *, asset_id="asset-orig", length=5.0, generator_id="minimax-h3-t2v-local"):
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.generatorId = generator_id
    master.sceneGeneratorId = generator_id
    batch.approvedClip = ApprovedClip(assetId=asset_id, executionSnapshotId="snap-a")
    batch.candidateVersions = [
        CandidateVersion(
            executionSnapshotId="snap-a",
            assetId=asset_id,
            label="Take A",
            takeId="take_a",
        )
    ]
    batch.status = "CandidateReady"
    batch.duration.plannedDuration = length
    batch.duration.timelineVisibleDuration = length
    scene = store.get_scene(db, pid, sid)
    director_tl = parse_director_timeline(scene.director_json, fallback_duration=length)
    director_tl.video_clips = [
        TimelineClip(
            id=f"bbclip_{batch_id}",
            asset_id=asset_id,
            start=0.0,
            length=length,
            trim_start=0.0,
            label="Take",
            media_type="video",
        )
    ]
    director_tl.media_mode = "video"
    director_tl.duration_sec = length
    store.save_master(db, pid, sid, master, director_tl=director_tl, bump_revision=True)
    return batch_id


def _seed_image_asset(db, pid, asset_id=None):
    aid = asset_id or f"img-{uuid.uuid4().hex[:8]}"
    db.add(
        Asset(
            id=aid,
            project_id=pid,
            tag="frame",
            kind="image",
            filename="frame.png",
            path="missing-ok-for-kind-check.png",
        )
    )
    db.commit()
    return aid


def test_h3_adapter_caps_remain_r2v_not_i2v_or_t2v():
    caps = MiniMaxH3LocalAdapter.capabilities
    assert caps.supportsReferenceToVideo is True
    assert caps.supportsImageToVideo is False
    assert caps.supportsTextToVideo is False


def test_timeline_capability_exposes_r2v_and_blocks_create_t2v_leak():
    adapter_caps = SimpleNamespace(
        supportsImageToVideo=False,
        supportsReferenceToVideo=True,
        supportsTextToVideo=False,
        supportsStartFrame=False,
        supportsPromptContinuation=False,
        audio_generation=True,
        notes="Timeline R2V",
        maxDurationSec=15.0,
        supportedDurations=[],
        draftPathway="local_live",
        supportsQueuedCancel=True,
        supportsRunningCancel=True,
        supportsLivePreview=False,
        supportsHonestProgress=False,
        supportsIntermediateFrames=False,
        remoteCancelCostNote=None,
        finalRequiresNewGeneration=True,
        draftResolution=None,
        finalResolution="1152x640",
        supportsVideoReferences=False,
        supportsImageAndVideoTogether=False,
        maximumReferenceVideos=0,
        supportedAspectRatios=["16:9"],
        id="minimax-h3-t2v-local",
        requiresLastFrame=False,
    )
    row = {
        "id": "minimax-h3",
        "label": "MiniMax H3",
        "locality": "local",
        "executable": True,
        "timelineAdapterId": "minimax-h3-t2v-local",
        "supportsTimelineGeneration": True,
        # CREATE surface may advertise t2v — must NOT leak onto Timeline flag
        "workflowCapabilities": {"t2v": {"supported": True}},
        "readiness": "Ready",
        "disabledReason": "",
    }
    gen = _capability_from_row(row, adapter_caps)
    assert gen.supportsReferenceToVideo is True
    assert gen.supportsImageToVideo is False
    assert gen.supportsTextToVideo is False
    assert (gen.workflowCapabilities or {}).get("t2v", {}).get("supported") is True


def test_retake_range_h3_image_frame_allowed_as_r2v(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    img = _seed_image_asset(db, pid)
    assert (
        place_visual_image_range(
            db,
            pid,
            sid,
            mark_in=1.0,
            mark_out=2.0,
            image_asset_id=img,
            placement_id="h3r2v",
            source_batch_id=batch_id,
            source_asset_id="asset-orig",
        )["ok"]
        is True
    )

    class _Caps:
        supportsImageToVideo = False
        supportsReferenceToVideo = True

    class _Adapter:
        capabilities = _Caps()

    class _Gen:
        label = "MiniMax H3 (Local)"
        locality = "local"
        executable = True
        supportsImageToVideo = False
        supportsReferenceToVideo = True
        supportsTextToVideo = False
        inPaintStrategies = ["complete_batch_retake", "range_replacement"]
        disabledReason = None
        readiness = "Ready"

    captured = {}

    def _fake_submit(db, project_id, scene_id, bid, continuity=None, **kwargs):
        captured["batch_id"] = bid
        captured["continuity"] = continuity
        return {
            "ok": True,
            "queueJobId": "q-h3",
            "internalJobId": "i-h3",
            "generatorId": "minimax-h3-t2v-local",
        }

    with patch.object(orchestrator, "get_generator", return_value=_Gen()), patch(
        "app.director_timeline_w46.generation.registry.get_registry"
    ) as reg, patch.object(
        orchestrator, "submit_batch_generation", side_effect=_fake_submit
    ), patch.object(
        orchestrator, "add_repair_range", return_value={"ok": True, "ranges": [{"id": "rr_h3"}]}
    ), patch(
        "app.director_timeline_w46.continuity.generator_locality",
        return_value="local",
    ):
        reg.return_value.get.return_value = _Adapter()
        out = orchestrator.retake_range(
            db,
            pid,
            sid,
            batch_id,
            start=1.0,
            length=1.0,
            prompt="hold the hallway framing",
            spend_api_credits=False,
        )
    assert out["ok"] is True, out
    assert out.get("error") != "IMAGE_FRAME_I2V_UNSUPPORTED"
    assert "text-to-video only" not in str(out.get("message") or "").lower()
    assert out.get("referenceImageAssetId") == img
    assert out["rangeReplacement"]["referenceImageAssetId"] == img
    assert out["rangeReplacement"]["generatorId"] == "minimax-h3-t2v-local"
    rr = (captured.get("continuity") or {}).get("rangeReplacement") or {}
    assert rr.get("referenceImageAssetId") == img
    assert captured["batch_id"] == batch_id


def test_retake_range_rejects_image_frame_without_i2v_or_r2v(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid, generator_id="fake-t2v-only")
    img = _seed_image_asset(db, pid)
    assert (
        place_visual_image_range(
            db,
            pid,
            sid,
            mark_in=1.0,
            mark_out=2.0,
            image_asset_id=img,
            placement_id="not2v",
            source_batch_id=batch_id,
            source_asset_id="asset-orig",
        )["ok"]
        is True
    )

    class _Caps:
        supportsImageToVideo = False
        supportsReferenceToVideo = False

    class _Adapter:
        capabilities = _Caps()

    class _Gen:
        label = "Fake T2V"
        locality = "local"
        executable = True
        supportsImageToVideo = False
        supportsReferenceToVideo = False
        supportsTextToVideo = True
        inPaintStrategies = ["range_replacement"]
        disabledReason = None
        readiness = "Ready"

    with patch.object(orchestrator, "get_generator", return_value=_Gen()), patch(
        "app.director_timeline_w46.generation.registry.get_registry"
    ) as reg, patch(
        "app.director_timeline_w46.continuity.generator_locality",
        return_value="local",
    ):
        reg.return_value.get.return_value = _Adapter()
        out = orchestrator.retake_range(
            db,
            pid,
            sid,
            batch_id,
            start=1.0,
            length=1.0,
            prompt="should fail",
            spend_api_credits=False,
        )
    assert out["ok"] is False
    assert out["error"] == "IMAGE_FRAME_I2V_UNSUPPORTED"
    assert "text-to-video only" not in str(out.get("message") or "").lower()
    msg = str(out.get("message") or "")
    assert "Reference-to-Video" in msg or "R2V" in msg


def test_request_builder_h3_range_image_stays_reference_mode():
    batch = BatchBlock(
        id="bb_r2v",
        sceneId="scene-r2v",
        label="H3",
        generatorId="minimax-h3-t2v-local",
        promptSegments=[
            TimelinePromptSegment(id="ps1", start=0.0, length=5.0, text="established hallway walk")
        ],
        duration=DurationState(plannedDuration=5.0),
    )
    snap = ExecutionSnapshot(
        batchBlockId=batch.id,
        selectedGenerator="minimax-h3-t2v-local",
        continuityState={
            "reTakeReason": "range_replacement",
            "userCorrection": {
                "delta": "slow the walk",
                "prompt": "slow the walk",
                "start": 1.0,
                "length": 1.0,
            },
            "rangeReplacement": {
                "start": 1.0,
                "length": 1.0,
                "prompt": "slow the walk",
                "sourceAssetId": "asset-orig",
                "startImageAssetId": "img-frame-1",
                "referenceImageAssetId": "img-frame-1",
            },
        },
    )
    req = build_timeline_generation_request(
        project_id="proj-r2v",
        scene_id="scene-r2v",
        batch=batch,
        snapshot=snap,
    )
    assert req.generatorId == "minimax-h3-t2v-local"
    assert req.generationMode == "reference"
    assert req.startImageAssetId == "img-frame-1"
    caps = MiniMaxH3LocalAdapter.capabilities
    assert caps.supportsImageToVideo is False
    assert caps.supportsReferenceToVideo is True


def test_retake_package_asserts_r2v_contract():
    batch = BatchBlock(
        id="bb_pkg",
        sceneId="scene-pkg",
        label="H3",
        generatorId="minimax-h3-t2v-local",
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0.0,
                length=8.0,
                text="[WIDE] cast on the couch in the quarters",
            )
        ],
        duration=DurationState(plannedDuration=8.0),
        currentTakeId="take_1",
        currentTakeAssetId="asset-1",
    )
    pkg = build_retake_context_package(
        batch=batch,
        range_rep={
            "start": 2.0,
            "length": 2.0,
            "prompt": "tighter on Korri",
            "sourceAssetId": "asset-1",
            "referenceImageAssetId": "img-crs",
            "startImageAssetId": "img-crs",
        },
        supports_image_to_video=False,
        supports_reference_to_video=True,
    )
    bc = pkg["boundaryContinuity"]
    assert bc["supportsReferenceToVideo"] is True
    assert bc["supportsImageToVideo"] is False
    assert bc["i2vAttached"] is False
    assert bc["r2vAttached"] is True
    assert "Reference-to-Video" in (bc.get("honesty") or "")
    honesty = bc.get("honesty") or ""
    assert "Seedance" in honesty or "T2V" in honesty
    hard = pkg["compiledPrompt"]
    assert "supportsReferenceToVideo=True" in hard
    assert "supportsImageToVideo=False" in hard
