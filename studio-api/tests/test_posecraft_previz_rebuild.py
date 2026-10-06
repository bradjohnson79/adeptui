"""Wave 5 regressions for the PoseCraft / Fire3D previz rebuild."""

from __future__ import annotations

import json
from pathlib import Path

from app.db import Project
from app.posecraft.import_adapter import import_reconstruction
from app.posecraft.reconstruction.contracts import ADEPT_FIRE3D_32GB_PROFILE
from app.posecraft.reconstruction.layout import layout_ready, write_single_image_layout
from app.posecraft.reconstruction.normalize import normalize_fire3d_output
from app.posecraft.reconstruction.runtime import ReconstructionRuntime, local_fire3d_available
from app.posecraft.schemas import FigureInstance, POSECRAFT_SCHEMA_VERSION, PoseCraftScene
from app.posecraft.scene_ops import replace_human_with_figure, sit_on_object
from app.posecraft.service import migrate_scene_to_current


FIXTURE = Path(__file__).parent / "fixtures" / "fire3d" / "003025_oriented_bboxes.json"


def _create_project(client, name: str = "PoseCraft Previz Rebuild") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Mess Hall previz"})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_adept_32gb_profile_is_config_only() -> None:
    assert ADEPT_FIRE3D_32GB_PROFILE["skip_render"] is True
    assert ADEPT_FIRE3D_32GB_PROFILE["object_batch_size"] == 1
    assert ADEPT_FIRE3D_32GB_PROFILE["appearance_decode_object_chunk_size"] == 1


def test_migrate_schema_2_primitives_to_objects() -> None:
    scene = migrate_scene_to_current(
        {
            "schemaVersion": 2,
            "revision": 4,
            "name": "Cafe",
            "notes": "",
            "updatedAt": "",
            "stage": {"gridSize": 12, "showAxes": True, "showPrimitives": True},
            "camera": {
                "lensMm": 35,
                "aspect": "16:9",
                "guides": [],
                "alpha": -1.57,
                "beta": 1.12,
                "radius": 7.5,
                "target": {"x": 0, "y": 1.2, "z": 0},
            },
            "figures": [],
            "primitives": [
                {
                    "id": "prim-chair",
                    "name": "Cafe Chair",
                    "kind": "block-chair",
                    "position": {"x": 1.2, "z": -0.4},
                    "rotationY": 30,
                    "scale": 1,
                    "size": {"x": 0.5, "y": 0.9, "z": 0.5},
                    "color": "#94a3b8",
                }
            ],
            "selectedFigureId": None,
            "selectedJoint": "head",
        }
    )
    assert scene["schemaVersion"] == POSECRAFT_SCHEMA_VERSION
    assert scene["objects"][0]["id"] == "prim-chair"
    assert scene["objects"][0]["source"] == "procedural"
    assert scene["objects"][0]["position"]["x"] == 1.2
    assert scene["environment"]["id"] == "environment"
    assert scene["cameras"]
    assert scene["shots"] == []


def test_normalize_official_single_image_annotation_fixture(tmp_path: Path) -> None:
    root = tmp_path
    # Official field names from Fire3D single-image annotation (obj_dict).
    (root / "oriented_bboxes.json").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    package = normalize_fire3d_output(root, reconstruction_id="rec-003025", source_asset_id="asset-mess")
    labels = {item.detectedLabel for item in package.objects}
    assert "dining table" in labels
    assert "chair" in labels
    humans = [item for item in package.objects if item.detectedHuman]
    assert len(humans) == 1
    assert package.detectedHumans[0].suggestedReplace is True


def test_import_review_omits_humans_and_honors_include_list(tmp_path: Path) -> None:
    root = tmp_path
    (root / "oriented_bboxes.json").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    package = normalize_fire3d_output(root, reconstruction_id="rec-review", source_asset_id="asset-mess")
    empty = PoseCraftScene.model_validate(migrate_scene_to_current({"schemaVersion": 3, "name": "Stage", "figures": [], "primitives": []}))
    imported = import_reconstruction(empty, package)
    assert all(not obj.detectedHuman for obj in imported.objects)
    assert any(obj.name == "dining table" for obj in imported.objects)

    only_human = import_reconstruction(
        empty,
        package,
        selected_object_ids=[item.objectId for item in package.objects if item.detectedHuman],
    )
    assert len(only_human.objects) == 1
    assert only_human.objects[0].detectedHuman is True


def test_human_replace_does_not_keep_static_person_as_character() -> None:
    scene = PoseCraftScene.model_validate(
        migrate_scene_to_current(
            {
                "schemaVersion": 3,
                "name": "Hall",
                "figures": [],
                "objects": [
                    {
                        "id": "obj-human",
                        "name": "person",
                        "source": "reconstructed",
                        "detectedHuman": True,
                        "position": {"x": 2, "y": 0, "z": 1},
                        "rotation": {"x": 0, "y": 40, "z": 0},
                    }
                ],
            }
        )
    )
    figure = FigureInstance(id="fig-korri", name="Korri", archetypeId="adult-female", colorId="seaglass", position={"x": 0, "z": 0}, rotationY=0, scale=1, pose={})
    result = replace_human_with_figure(scene, "obj-human", figure)
    assert result["applied"] is True
    assert result["keptStaticPerson"] is False
    assert scene.figures[0].id == "fig-korri"
    assert scene.figures[0].position["x"] == 2
    assert scene.objects[0].visible is False
    assert scene.objects[0].id != scene.figures[0].id


def test_sit_on_object_places_pelvis() -> None:
    scene = PoseCraftScene.model_validate(
        migrate_scene_to_current(
            {
                "schemaVersion": 3,
                "name": "Hall",
                "figures": [
                    {
                        "id": "fig-korri",
                        "name": "Korri",
                        "archetypeId": "adult-female",
                        "colorId": "seaglass",
                        "position": {"x": 0, "z": 0},
                        "rotationY": 0,
                        "scale": 1,
                        "pose": {},
                    }
                ],
                "objects": [
                    {
                        "id": "obj-chair",
                        "name": "chair",
                        "source": "procedural",
                        "position": {"x": 1.5, "y": 0, "z": -0.2},
                        "size": {"x": 0.5, "y": 0.8, "z": 0.5},
                    }
                ],
            }
        )
    )
    result = sit_on_object(scene, "fig-korri", "obj-chair")
    assert result["applied"] is True
    assert scene.figures[0].position["x"] == 1.5
    assert scene.figures[0].position["y"] >= 0.38
    assert scene.figures[0].poseId == "rest-seated"


def test_layout_refuses_invented_point_cloud(tmp_path: Path) -> None:
    scene_dir = write_single_image_layout(tmp_path, scene_id="003025", rgb_bytes=b"\xff\xd8fakejpeg")
    ready, reason = layout_ready(scene_dir)
    assert ready is False
    assert "aligned_pcd.ply" in reason


def test_local_fire3d_is_honest_when_missing() -> None:
    available, detail = local_fire3d_available()
    if not available:
        assert "fire3d" in detail.lower() or "wsl" in detail.lower() or "not installed" in detail.lower()
    job = ReconstructionRuntime().start(project_id="p1", source_asset_id="a1")
    if not available:
        assert job.status == "unavailable"
        assert job.package is None


def test_backend_ig_handoff_is_document_sot(client) -> None:
    project_id = _create_project(client)
    scene = {
        "schemaVersion": 3,
        "currentScene": migrate_scene_to_current(
            {
                "schemaVersion": 3,
                "name": "Hall",
                "revision": 2,
                "figures": [],
                "primitives": [],
            }
        ),
        "snapshots": [
            {
                "snapshotId": "snap-1",
                "projectId": "pending",
                "sceneId": "scene-1",
                "name": "Shot 01",
                "imageAssetId": "img-previz-1",
                "camera": {
                    "lensMm": 35,
                    "aspect": "16:9",
                    "guides": [],
                    "alpha": -1.57,
                    "beta": 1.12,
                    "radius": 7.5,
                    "target": {"x": 0, "y": 1.2, "z": 0},
                },
                "sceneRevision": 2,
            }
        ],
        "selectedSnapshotId": "snap-1",
    }
    put = client.put(f"/api/posecraft/projects/{project_id}/scene", json=scene)
    assert put.status_code == 200, put.text
    handoff = client.post(
        f"/api/posecraft/projects/{project_id}/handoff/image-generator",
        json={"snapshotId": "snap-1", "imageAssetId": "img-previz-1"},
    )
    assert handoff.status_code == 200, handoff.text
    got = client.get(f"/api/posecraft/projects/{project_id}/handoff/image-generator")
    assert got.status_code == 200
    assert got.json()["imageAssetId"] == "img-previz-1"
    assert got.json()["snapshotId"] == "snap-1"


def test_auto_previz_requires_stored_approved_plan(client) -> None:
    project_id = _create_project(client, "Auto Previz Gate")
    denied = client.post(
        f"/api/posecraft/projects/{project_id}/auto-previz/execute",
        json={"planId": "missing", "approved": True},
    )
    assert denied.status_code == 404
    unapproved = client.post(
        f"/api/posecraft/projects/{project_id}/auto-previz/execute",
        json={"planId": "anything", "approved": False},
    )
    assert unapproved.status_code == 409
    planned = client.post(
        f"/api/posecraft/projects/{project_id}/auto-previz/plan",
        json={"description": "Korri and Anadriya talk", "shotCount": 3},
    )
    assert planned.status_code == 200, planned.text
    plan_id = planned.json()["planId"]
    executed = client.post(
        f"/api/posecraft/projects/{project_id}/auto-previz/execute",
        json={"planId": plan_id, "approved": True},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["currentScene"]["shots"]


def test_hydrate_failure_does_not_put_empty(client) -> None:
    from app.db import SessionLocal

    project_id = _create_project(client, "Corrupt PoseCraft")
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        assert project is not None
        project.posecraft_document_json = "{not-json"
        db.commit()
    finally:
        db.close()
    loaded = client.get(f"/api/posecraft/projects/{project_id}/scene")
    assert loaded.status_code == 200
    assert loaded.json()["loadState"] == "corrupt"
    empty = loaded.json()
    empty["loadState"] = "corrupt"
    refused = client.put(f"/api/posecraft/projects/{project_id}/scene", json=empty)
    assert refused.status_code == 409
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        assert project.posecraft_document_json == "{not-json"
    finally:
        db.close()


def test_codirector_sit_writes_canonical_scene(client) -> None:
    project_id = _create_project(client, "Co-Director Sit")
    scene = {
        "schemaVersion": 3,
        "currentScene": migrate_scene_to_current(
            {
                "schemaVersion": 3,
                "name": "Hall",
                "revision": 2,
                "figures": [
                    {
                        "id": "fig-korri",
                        "name": "Korri",
                        "archetypeId": "adult-female",
                        "colorId": "seaglass",
                        "position": {"x": 0, "z": 0},
                        "rotationY": 0,
                        "scale": 1,
                        "pose": {},
                    }
                ],
                "objects": [
                    {
                        "id": "obj-chair",
                        "name": "chair",
                        "source": "procedural",
                        "position": {"x": 2, "y": 0, "z": 0},
                        "size": {"x": 0.5, "y": 0.8, "z": 0.5},
                    }
                ],
            }
        ),
    }
    assert client.put(f"/api/posecraft/projects/{project_id}/scene", json=scene).status_code == 200
    proposal = client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": "posecraft.sit_on_object", "arguments": {"figureId": "fig-korri", "objectId": "obj-chair"}},
    )
    assert proposal.status_code == 200, proposal.text
    proposal_id = proposal.json()["id"]
    approved = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve", json={})
    assert approved.status_code == 200, approved.text
    loaded = client.get(f"/api/posecraft/projects/{project_id}/scene")
    figure = loaded.json()["currentScene"]["figures"][0]
    assert figure["position"]["x"] == 2
    assert figure["poseId"] == "rest-seated"


def test_library_classifies_posecraft_3d_and_previz() -> None:
    from app.project_library.classify import ClassifyInput, classify_asset

    previz = classify_asset(ClassifyInput(kind="posecraft_snapshot", filename="shot01.png"))
    assert previz.target_folder == "scenes.sets"
    mesh = classify_asset(ClassifyInput(kind="mesh-3d", filename="table.glb", tag="fire3d reconstructed"))
    assert mesh.target_folder == "three_d.props"
    figure = classify_asset(ClassifyInput(kind="mesh-3d", filename="korri.glb", role="figure"))
    assert figure.target_folder == "three_d.characters"
    env = classify_asset(ClassifyInput(kind="mesh-3d", filename="room.glb", role="environment", tag="reconstruct"))
    assert env.target_folder == "three_d.environments"


def test_library_delete_guard_scans_posecraft_document(client) -> None:
    from app.db import SessionLocal
    from app.scene_references.service import _entity_refs_for_asset

    project_id = _create_project(client, "Delete Guard")
    scene = {
        "schemaVersion": 3,
        "currentScene": migrate_scene_to_current(
            {
                "schemaVersion": 3,
                "name": "Hall",
                "revision": 2,
                "figures": [
                    {
                        "id": "fig-custom",
                        "name": "Imported",
                        "archetypeId": "adult-male",
                        "colorId": "seaglass",
                        "position": {"x": 0, "z": 0},
                        "rotationY": 0,
                        "scale": 1,
                        "pose": {},
                        "customAssetId": "mesh-figure-1",
                    }
                ],
                "objects": [
                    {
                        "id": "obj-table",
                        "name": "table",
                        "source": "reconstructed",
                        "meshAssetId": "mesh-table-1",
                        "position": {"x": 0, "y": 0, "z": 0},
                    }
                ],
            }
        ),
        "snapshots": [
            {
                "snapshotId": "snap-1",
                "projectId": project_id,
                "sceneId": "scene-1",
                "name": "Shot 01",
                "imageAssetId": "img-previz-1",
                "sceneRevision": 2,
            }
        ],
    }
    assert client.put(f"/api/posecraft/projects/{project_id}/scene", json=scene).status_code == 200
    db = SessionLocal()
    try:
        figure_refs = _entity_refs_for_asset(db, project_id, "mesh-figure-1")
        object_refs = _entity_refs_for_asset(db, project_id, "mesh-table-1")
        snap_refs = _entity_refs_for_asset(db, project_id, "img-previz-1")
    finally:
        db.close()
    assert any(ref["field"] == "customAssetId" for ref in figure_refs)
    assert any(ref["field"] == "meshAssetId" for ref in object_refs)
    assert any(ref["field"] == "imageAssetId" for ref in snap_refs)
