"""Regression: provider-agnostic Timeline generation workflow."""

from __future__ import annotations

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
