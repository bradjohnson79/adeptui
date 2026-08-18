"""Phase 2 — Qwen image-to-image ERS grounding + Environment Visual Canon.

Binding law under test: ERS generation requires a generator capable of
image input + text/structured instruction. A pure text-to-image generator is
not acceptable for ERS. The real conditioning proof is the graph itself:
LoadImage -> TextEncodeQwenImageEdit (image tokens + reference latents).
"""

from __future__ import annotations

import uuid

import pytest

from app.codirector.capabilities.handlers import ers_generate
from app.codirector.vision.visual_canon import (
    EnvironmentVisualCanon,
    canon_fingerprint,
    canon_is_stale,
    load_visual_canon,
    merge_visual_canon,
    parse_visual_canon_output,
    save_visual_canon,
)
from app.config import settings
from app.image_product.compile import compile_image_request
from app.image_runtime.fingerprints import graph_hash
from app.image_runtime.certified_registry import get_workflow
from app.spatial_map.schemas import SpatialMapDocument
from app.workflows.qwen_image_2512 import build_qwen_2512_ref_workflow

ATLAS_ID = "caa72759-d965-41f9-b1d5-77cdcf9b9614"


# ---------------------------------------------------------------------------
# 1. Runtime graph — mandatory real conditioning proof (graph level)
# ---------------------------------------------------------------------------


def test_qwen2512_ref_graph_loads_source_image() -> None:
    graph = build_qwen_2512_ref_workflow(
        unet_name=settings.qwen_image_2512_unet,
        clip_name=settings.qwen_image_2512_clip,
        vae_name=settings.qwen_image_2512_vae,
        positive="same environment, north elevation",
        negative="",
        image_name="atlas.png",
        width=1328,
        height=1328,
        seed=7,
        steps=50,
        cfg=4.0,
        model_shift=settings.qwen_image_2512_shift,
    )
    classes = {node["class_type"] for node in graph.values()}
    assert "LoadImage" in classes, "the source image must be opened by the graph"
    assert "TextEncodeQwenImageEdit" in classes, "image tokens + reference latents must be wired"
    # The source image feeds the conditioning node (not just metadata).
    load = graph["5"]
    assert load["class_type"] == "LoadImage"
    assert load["inputs"]["image"] == "atlas.png"
    encode = graph["6"]
    assert encode["class_type"] == "TextEncodeQwenImageEdit"
    assert encode["inputs"]["image"] == ["5", 0]
    assert encode["inputs"]["vae"] == ["3", 0]
    assert encode["inputs"]["clip"] == ["2", 0]
    neg = graph["7"]
    assert neg["class_type"] == "TextEncodeQwenImageEdit"
    assert neg["inputs"]["image"] == ["5", 0]
    sampler = graph["9"]
    assert sampler["class_type"] == "KSampler"
    assert sampler["inputs"]["positive"] == ["6", 0]
    assert sampler["inputs"]["negative"] == ["7", 0]
    # Fingerprint is deterministic (graph drift enforcement relies on it).
    assert graph_hash(graph) == graph_hash(build_qwen_2512_ref_workflow(
        unet_name=settings.qwen_image_2512_unet,
        clip_name=settings.qwen_image_2512_clip,
        vae_name=settings.qwen_image_2512_vae,
        positive="same environment, north elevation",
        negative="",
        image_name="atlas.png",
        width=1328,
        height=1328,
        seed=7,
        steps=50,
        cfg=4.0,
        model_shift=settings.qwen_image_2512_shift,
    ))


def test_qwen2512_ref_registry_entry_is_certified() -> None:
    wf = get_workflow("qwen2512.ref")
    assert wf is not None
    assert wf.status == "Certified"
    assert "LoadImage" in wf.required_nodes
    assert "TextEncodeQwenImageEdit" in wf.required_nodes
    assert "reference_image" in wf.required_inputs


def _qwen_ref_graph(width: int, height: int) -> dict:
    return build_qwen_2512_ref_workflow(
        unet_name=settings.qwen_image_2512_unet,
        clip_name=settings.qwen_image_2512_clip,
        vae_name=settings.qwen_image_2512_vae,
        positive="same environment, north elevation",
        negative="",
        image_name="atlas.png",
        width=width,
        height=height,
        seed=7,
        steps=50,
        cfg=4.0,
        model_shift=settings.qwen_image_2512_shift,
    )


def test_qwen2512_ref_frame_size_is_runtime_not_topology() -> None:
    from app.image_runtime.fingerprints import assert_no_graph_drift, WorkflowGraphDriftError

    wf = get_workflow("qwen2512.ref")
    expected = wf.fingerprints.get("graphHash")
    square = _qwen_ref_graph(1328, 1328)
    wide = _qwen_ref_graph(1280, 720)
    assert graph_hash(square, workflow_key="qwen2512.ref") == expected
    assert graph_hash(wide, workflow_key="qwen2512.ref") == expected
    assert_no_graph_drift(
        built_graph=wide,
        expected_graph_hash=expected,
        workflow_key="qwen2512.ref",
        workflow_version="1.0.0",
    )
    broken = dict(wide)
    broken["5"] = {"class_type": "SaveVideo", "inputs": {"image": "atlas.png"}}
    with pytest.raises(WorkflowGraphDriftError):
        assert_no_graph_drift(
            built_graph=broken,
            expected_graph_hash=expected,
            workflow_key="qwen2512.ref",
            workflow_version="1.0.0",
        )


def test_ers_i2i_workflow_key_available_when_certified() -> None:
    assert ers_generate._ers_i2i_workflow_key() == "qwen2512.ref"


def test_dispatcher_forwards_force_workflow_key() -> None:
    import inspect

    from app.codirector.execution import dispatcher

    src = inspect.getsource(dispatcher)
    assert '"forceWorkflowKey"' in src
    assert '"lockModelFamily"' in src


# ---------------------------------------------------------------------------
# 2. ERS handler — image-to-image routing and honest blocks
# ---------------------------------------------------------------------------


def _sheet(project_id: str, spatial_map_id: str):
    from app.environment_reference_sheet import orchestrator
    from app.environment_reference_sheet.contracts import (
        DirectionalViewRecord,
        SpatialMapReference,
    )

    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium, hanging gardens, cool daylight.",
        scene_id="scene-1",
    )
    sheet.spatialMap = SpatialMapReference(mapId=spatial_map_id, northLockDirection="north")
    sheet.directionalViews = [
        DirectionalViewRecord(
            direction=direction,
            title=f"{direction.title()} View",
            prompt=f"{direction.title()} view of the glass-roofed atrium.",
            sourceDirection=direction,
            status="planned",
        )
        for direction in ("north", "east", "south", "west")
    ]
    return sheet


def _patch_handler(monkeypatch, sheet, document, captured_bodies):
    class _Job:
        def __init__(self, job_id: str) -> None:
            self.id = job_id

    def _fake_enqueue(db, enqueue_project_id, body, scene_id=None):
        captured_bodies.append(dict(body))
        return _Job("job-ers-one")

    monkeypatch.setattr("app.environment_reference_sheet.store.list_sheets", lambda pid: [sheet])
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.attach_spatial_map",
        lambda db, current, spatial_map_id: current,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.compose_sheet_metadata",
        lambda current: current,
    )
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue)
    monkeypatch.setattr(
        ers_generate,
        "_enqueue_ers_image_product",
        lambda db, pid, body, scene_id=None: {"jobId": _fake_enqueue(db, pid, body, scene_id).id},
    )
    monkeypatch.setattr("app.spatial_map.service.get_document", lambda db, pid, mid: document)
    monkeypatch.setattr("app.spatial_map.ers_persistence.save_ers_package", lambda *a, **k: None)
    monkeypatch.setattr("app.environment_reference_sheet.store.save_sheet", lambda current: None)


def test_ers_requires_authoritative_source_image(monkeypatch) -> None:
    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    sheet = _sheet(project_id, spatial_map_id)
    captured: list[dict] = []
    _patch_handler(
        monkeypatch,
        sheet,
        SpatialMapDocument(projectId=project_id, id=spatial_map_id),
        captured,
    )
    with pytest.raises(RuntimeError, match="authoritative environment image"):
        ers_generate.handle(
            db=None,
            project_id=project_id,
            execution_id="e-1",
            spatial_map_id=spatial_map_id,
            model="qwen2512",
            model_family_preference="qwen2512",
        )
    assert not captured


def test_ers_defaults_to_qwen_i2i_with_source(monkeypatch) -> None:
    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    sheet = _sheet(project_id, spatial_map_id)
    captured: list[dict] = []
    _patch_handler(
        monkeypatch,
        sheet,
        SpatialMapDocument(projectId=project_id, id=spatial_map_id, backgroundAssetId=ATLAS_ID),
        captured,
    )
    ers_generate.handle(db=None, project_id=project_id, execution_id="e-2", spatial_map_id=spatial_map_id)
    assert len(captured) == 1
    body = captured[0]
    assert body.get("forceWorkflowKey") == "qwen2512.ref"
    assert body.get("sourceAssetId") == ATLAS_ID
    assert body["creativeContext"]["referenceGrounding"]["mode"] == "pixel"
    assert "qwen2512.ref" in str(body.get("creativeContext") or {}).replace("'", '"')


# ---------------------------------------------------------------------------
# 3. Compile — ERS preserves source pixels without becoming an edit
# ---------------------------------------------------------------------------


def test_compile_ers_preserves_source_asset_and_operation(monkeypatch) -> None:
    project_id = f"proj-{uuid.uuid4()}"
    body = {
        "prompt": "One unified ERS of the atrium.",
        "purpose": "environment_reference_sheet",
        "operation": "image.generate",
        "sourceAssetId": ATLAS_ID,
        "source_asset_id": ATLAS_ID,
        "referenceImage": ATLAS_ID,
        "modelFamilyPreference": "qwen2512",
        "forceWorkflowKey": "qwen2512.ref",
        "allow_force_workflow_key": True,
        "lockModelFamily": True,
        "source": "local",
        "tag": "codirector_ers_e_test",
        "width": 2560,
        "height": 1440,
        "creativeContext": {"objective": "environment_reference_sheet"},
    }
    compiled = compile_image_request(project_id, body)
    intent = compiled["imageIntent"]
    assert intent["operation"] == "image.generate"
    assert intent["sourceAssetId"] == ATLAS_ID
    runtime = compiled["imageRuntime"]
    assert runtime.get("canExecute") is True
    selected = str(runtime.get("workflowKey") or compiled.get("contract", {}).get("workflow_key") or "")
    assert selected == "qwen2512.ref"
    assert "zimage" not in selected


# ---------------------------------------------------------------------------
# 4. Environment Visual Canon — parse, merge, staleness, persistence
# ---------------------------------------------------------------------------


DETERMINISTIC_VLM_OUTPUT = (
    '{"identity": {"environmentType": "coffee_shop", "architecturalStyle": "industrial", '
    '"dominantMaterials": ["brick", "wood"], "colorPalette": ["warm browns", "cream"], '
    '"lightingCharacter": "warm ambient"}, '
    '"geometry": {"roomShape": "rectangle", "wallRelationships": "rear wall = counter", '
    '"windowLocations": ["left wall"], "doorOrEntranceLocations": ["right of counter"], '
    '"circulation": "center aisle"}, '
    '"fixedArchitecture": {"serviceCounterOrBar": {"location": "rear wall", "shape": "long bar", '
    '"orientation": "facing room"}, "shelving": "behind bar", "cabinetry": "under counter", '
    '"builtIns": "none", "permanentFixtures": ["espresso machine"]}, '
    '"furniture": {"couch": {"present": true, "location": "right wall"}, "tables": ["center"], '
    '"chairs": ["around tables"], "stools": ["at bar"], "displayCases": [], "plants": ["two by window"], '
    '"majorLamps": ["pendant over bar"], "majorDecor": ["posters on rear wall"]}, '
    '"spatialRelationships": ["bar spans rear wall", "windows on left wall", "couch against right wall"], '
    '"hardInvariants": ["do not move the service counter", "preserve window count and location", '
    '"do not add or remove the couch", "do not mirror the room"], '
    '"uncertainty": ["ceiling height not visible", "back-of-house layout unseen"]}'
)


def test_visual_canon_parses_deterministic_output() -> None:
    canon = parse_visual_canon_output(DETERMINISTIC_VLM_OUTPUT)
    assert canon is not None
    assert canon.identity.get("environmentType") == "coffee_shop"
    assert canon.geometry.get("windowLocations") == ["left wall"]
    assert canon.fixedArchitecture["serviceCounterOrBar"]["location"] == "rear wall"
    assert canon.furniture["couch"] == {"present": True, "location": "right wall"}
    assert "bar spans rear wall" in canon.spatialRelationships
    assert any("do not move the service counter" in i for i in canon.hardInvariants)
    assert any("ceiling height" in u for u in canon.uncertainty)


def test_visual_canon_unparseable_stays_none() -> None:
    assert parse_visual_canon_output("sorry, no JSON here") is None
    assert parse_visual_canon_output('{"broken": ') is None


def test_visual_canon_fingerprint_stable_and_staleness() -> None:
    canon = parse_visual_canon_output(DETERMINISTIC_VLM_OUTPUT)
    assert canon is not None
    canon.availability = "available"
    canon.sourceAssetId = ATLAS_ID
    canon.groundingFingerprint = "fp-v1"
    fp = canon_fingerprint(canon)
    assert fp == canon_fingerprint(canon)
    assert canon_is_stale(canon, "fp-v2") is True
    assert canon_is_stale(canon, "fp-v1") is False
    assert canon_is_stale(None, "fp-v1") is True


def test_visual_canon_creator_corrections_win() -> None:
    canon = parse_visual_canon_output(DETERMINISTIC_VLM_OUTPUT)
    assert canon is not None
    canon.availability = "available"
    canon.sourceAssetId = ATLAS_ID
    canon.groundingFingerprint = "fp-v1"
    merged = merge_visual_canon(
        canon,
        {"geometry": {"roomShape": "L-shaped", "windowLocations": ["left wall", "rear wall"]}},
    )
    assert merged is not None
    assert merged.geometry["roomShape"] == "L-shaped"
    assert merged.geometry["windowLocations"] == ["left wall", "rear wall"]
    assert merged.provenance == "creator_corrected"
    # Creator corrections change the fingerprint (new version), never the source.
    assert merged.fingerprint != canon.fingerprint
    assert merged.sourceAssetId == ATLAS_ID


def test_visual_canon_persistence_roundtrip() -> None:
    from app.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        project_id = f"proj-{uuid.uuid4()}"
        map_id = f"map-{uuid.uuid4()}"
        canon = parse_visual_canon_output(DETERMINISTIC_VLM_OUTPUT)
        assert canon is not None
        canon.availability = "available"
        canon.sourceAssetId = ATLAS_ID
        canon.mapId = map_id
        canon.groundingFingerprint = "fp-v1"
        save_visual_canon(db, project_id, map_id, canon)
        loaded = load_visual_canon(db, project_id, map_id)
        assert loaded is not None
        assert loaded.identity.get("environmentType") == "coffee_shop"
        assert loaded.groundingFingerprint == "fp-v1"
        assert loaded.sourceAssetId == ATLAS_ID
    finally:
        db.close()
