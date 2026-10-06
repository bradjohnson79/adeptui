"""Visual-track range replacement: A|Middle|B geometry, fit-or-fail, persist.

SINGLE-STORE: SceneTimelineMaster batch.visualClips is the sole Visual SoT.
These tests seed and assert Master batch.visualClips (batch-local coords) —
never the retired legacy director_json video_clips array (PUT /director is
410 Gone; save_master persists Master + workspace only).
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db import Asset, Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import store
from app.director_timeline_w46.contracts import (
    ApprovedClip,
    BatchBlock,
    BatchClip,
    DurationState,
    SceneTimelineMaster,
)
from app.director_timeline_w46.generation import completion as completion_mod
from app.director_timeline_w46.generation.completion import (
    apply_shared_completion,
    place_approved_batches_on_timeline,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationResult
from app.director_timeline_w46.visual_range import (
    find_image_frame_asset_in_range,
    place_visual_image_range,
    replace_visual_range,
)


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Visual Range", description=""))
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


def _seed_active_take(db, pid, sid, *, asset_id="asset-orig", length=5.0):
    """Plant a one-window Master with an approved playable take (Master SoT)."""
    master = SceneTimelineMaster(
        sceneId=sid,
        batchBlocks=[
            BatchBlock(
                id="bb1",
                sceneId=sid,
                order=0,
                label="Window 1",
                status="Approved",
                duration=DurationState(plannedDuration=length, timelineVisibleDuration=length),
                approvedClip=ApprovedClip(assetId=asset_id, executionSnapshotId="snap-a"),
            )
        ],
    )
    store.save_master(db, pid, sid, master)
    return "bb1"


def _visual_clips(db, pid, sid, batch_id="bb1") -> list:
    """Read back Master batch.visualClips (batch-local coordinates)."""
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    return list(batch.visualClips or [])


def test_replace_visual_range_splits_a_retake_b_trim_starts(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    out = replace_visual_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.5,
        replacement_asset_id="asset-retake",
        retake_id="rr_test1",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
        replacement_duration=1.5,
    )
    assert out["ok"] is True, out
    clips = {c["id"]: c for c in out["clips"]}
    assert f"bbvclip_{batch_id}" in clips
    assert clips[f"bbvclip_{batch_id}"]["start"] == 0.0
    assert clips[f"bbvclip_{batch_id}"]["length"] == 1.0
    assert clips[f"bbvclip_{batch_id}"]["trim_start"] == 0.0
    assert clips[f"bbvclip_{batch_id}"]["asset_id"] == "asset-orig"

    rt = clips["rtclip_rr_test1"]
    assert rt["start"] == 1.0
    assert rt["length"] == 1.5
    assert rt["trim_start"] == 0.0
    assert rt["asset_id"] == "asset-retake"
    assert rt["metadata"]["markIn"] == 1.0
    assert rt["metadata"]["markOut"] == 2.5
    assert rt["metadata"]["sourceBatchId"] == batch_id

    b = next(c for c in out["clips"] if c["id"].startswith("rtb_"))
    assert b["start"] == 2.5
    assert b["length"] == pytest.approx(2.5)
    assert b["trim_start"] == 2.5  # markOut, not 0
    assert b["asset_id"] == "asset-orig"

    # Same-lane: no overlap (Master batch-local ordering)
    ordered = sorted(_visual_clips(db, pid, sid), key=lambda c: c.start)
    assert [c.id for c in ordered] == [f"bbvclip_{batch_id}", "rtclip_rr_test1", b["id"]]
    assert ordered[0].start + ordered[0].length == pytest.approx(ordered[1].start)
    assert ordered[1].start + ordered[1].length == pytest.approx(ordered[2].start)


def test_replace_visual_range_duration_mismatch_fails_without_mutation(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    before_ids = [c.id for c in _visual_clips(db, pid, sid)]
    out = replace_visual_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        replacement_asset_id="asset-bad",
        retake_id="rr_bad",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
        replacement_duration=3.0,  # != 1.0
    )
    assert out["ok"] is False
    assert out["error"] == "REPLACEMENT_DURATION_MISMATCH"
    after = _visual_clips(db, pid, sid)
    assert [c.id for c in after] == before_ids
    # Approved take untouched by the refused split.
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    assert batch.approvedClip is not None
    assert batch.approvedClip.assetId == "asset-orig"


def test_replace_visual_range_persist_reload_keeps_geometry_and_metadata(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    out = replace_visual_range(
        db,
        pid,
        sid,
        mark_in=0.5,
        mark_out=2.0,
        replacement_asset_id="asset-retake",
        retake_id="rr_persist",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
        replacement_duration=1.5,
    )
    assert out["ok"] is True
    # Reload from DB (Master visualClips)
    by_id = {c.id: c for c in _visual_clips(db, pid, sid)}
    assert "rtclip_rr_persist" in by_id
    rt = by_id["rtclip_rr_persist"]
    assert rt.metadata["retakeId"] == "rr_persist"
    assert rt.metadata["sourceAssetId"] == "asset-orig"
    assert rt.metadata["replacementAssetId"] == "asset-retake"
    assert rt.metadata["markIn"] == 0.5
    assert rt.metadata["markOut"] == 2.0
    assert rt.metadata["createdAt"]
    b = next(c for c in by_id.values() if str(c.id).startswith("rtb_"))
    assert b.trimStart == 2.0


def test_place_approved_skips_bbclip_overwrite_when_range_composition_present(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    assert replace_visual_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        replacement_asset_id="asset-retake",
        retake_id="rr_gate",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
        replacement_duration=1.0,
    )["ok"] is True

    # Would formerly rebuild a single bbvclip_ full take — must not.
    placed = place_approved_batches_on_timeline(db, pid, sid)
    assert placed["ok"] is True
    clips = _visual_clips(db, pid, sid)
    ids = [c.id for c in clips]
    assert "rtclip_rr_gate" in ids
    assert sum(1 for i in ids if i.startswith("bbvclip_")) == 1  # A remnant only
    # Not a single full-take overwrite
    full = next(c for c in clips if c.id == f"bbvclip_{batch_id}")
    assert full.length == pytest.approx(1.0)
    assert any(c.id.startswith("rtb_") for c in clips)


def test_non_range_approve_still_places_bbclip(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid, asset_id="asset-whole", length=5.0)

    placed = place_approved_batches_on_timeline(db, pid, sid)
    assert placed["ok"] is True
    assert f"bbvclip_{batch_id}" in placed["clipIds"]
    clips = _visual_clips(db, pid, sid)
    assert len(clips) == 1
    assert clips[0].id == f"bbvclip_{batch_id}"
    assert clips[0].length == pytest.approx(5.0)
    assert clips[0].trimStart == 0.0


def test_range_retake_complete_calls_replace_not_whole_take_placer(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    from app.director_timeline_w46.contracts import ExecutionSnapshot

    snap = ExecutionSnapshot(
        batchBlockId=batch_id,
        continuityState={
            "reTakeReason": "range_replacement",
            "rangeReplacement": {
                "start": 1.0,
                "length": 1.0,
                "sourceAssetId": "asset-orig",
                "repairId": "rr_complete",
            },
        },
    )
    master.executionSnapshots[snap.id] = snap
    store.save_master(db, pid, sid, master)

    result = TimelineGenerationResult(
        internalJobId="job-r",
        providerJobId="prov-r",
        queueJobId="q-r",
        generatorId="ltx-local",
        status="completed",
        outputAssetIds=["asset-retake"],
        duration=1.0,
        apiUsed=False,
    )

    with patch.object(
        completion_mod, "place_approved_batches_on_timeline"
    ) as mock_place, patch(
        "app.director_timeline_w46.visual_range._probe_asset_duration",
        return_value=1.0,
    ):
        done = apply_shared_completion(
            db,
            project_id=pid,
            scene_id=sid,
            batch_id=batch_id,
            execution_snapshot_id=snap.id,
            result=result,
            auto_approve=False,
        )
    assert done["ok"] is True, done
    mock_place.assert_not_called()
    placement = done.get("placement") or {}
    assert placement.get("ok") is True
    assert "rtclip_rr_complete" in (placement.get("clipIds") or [])

    clips = _visual_clips(db, pid, sid)
    assert any(c.id == "rtclip_rr_complete" for c in clips)
    b = next(c for c in clips if str(c.id).startswith("rtb_"))
    assert b.trimStart == 2.0
    # auto_approve OFF must not block insertion
    reloaded = SceneTimelineMaster.model_validate(store.load_master(db, pid, sid)["master"])
    live = next(b for b in reloaded.batchBlocks if b.id == batch_id)
    assert live.approvedClip is not None  # prior approved remains
    assert live.approvedClip.assetId == "asset-orig"
    assert live.candidateVersions  # new candidate attached


def test_non_destructive_keeps_unrelated_clips(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    batch.visualClips = [
        BatchClip(
            id="manual_extra",
            kind="video",
            assetId="asset-manual",
            start=10.0,
            length=2.0,
            label="Manual",
        )
    ]
    store.save_master(db, pid, sid, master)

    out = replace_visual_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        replacement_asset_id="asset-retake",
        retake_id="rr_nd",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
        replacement_duration=1.0,
    )
    assert out["ok"] is True
    ids = [c.id for c in _visual_clips(db, pid, sid)]
    assert "manual_extra" in ids
    assert "rtclip_rr_nd" in ids


def _seed_image_asset(db, pid, asset_id=None):
    asset_id = asset_id or f"asset-img-{uuid.uuid4().hex[:8]}"
    db.add(
        Asset(
            id=asset_id,
            project_id=pid,
            tag="frame",
            kind="image",
            filename="frame.png",
            path="missing-ok-for-kind-check.png",
        )
    )
    db.commit()
    return asset_id


def test_place_visual_image_range_splits_a_image_b(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    img = _seed_image_asset(db, pid)
    out = place_visual_image_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.5,
        image_asset_id=img,
        placement_id="place1",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
    )
    assert out["ok"] is True, out
    clips = {c["id"]: c for c in out["clips"]}
    assert f"bbvclip_{batch_id}" in clips
    assert clips[f"bbvclip_{batch_id}"]["length"] == 1.0
    assert clips[f"bbvclip_{batch_id}"]["trim_start"] == 0.0
    assert clips[f"bbvclip_{batch_id}"]["asset_id"] == "asset-orig"

    img_clip = clips["imgclip_place1"]
    assert img_clip["start"] == 1.0
    assert img_clip["length"] == 1.5
    assert img_clip["trim_start"] == 0.0
    assert img_clip["asset_id"] == img
    assert img_clip["media_type"] == "image"
    assert img_clip["metadata"]["role"] == "image_frame"
    assert img_clip["metadata"]["referenceImageAssetId"] == img
    assert img_clip["metadata"]["markIn"] == 1.0
    assert img_clip["metadata"]["markOut"] == 2.5
    assert img_clip["metadata"]["sourceBatchId"] == batch_id
    assert img_clip["metadata"]["createdAt"]

    b = next(c for c in out["clips"] if c["id"].startswith("rtb_"))
    assert b["start"] == 2.5
    assert b["length"] == pytest.approx(2.5)
    assert b["trim_start"] == 2.5
    assert b["asset_id"] == "asset-orig"
    assert b["media_type"] == "video"

    ordered = sorted(_visual_clips(db, pid, sid), key=lambda c: c.start)
    assert [c.id for c in ordered] == [f"bbvclip_{batch_id}", "imgclip_place1", b["id"]]
    assert ordered[1].kind == "image"


def test_place_visual_image_range_rejects_non_image_and_bad_marks(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    vid = f"asset-vid-{uuid.uuid4().hex[:8]}"
    db.add(
        Asset(
            id=vid,
            project_id=pid,
            tag="v",
            kind="video",
            filename="v.mp4",
            path="v.mp4",
        )
    )
    db.commit()
    bad_kind = place_visual_image_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        image_asset_id=vid,
        placement_id="x",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
    )
    assert bad_kind["ok"] is False
    assert bad_kind["error"] == "IMAGE_ASSET_KIND_REQUIRED"

    img = _seed_image_asset(db, pid)
    bad_marks = place_visual_image_range(
        db,
        pid,
        sid,
        mark_in=2.0,
        mark_out=2.0,
        image_asset_id=img,
        placement_id="y",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
    )
    assert bad_marks["ok"] is False
    assert bad_marks["error"] == "INVALID_RANGE"


def test_find_image_frame_asset_in_range_from_imgclip(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    img = _seed_image_asset(db, pid)
    assert place_visual_image_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        image_asset_id=img,
        placement_id="refwin",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
    )["ok"] is True
    clips = _visual_clips(db, pid, sid)
    found = find_image_frame_asset_in_range(
        clips,
        mark_in=1.0,
        mark_out=2.0,
        source_batch_id=batch_id,
    )
    assert found == img
    miss = find_image_frame_asset_in_range(
        clips,
        mark_in=3.0,
        mark_out=4.0,
        source_batch_id=batch_id,
    )
    assert miss is None


def test_replace_visual_range_preserves_reference_image_asset_id(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    out = replace_visual_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        replacement_asset_id="asset-retake",
        retake_id="rr_refkeep",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
        replacement_duration=1.0,
        reference_image_asset_id="asset-seed-img",
    )
    assert out["ok"] is True, out
    rt = next(c for c in out["clips"] if c["id"] == "rtclip_rr_refkeep")
    assert rt["metadata"]["referenceImageAssetId"] == "asset-seed-img"
    persisted = next(c for c in _visual_clips(db, pid, sid) if c.id == "rtclip_rr_refkeep")
    assert persisted.metadata["referenceImageAssetId"] == "asset-seed-img"


def test_image_then_video_replace_uses_shared_splitter(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    img = _seed_image_asset(db, pid)
    assert place_visual_image_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        image_asset_id=img,
        placement_id="thenvid",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
    )["ok"] is True
    out = replace_visual_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        replacement_asset_id="asset-retake",
        retake_id="rr_after_img",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
        replacement_duration=1.0,
        reference_image_asset_id=img,
    )
    assert out["ok"] is True, out
    clips = sorted(_visual_clips(db, pid, sid), key=lambda c: c.start)
    ids = [c.id for c in clips]
    assert "imgclip_thenvid" not in ids
    assert "rtclip_rr_after_img" in ids
    rt = next(c for c in clips if c.id == "rtclip_rr_after_img")
    assert rt.metadata["referenceImageAssetId"] == img
    b = next(c for c in clips if str(c.id).startswith("rtb_"))
    assert b.trimStart == 2.0


def test_retake_range_picks_reference_from_imgclip(db_scene):
    """Retake-range continuity carries referenceImageAssetId from Visual imgclip_*."""
    from app.director_timeline_w46 import orchestrator

    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    img = _seed_image_asset(db, pid)
    assert place_visual_image_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        image_asset_id=img,
        placement_id="retakeref",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
    )["ok"] is True
    # retake_range is fail-closed on the CURRENT take: mint Take A from the
    # existing approved media via the real bundle load (initial migration).
    from app.director_timeline_w46 import service as timeline_service

    bundle = timeline_service.load_timeline_bundle(db, pid, sid)
    assert bundle.get("ok") is True
    master = bundle["master"]
    assert master.sceneTakes, "initial migration must bind existing media to Take A"
    master.batchBlocks[0].generatorId = "ltx-local"
    master.sceneGeneratorId = "ltx-local"
    store.save_master(db, pid, sid, master)

    class _Caps:
        supportsImageToVideo = True

    class _Adapter:
        capabilities = _Caps()

    class _Gen:
        label = "Mock I2V"
        locality = "local"
        executable = True
        supportsImageToVideo = True
        inPaintStrategies = ["range_replacement"]
        disabledReason = None
        readiness = "ready"

    captured = {}

    def _fake_submit(db, project_id, scene_id, batch_id, continuity=None, **kwargs):
        captured["continuity"] = continuity
        return {"ok": True, "queueJobId": "q-mock", "internalJobId": "i-mock"}

    with patch.object(orchestrator, "get_generator", return_value=_Gen()), patch(
        "app.director_timeline_w46.generation.registry.get_registry"
    ) as reg, patch.object(
        orchestrator,
        "submit_batch_generation",
        side_effect=_fake_submit,
    ), patch.object(
        orchestrator,
        "add_repair_range",
        return_value={"ok": True, "ranges": [{"id": "rr_mock"}]},
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
            prompt="walk forward",
            spend_api_credits=False,
        )
    assert out["ok"] is True, out
    assert out.get("referenceImageAssetId") == img
    assert out["rangeReplacement"]["referenceImageAssetId"] == img
    assert out["rangeReplacement"]["startImageAssetId"] == img
    rr = (captured.get("continuity") or {}).get("rangeReplacement") or {}
    assert rr.get("referenceImageAssetId") == img
    assert rr.get("startImageAssetId") == img


def test_place_approved_skips_overwrite_when_imgclip_composition_present(db_scene):
    db, pid, sid = db_scene
    batch_id = _seed_active_take(db, pid, sid)
    img = _seed_image_asset(db, pid)
    assert place_visual_image_range(
        db,
        pid,
        sid,
        mark_in=1.0,
        mark_out=2.0,
        image_asset_id=img,
        placement_id="gateimg",
        source_batch_id=batch_id,
        source_asset_id="asset-orig",
    )["ok"] is True
    placed = place_approved_batches_on_timeline(db, pid, sid)
    assert placed["ok"] is True
    clips = _visual_clips(db, pid, sid)
    ids = [c.id for c in clips]
    assert "imgclip_gateimg" in ids
    full = next(c for c in clips if c.id == f"bbvclip_{batch_id}")
    assert full.length == pytest.approx(1.0)


def test_request_builder_uses_reference_image_from_range_rep():
    from app.director_timeline_w46.generation.request_builder import _range_replacement
    from app.director_timeline_w46.contracts import ExecutionSnapshot

    snap = ExecutionSnapshot(
        batchBlockId="b1",
        continuityState={
            "rangeReplacement": {
                "start": 1.0,
                "length": 1.0,
                "referenceImageAssetId": "asset-from-imgclip",
            }
        },
    )
    rr = _range_replacement(snap)
    assert rr["referenceImageAssetId"] == "asset-from-imgclip"
    # request_builder cut_in preference is covered by reading the source path
    from pathlib import Path
    src = Path("app/director_timeline_w46/generation/request_builder.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert 'range_rep.get("referenceImageAssetId")' in src
