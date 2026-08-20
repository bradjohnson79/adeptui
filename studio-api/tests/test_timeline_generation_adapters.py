"""Regression: provider-agnostic Timeline generation workflow."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import orchestrator, service
from app.director_timeline_w46.generation.completion import (
    apply_shared_completion,
    place_approved_batches_on_timeline,
)
from app.director_timeline_w46.generation.contracts import (
    TimelineGenerationRequest,
    TimelineGenerationResult,
)
from app.director_timeline_w46.generation.registry import (
    GeneratorNotFoundError,
    get_registry,
)
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.contracts import ExecutionSnapshot


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Timeline Gen Cert", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="cinematic bottle push-in",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def test_registry_resolves_generator_ids():
    reg = get_registry()
    assert reg.resolve_id("minimax-h3-t2v-local") == "minimax-h3-t2v-local"
    assert reg.resolve_id("minimax-h3-local") == "minimax-h3-t2v-local"
    assert reg.resolve_id("minimax-h3") == "minimax-h3-t2v-local"
    assert reg.resolve_id("minimax-h3-i2v-local") == "minimax-h3-i2v-local"
    assert reg.resolve_id("ltx-local") == "ltx-local"
    assert reg.resolve_id("seedance-api") == "seedance-api"
    assert reg.resolve_id("kling-api") == "kling-api"
    with pytest.raises(GeneratorNotFoundError):
        reg.resolve_id("unknown-engine")


def test_capability_validation_rejects_unsupported_refs():
    adapter = get_registry().get("minimax-h3-t2v-local")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="image_to_video",
        prompt="x",
        startImageAssetId="img1",
        fallbackAllowed=False,
    )
    result = adapter.validate(req)
    assert result.ok is False
    assert any("image-to-video" in e.lower() for e in result.errors)


def test_normalized_request_from_batch(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(
        db,
        pid,
        sid,
        batch_id,
        {
            "generatorId": "minimax-h3-t2v-local",
            "promptSegments": [
                {
                    "id": "ps1",
                    "start": 0,
                    "length": 5,
                    "text": "glass bottle condensation",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1",
                }
            ],
            "sourceAnchors": [
                {
                    "id": "anc1",
                    "kind": "image",
                    "assetId": "img-a",
                    "label": "Start",
                    "atTime": 0,
                    "strength": 1,
                }
            ],
        },
    )
    payload = service.workspace(db, pid, sid)
    from app.director_timeline_w46.contracts import BatchBlock, SceneTimelineMaster

    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-t2v-local")
    req = build_timeline_generation_request(
        project_id=pid, scene_id=sid, batch=batch, snapshot=snap, fallback_allowed=False
    )
    assert req.generatorId == "minimax-h3-t2v-local"
    assert req.generationMode == "text_to_video"
    assert "glass bottle" in req.prompt
    assert req.startImageAssetId is None  # T2V profile does not accept I2V start frames
    assert req.providerOptions.get("planningStartImageAssetId") == "img-a"
    assert req.fallbackAllowed is False


def test_i2v_normalized_request_binds_start_image(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(
        db,
        pid,
        sid,
        batch_id,
        {
            "generatorId": "minimax-h3-i2v-local",
            "promptSegments": [
                {
                    "id": "ps1",
                    "start": 0,
                    "length": 5,
                    "text": "identity-preserving motion from start frame",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1",
                }
            ],
            "sourceAnchors": [
                {
                    "id": "anc1",
                    "kind": "image",
                    "assetId": "img-i2v-a",
                    "label": "Start",
                    "atTime": 0,
                    "strength": 1,
                }
            ],
        },
    )
    payload = service.workspace(db, pid, sid)
    from app.director_timeline_w46.contracts import SceneTimelineMaster

    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-i2v-local")
    req = build_timeline_generation_request(
        project_id=pid, scene_id=sid, batch=batch, snapshot=snap, fallback_allowed=False
    )
    assert req.generatorId == "minimax-h3-i2v-local"
    assert req.generationMode == "image_to_video"
    assert req.startImageAssetId == "img-i2v-a"
    assert req.fallbackAllowed is False


def test_ltx_routes_through_shared_interface(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(
        db,
        pid,
        sid,
        batch_id,
        {
            "generatorId": "ltx-local",
            "promptSegments": [
                {
                    "id": "ps1",
                    "start": 0,
                    "length": 5,
                    "text": "ltx motion test",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1",
                }
            ],
        },
    )
    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        gen = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert gen["ok"] is True
    assert gen["generatorId"] == "ltx-local"
    assert gen["queueJobId"]
    assert gen["normalizedRequest"]["generatorId"] == "ltx-local"
    assert gen["job"]["queueJobId"] == gen["queueJobId"]


def test_ltx_collects_output_asset_ids_from_job_params(db_scene):
    from app.db import Job
    from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter
    from app.director_timeline_w46.generation.contracts import NormalizedJobSubmission

    db, pid, sid = db_scene
    job_id = str(uuid.uuid4())
    db.add(
        Job(
            id=job_id,
            project_id=pid,
            scene_id=sid,
            kind="render_scene",
            status="done",
            progress=1.0,
            message="Scene render complete",
            stage="done",
            params_json=json.dumps(
                {
                    "outputAssetIds": ["asset-ltx-draft"],
                    "draftMode": True,
                    "aspectRatio": "21:9",
                    "resolution": "672x288",
                }
            ),
            output_path="C:/tmp/ltx-draft.mp4",
        )
    )
    db.commit()
    adapter = LtxLocalAdapter()
    sub = NormalizedJobSubmission(
        internalJobId=job_id,
        queueJobId=job_id,
        generatorId="ltx-local",
        status="queued",
    )
    st = adapter.get_status(sub)
    assert st.status == "completed"
    assert st.providerMetadata.get("outputAssetIds") == ["asset-ltx-draft"]
    result = adapter.collect_result(sub)
    assert result.status == "completed"
    assert result.outputAssetIds == ["asset-ltx-draft"]


def test_ltx_submit_preserves_timeline_2_5_identity(db_scene):
    from app.db import Job
    from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter

    db, pid, sid = db_scene
    adapter = LtxLocalAdapter()
    req = TimelineGenerationRequest(
        projectId=pid,
        sceneId=sid,
        batchBlockId="bb_25",
        executionSnapshotId="snap_25",
        generatorId="ltx-local",
        generationMode="image_to_video",
        prompt="continue the turn",
        duration=5.0,
        startImageAssetId="asset_last",
        providerOptions={"originalGeneratorId": "ltx-2.5-distilled", "selectedGenerator": "ltx-2.5-distilled"},
    )
    with patch(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        MagicMock(),
    ):
        sub = adapter.submit(req)
    row = db.get(Job, sub.queueJobId)
    params = json.loads(row.params_json)
    assert params["generatorId"] == "ltx-2.5-distilled"
    assert params["variant"] == "ltx-2.5-distilled"
    assert params["adapterId"] == "ltx-local"
    assert sub.providerMetadata.get("requestedModel") == "ltx-2.5-distilled"


def test_ltx_submit_queued_does_not_imply_provider_accepted(db_scene):
    from app.db import Job
    from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter

    db, pid, sid = db_scene
    adapter = LtxLocalAdapter()
    req = TimelineGenerationRequest(
        projectId=pid,
        sceneId=sid,
        batchBlockId="bb_test",
        executionSnapshotId="snap_test",
        generatorId="ltx-2.5-distilled",
        generationMode="image_to_video",
        prompt="continue the turn",
        duration=5.0,
        startImageAssetId="asset_last",
    )
    with patch(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        MagicMock(),
    ):
        sub = adapter.submit(req)
    assert sub.status == "queued"
    assert sub.queueJobId
    assert sub.providerJobId is None
    assert sub.providerMetadata.get("providerAccepted") is False
    row = db.get(Job, sub.queueJobId)
    assert row is not None
    assert row.status == "queued"
    assert not row.comfy_prompt_id
    st = adapter.get_status(sub)
    assert st.status == "queued"
    assert st.providerJobId is None
    assert st.providerMetadata.get("providerAccepted") is False


def test_ltx_enqueue_failure_fails_job_instead_of_eternal_queued(db_scene):
    from app.db import Job
    from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter

    db, pid, sid = db_scene
    adapter = LtxLocalAdapter()
    req = TimelineGenerationRequest(
        projectId=pid,
        sceneId=sid,
        batchBlockId="bb_fail",
        executionSnapshotId="snap_fail",
        generatorId="ltx-local",
        generationMode="image_to_video",
        prompt="fail enqueue",
        duration=5.0,
    )
    with patch(
        "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
        side_effect=RuntimeError("queue worker loop is not running"),
    ):
        with pytest.raises(RuntimeError, match="queue worker loop"):
            adapter.submit(req)
    rows = db.query(Job).filter(Job.project_id == pid).all()
    assert rows
    assert any(r.status == "failed" and "enqueue" in (r.message or "").lower() for r in rows)


def test_ltx_submit_enqueues_job_queue_not_missing_worker_alias(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(
        db,
        pid,
        sid,
        batch_id,
        {
            "generatorId": "ltx-local",
            "promptSegments": [
                {
                    "id": "ps1",
                    "start": 0,
                    "length": 5,
                    "text": "enqueue",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1",
                }
            ],
        },
    )
    enqueue = MagicMock()
    with (
        patch("app.director_timeline_w46.generation.watcher.start_completion_watcher", MagicMock()),
        patch("app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue", enqueue),
    ):
        gen = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert gen["ok"] is True
    assert enqueue.called
    assert gen.get("providerJobId") in (None, "")


def test_hosted_adapter_returns_provider_job_id():
    adapter = get_registry().get("seedance-api")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="seedance-api",
        generationMode="text_to_video",
        prompt="hosted clip",
        duration=5.0,
        providerOptions={
            "testInjectResult": {"status": "completed", "outputAssetIds": ["asset-seed"]}
        },
    )
    assert adapter.validate(req).ok is True
    sub = adapter.submit(req)
    assert sub.providerJobId and sub.providerJobId.startswith("seedance_")
    assert sub.apiUsed is True
    st = adapter.get_status(sub)
    assert st.status == "completed"
    result = adapter.collect_result(sub)
    assert result.outputAssetIds == ["asset-seed"]


def test_no_silent_generator_fallback(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(db, pid, sid, batch_id, {"generatorId": "not-a-real-generator"})
    gen = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert gen["ok"] is False
    assert gen["error"] == "GENERATOR_UNKNOWN"


def test_submit_requires_generator(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(db, pid, sid, batch_id, {"generatorId": None})
    gen = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert gen["ok"] is False
    assert gen["error"] == "GENERATOR_REQUIRED"


def test_minimax_submit_mocked_adapter(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(
        db,
        pid,
        sid,
        batch_id,
        {
            "generatorId": "minimax-h3-t2v-local",
            "promptSegments": [
                {
                    "id": "ps1",
                    "start": 0,
                    "length": 5,
                    "text": "minimax batch prompt",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1",
                }
            ],
        },
    )

    fake_sub = MagicMock()
    fake_sub.status = "running"
    fake_sub.queueJobId = "h3-job-1"
    fake_sub.providerJobId = "h3-job-1"
    fake_sub.internalJobId = "h3-job-1"
    fake_sub.apiUsed = False
    fake_sub.generatorId = "minimax-h3-t2v-local"
    fake_sub.providerMetadata = {}
    fake_sub.model_dump = lambda: {"queueJobId": "h3-job-1"}

    adapter = get_registry().get("minimax-h3-t2v-local")
    with patch.object(adapter, "submit", return_value=fake_sub), patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        gen = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert gen["ok"] is True
    assert gen["generatorId"] == "minimax-h3-t2v-local"
    assert gen["queueJobId"] == "h3-job-1"
    assert gen["normalizedRequest"]["generatorId"] == "minimax-h3-t2v-local"
    assert gen["apiUsed"] is False


def test_shared_completion_places_clips_in_batch_order(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    b1 = ws["master"]["batchBlocks"][0]["id"]
    added = service.add_batch(db, pid, sid, label="Batch 2", planned_duration=5.0, generator_id="ltx-local")
    b2 = added["batch"]["id"]
    service.patch_batch(db, pid, sid, b1, {"generatorId": "ltx-local", "label": "Batch 1"})

    # Create snapshots + approve via shared completion
    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        # Manually complete without real generate
        from app.director_timeline_w46.contracts import SceneTimelineMaster

        for batch_id, asset in ((b1, "asset-1"), (b2, "asset-2")):
            payload = service.workspace(db, pid, sid)
            master = SceneTimelineMaster.model_validate(payload["master"])
            batch = next(b for b in master.batchBlocks if b.id == batch_id)
            snap = orchestrator.create_execution_snapshot(batch)
            master.executionSnapshots[snap.id] = snap
            from app.director_timeline_w46 import store

            store.save_master(db, pid, sid, master)
            result = TimelineGenerationResult(
                internalJobId=f"job-{asset}",
                providerJobId=f"prov-{asset}",
                queueJobId=f"q-{asset}",
                generatorId="ltx-local",
                status="completed",
                outputAssetIds=[asset],
                duration=5.0,
                apiUsed=False,
            )
            out = apply_shared_completion(
                db,
                project_id=pid,
                scene_id=sid,
                batch_id=batch_id,
                execution_snapshot_id=snap.id,
                result=result,
                auto_approve=True,
            )
            assert out["ok"] is True

    place = place_approved_batches_on_timeline(db, pid, sid)
    assert place["ok"] is True
    assert place["placedCount"] == 2
    # Reload director timeline order
    from app.director_timeline import parse_director_timeline
    from app.director_timeline_w46 import store

    scene = store.get_scene(db, pid, sid)
    tl = parse_director_timeline(scene.director_json, fallback_duration=5.0, fallback_prompt="")
    clips = sorted(tl.video_clips, key=lambda c: c.start)
    assert [c.asset_id for c in clips if str(c.id).startswith("bbclip_")] == ["asset-1", "asset-2"]

    # Idempotent second place
    place2 = place_approved_batches_on_timeline(db, pid, sid)
    assert place2["placedCount"] == 2
    scene2 = store.get_scene(db, pid, sid)
    tl2 = parse_director_timeline(scene2.director_json, fallback_duration=5.0, fallback_prompt="")
    managed = [c for c in tl2.video_clips if str(c.id).startswith("bbclip_")]
    assert len(managed) == 2


def test_lineage_survives_reload(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(db, pid, sid, batch_id, {"generatorId": "ltx-local", "label": "Hero"})
    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.director_timeline_w46 import store

    payload = service.workspace(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap = orchestrator.create_execution_snapshot(batch)
    master.executionSnapshots[snap.id] = snap
    store.save_master(db, pid, sid, master)
    result = TimelineGenerationResult(
        internalJobId="job-lin",
        providerJobId="prov-lin",
        queueJobId="q-lin",
        generatorId="ltx-local",
        status="completed",
        outputAssetIds=["asset-lin"],
        duration=4.5,
        apiUsed=False,
    )
    out = apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=batch_id,
        execution_snapshot_id=snap.id,
        result=result,
    )
    assert out["ok"] is True
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == batch_id)
    assert batch_rel["status"] == "Approved"
    assert batch_rel["approvedClip"]["assetId"] == "asset-lin"
    lineage = next(
        (r for r in batch_rel["references"] if r.get("kind") == "timelineGenerationLineage"),
        None,
    )
    assert lineage is not None
    assert lineage["generatorId"] == "ltx-local"
    assert lineage["queueJobId"] == "q-lin"
    assert lineage["outputAssetId"] == "asset-lin"


def test_i2v_adapter_rejects_missing_start_image():
    adapter = get_registry().get("minimax-h3-i2v-local")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-i2v-local",
        generationMode="image_to_video",
        prompt="identity preserve",
        startImageAssetId=None,
        fallbackAllowed=False,
    )
    result = adapter.validate(req)
    assert result.ok is False
    assert any("startImageAssetId" in e or "Start image" in e for e in result.errors)


def test_i2v_adapter_rejects_fallback_allowed():
    adapter = get_registry().get("minimax-h3-i2v-local")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-i2v-local",
        generationMode="image_to_video",
        prompt="identity preserve",
        startImageAssetId="img-1",
        fallbackAllowed=True,
    )
    result = adapter.validate(req)
    assert result.ok is False
    assert any("fallbackAllowed" in e for e in result.errors)


def test_t2v_adapter_refuses_image_to_video_mode():
    adapter = get_registry().get("minimax-h3-t2v-local")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="image_to_video",
        prompt="x",
        startImageAssetId="img-1",
        fallbackAllowed=False,
    )
    assert adapter.validate(req).ok is False
    with pytest.raises(ValueError, match="image-to-video"):
        adapter.submit(req)


def test_i2v_completion_lineage_keeps_start_image(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(
        db, pid, sid, batch_id, {"generatorId": "minimax-h3-i2v-local", "label": "I2V"}
    )
    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.director_timeline_w46 import store

    payload = service.workspace(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap = orchestrator.create_execution_snapshot(batch)
    master.executionSnapshots[snap.id] = snap
    store.save_master(db, pid, sid, master)
    result = TimelineGenerationResult(
        internalJobId="job-i2v",
        providerJobId="prov-i2v",
        queueJobId="q-i2v",
        generatorId="minimax-h3-i2v-local",
        status="completed",
        outputAssetIds=["asset-i2v"],
        duration=5.0,
        apiUsed=False,
        providerMetadata={
            "startImageAssetId": "img-start-a",
            "startImageSha256": "abc123",
            "comfyImageName": "studio/h3_i2v_a.png",
            "workflowId": "route-a-experimental-private-i2va",
            "ltxUsed": False,
        },
    )
    out = apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=batch_id,
        execution_snapshot_id=snap.id,
        result=result,
    )
    assert out["ok"] is True
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == batch_id)
    lineage = next(
        (r for r in batch_rel["references"] if r.get("kind") == "timelineGenerationLineage"),
        None,
    )
    assert lineage is not None
    assert lineage["startImageAssetId"] == "img-start-a"
    assert lineage["startImageSha256"] == "abc123"
    assert lineage["comfyImageName"] == "studio/h3_i2v_a.png"
    assert lineage["workflowId"] == "route-a-experimental-private-i2va"
    assert lineage["generatorId"] == "minimax-h3-i2v-local"


def test_retake_does_not_overwrite_active_take(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(db, pid, sid, batch_id, {"generatorId": "ltx-local", "label": "Hero"})
    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.director_timeline_w46 import store

    payload = service.workspace(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap_a = orchestrator.create_execution_snapshot(batch)
    master.executionSnapshots[snap_a.id] = snap_a
    store.save_master(db, pid, sid, master)
    first = apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=batch_id,
        execution_snapshot_id=snap_a.id,
        result=TimelineGenerationResult(
            internalJobId="job-a",
            providerJobId="prov-a",
            queueJobId="q-a",
            generatorId="ltx-local",
            status="completed",
            outputAssetIds=["asset-take-a"],
            duration=5.0,
            apiUsed=False,
        ),
        auto_approve=True,
    )
    assert first["ok"] is True
    payload = service.workspace(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap_b = orchestrator.create_execution_snapshot(
        batch,
        continuity={"reTakeReason": "creator_retake", "userCorrection": {"delta": "walk behind"}},
    )
    master.executionSnapshots[snap_b.id] = snap_b
    store.save_master(db, pid, sid, master)
    second = apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=batch_id,
        execution_snapshot_id=snap_b.id,
        result=TimelineGenerationResult(
            internalJobId="job-b",
            providerJobId="prov-b",
            queueJobId="q-b",
            generatorId="ltx-local",
            status="completed",
            outputAssetIds=["asset-take-b"],
            duration=5.0,
            apiUsed=False,
        ),
        auto_approve=True,
    )
    assert second["ok"] is True
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == batch_id)
    assert batch_rel["approvedClip"]["assetId"] == "asset-take-a"
    assert len(batch_rel["candidateVersions"]) == 2
    take_b = next(c for c in batch_rel["candidateVersions"] if c["assetId"] == "asset-take-b")
    assert take_b["approved"] is False
    assert take_b["reTakeReason"] == "creator_retake"
    assert take_b["userCorrection"]["delta"] == "walk behind"
    assert take_b["parentTakeId"]


def test_draft_capability_truth_table():
    reg = get_registry()
    ltx = reg.capabilities("ltx-local")
    assert ltx.draftPathway == "local_live"
    assert ltx.supportsQueuedCancel is True
    assert ltx.supportsRunningCancel is True
    assert ltx.supportsVideoReferences is False
    mm = reg.capabilities("minimax-h3-t2v-local")
    assert mm.draftPathway == "none"
    assert mm.supportsRunningCancel is True
    seed = reg.capabilities("seedance-api")
    assert seed.draftPathway == "cheap_preview"
    assert seed.supportsVideoReferences is True
    assert seed.supportsQueuedCancel is False
    kling = reg.capabilities("kling-api")
    assert kling.draftPathway == "none"
    assert kling.supportsVideoReferences is False


def test_video_reference_refused_not_silently_dropped():
    from app.director_timeline_w46.generation.adapter import validate_against_capabilities

    for gen_id in ("ltx-local", "minimax-h3-t2v-local", "kling-api"):
        caps = get_registry().capabilities(gen_id)
        req = TimelineGenerationRequest(
            projectId="p",
            sceneId="s",
            batchBlockId="b",
            executionSnapshotId="snap",
            generatorId=gen_id,
            generationMode="text_to_video",
            prompt="dance",
            videoReferenceAssetId="vid-1",
        )
        result = validate_against_capabilities(caps, req)
        assert result.ok is False, gen_id
        assert any("video reference" in e.lower() for e in result.errors), result.errors
        assert req.videoReferenceAssetId == "vid-1"


def test_seedance_accepts_video_reference():
    adapter = get_registry().get("seedance-api")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="seedance-api",
        generationMode="image_to_video",
        prompt="character dances",
        startImageAssetId="img-1",
        videoReferenceAssetId="vid-1",
        aspectRatio="21:9",
        resolution="480p",
        providerOptions={"testInjectResult": {"status": "completed", "outputAssetIds": ["draft-a"]}},
    )
    assert adapter.validate(req).ok is True
    sub = adapter.submit(req)
    result = adapter.collect_result(sub)
    assert result.outputAssetIds == ["draft-a"]


def test_request_builder_sets_draft_and_aspect(db_scene):
    db, pid, sid = db_scene
    from app.db import Scene

    row = db.get(Scene, sid)
    row.aspect_ratio = "21:9"
    db.commit()
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(
        db,
        pid,
        sid,
        batch_id,
        {
            "generatorId": "ltx-local",
            "promptSegments": [
                {
                    "id": "ps1",
                    "start": 0,
                    "length": 5,
                    "text": "ultrawide draft",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1",
                }
            ],
            "sourceAnchors": [
                {
                    "id": "ancv",
                    "kind": "video",
                    "assetId": "motion-1",
                    "label": "Video Reference",
                    "atTime": 0,
                    "strength": 1,
                }
            ],
        },
    )
    payload = service.workspace(db, pid, sid)
    from app.director_timeline_w46.contracts import SceneTimelineMaster

    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-local")
    req = build_timeline_generation_request(
        project_id=pid, scene_id=sid, batch=batch, snapshot=snap, aspect_ratio="21:9"
    )
    assert req.aspectRatio == "21:9"
    assert req.resolution == "672x288"
    assert req.providerOptions.get("draftMode") is True
    assert req.videoReferenceAssetId == "motion-1"
    refused = get_registry().get("ltx-local").validate(req)
    assert refused.ok is False
    assert any("video reference" in e.lower() for e in refused.errors)


def test_seedance_draft_uses_480p_final_uses_720p():
    from app.director_timeline_w46.contracts import BatchBlock, DurationState, TimelinePromptSegment
    from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request

    batch = BatchBlock(
        id="b1",
        sceneId="s",
        label="Hero",
        generatorId="seedance-api",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=5,
                text="wide shot",
                role="primary",
                strength=1,
                anchorIds=[],
                executionStrategy="compiled",
                versionId="psv1",
            )
        ],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="seedance-api")
    draft = build_timeline_generation_request(
        project_id="p", scene_id="s", batch=batch, snapshot=snap, aspect_ratio="21:9", draft_mode=True
    )
    assert draft.resolution == "480p"
    assert draft.aspectRatio == "21:9"
    final = build_timeline_generation_request(
        project_id="p", scene_id="s", batch=batch, snapshot=snap, aspect_ratio="21:9", draft_mode=False
    )
    assert final.resolution == "720p"
    assert final.providerOptions.get("draftMode") is False


def test_draft_completion_does_not_auto_approve(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(db, pid, sid, batch_id, {"generatorId": "ltx-local"})
    from app.director_timeline_w46 import store
    from app.director_timeline_w46.contracts import SceneTimelineMaster

    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap = orchestrator.create_execution_snapshot(
        batch, continuity={"takeState": {"quality": "draft", "draftPathway": "local_live"}}
    )
    master.executionSnapshots[snap.id] = snap
    store.save_master(db, pid, sid, master)
    done = apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=batch_id,
        execution_snapshot_id=snap.id,
        result=TimelineGenerationResult(
            internalJobId="job-draft",
            generatorId="ltx-local",
            status="completed",
            outputAssetIds=["asset-draft"],
            duration=5.0,
        ),
        auto_approve=True,
    )
    assert done["ok"] is True
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == batch_id)
    assert batch_rel["approvedClip"] is None
    assert batch_rel["status"] == "CandidateReady"
    cand = batch_rel["candidateVersions"][0]
    assert cand["takeState"]["quality"] == "draft"
    assert cand["approved"] is False


