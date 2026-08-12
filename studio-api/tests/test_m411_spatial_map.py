from __future__ import annotations

import uuid
from pathlib import Path

from app.spatial_map.collage import generate_360_plan


def _create_project(client, name: str = "Spatial Map Test") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_scene(project_id: str, name: str = "Scene A") -> str:
    from app.db import Scene

    db = _session()
    try:
        scene = Scene(id=str(uuid.uuid4()), project_id=project_id, name=name)
        db.add(scene)
        db.commit()
        return scene.id
    finally:
        db.close()


def _insert_asset(project_id: str, kind: str, filename: str, isolated_data_dir: Path) -> str:
    from app.db import Asset

    asset_id = str(uuid.uuid4())
    dest = isolated_data_dir / "assets" / project_id / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"spatial-map-test")
    db = _session()
    try:
        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind=kind,
            tag=kind,
            filename=filename,
            path=str(dest),
        )
        db.add(asset)
        db.commit()
    finally:
        db.close()
    return asset_id


def test_spatial_map_limits_enforced(client) -> None:
    project_id = _create_project(client)
    create = client.post(f"/api/spatial-map/projects/{project_id}/maps", json={"title": "Stage"})
    assert create.status_code == 200
    document_id = create.json()["document"]["id"]

    for index in range(4):
        res = client.post(
            f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
            json={"characterId": f"char-{index}", "label": f"Character {index}", "x": index, "z": -index},
        )
        assert res.status_code == 200
    over = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={"characterId": "char-over", "label": "Too Many"},
    )
    assert over.status_code == 409
    assert over.json()["detail"]["code"] == "CHARACTER_LIMIT_REACHED"

    for index in range(4):
        res = client.post(
            f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
            json={"label": f"Prop {index}", "propId": f"prop-{index}"},
        )
        assert res.status_code == 200
    over = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Too Many Prop"},
    )
    assert over.status_code == 409
    assert over.json()["detail"]["code"] == "PROP_LIMIT_REACHED"

    for index in range(8):
        res = client.post(
            f"/api/spatial-map/projects/{project_id}/maps/{document_id}/cameras",
            json={"label": f"Cam {index}", "yawDegrees": index * 45},
        )
        assert res.status_code == 200
    over = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/cameras",
        json={"label": "Too Many Camera"},
    )
    assert over.status_code == 409
    assert over.json()["detail"]["code"] == "CAMERA_LIMIT_REACHED"


def test_spatial_map_reference_bundle_and_assignment(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    scene_id = _create_scene(project_id)
    background_asset_id = _insert_asset(project_id, "environment", "panorama.png", isolated_data_dir)
    character_asset_id = _insert_asset(project_id, "image", "hero.png", isolated_data_dir)

    create = client.post(
        f"/api/spatial-map/projects/{project_id}/maps",
        json={
            "title": "Courtyard",
            "backgroundAssetId": background_asset_id,
            "masterEnvironmentPrompt": "Moonlit courtyard with warm lanterns.",
        },
    )
    assert create.status_code == 200
    document_id = create.json()["document"]["id"]

    char_res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={
            "characterId": "hero-1",
            "label": "Hero",
            "assetId": character_asset_id,
            "x": -2.0,
            "y": 1.6,
            "z": -2.5,
        },
    )
    assert char_res.status_code == 200
    character_placement_id = char_res.json()["document"]["characters"][0]["id"]

    cam_res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/cameras",
        json={"label": "Hero Cam", "targetCharacterIds": ["hero-1"], "hero": True, "lensMm": 50},
    )
    assert cam_res.status_code == 200

    collage_res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/collage",
        json={"masterEnvironmentPrompt": "Moonlit courtyard with warm lanterns."},
    )
    assert collage_res.status_code == 200

    view_res = client.put(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/collage/views/front",
        json={"assetId": background_asset_id, "prompt": "Lanterns and fountain", "status": "captured"},
    )
    assert view_res.status_code == 200

    bundle = client.get(f"/api/spatial-map/projects/{project_id}/maps/{document_id}/reference-bundle?target=image")
    assert bundle.status_code == 200
    payload = bundle.json()["bundle"]
    assert payload["backgroundAssetId"] == background_asset_id
    assert payload["target"] == "image"
    assert payload["primaryCamera"]["label"] == "Hero Cam"
    assert background_asset_id in payload["referenceAssetIds"]
    assert character_asset_id in payload["referenceAssetIds"]
    assert payload["creatorPositionLabels"][character_placement_id] == "foreground left"

    assigned = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/assign-scene",
        json={"sceneId": scene_id, "locationId": "courtyard-main"},
    )
    assert assigned.status_code == 200
    document = assigned.json()["document"]
    assert document["sceneId"] == scene_id
    assert document["locationId"] == "courtyard-main"
    assert scene_id in document["assignedSceneIds"]


def test_generate_360_plan_uses_one_master_prompt() -> None:
    plan = generate_360_plan(
        master_environment_prompt="Ancient observatory under aurora skies.",
        include_characters=False,
        camera_height_meters=1.7,
        lens_mm=24.0,
    )
    assert plan["masterEnvironmentPrompt"] == "Ancient observatory under aurora skies."
    assert len(plan["shots"]) == 8
    assert [shot["yawDegrees"] for shot in plan["shots"]] == [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
    assert all("Same environment" in shot["prompt"] for shot in plan["shots"])
    assert all("24mm" in shot["prompt"] for shot in plan["shots"])


def test_spatial_map_variant_tracks_source(client) -> None:
    project_id = _create_project(client)
    create = client.post(f"/api/spatial-map/projects/{project_id}/maps", json={"title": "Base Blocking"})
    assert create.status_code == 200
    document_id = create.json()["document"]["id"]

    variant = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/variants",
        json={"name": "Wide Variant", "notesSuffix": "Use for the crane move."},
    )
    assert variant.status_code == 200
    variant_doc = variant.json()["document"]
    assert variant_doc["variantOfId"] == document_id
    assert variant_doc["title"] == "Wide Variant"
    assert "Use for the crane move." in variant_doc["notes"]

    source = client.get(f"/api/spatial-map/projects/{project_id}/maps/{document_id}")
    assert source.status_code == 200
    assert variant_doc["id"] in source.json()["document"]["variantIds"]


def test_image_compile_preview_uses_spatial_reference_bundle(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client, "Spatial Image Preview")
    background_asset_id = _insert_asset(project_id, "image", "spatial_bg.png", isolated_data_dir)
    character_asset_id = _insert_asset(project_id, "image", "spatial_hero.png", isolated_data_dir)

    create = client.post(
        f"/api/spatial-map/projects/{project_id}/maps",
        json={
            "title": "Stage Blocking",
            "backgroundAssetId": background_asset_id,
            "masterEnvironmentPrompt": "Warm apartment kitchen with morning backlight.",
        },
    )
    assert create.status_code == 200
    document = create.json()["document"]
    document_id = document["id"]

    char_res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={
            "characterId": "korri",
            "label": "Korri",
            "assetId": character_asset_id,
            "x": -2.2,
            "y": 1.6,
            "z": -1.8,
            "pose": "leaning in",
            "expression": "skeptical",
        },
    )
    assert char_res.status_code == 200
    cam_res = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/cameras",
        json={"label": "Hero Cam", "hero": True, "shotType": "wide", "lensMm": 35},
    )
    assert cam_res.status_code == 200
    camera_id = cam_res.json()["document"]["cameras"][0]["id"]

    preview = client.post(
        f"/api/image-studio/projects/{project_id}/cinematic/compile-preview",
        json={
            "projectId": project_id,
            "prompt": "Korri pauses by the table.",
            "controls": {"aspectRatio": "16:9", "shotIntent": "medium", "category": "storyboard"},
            "spatialMapId": document_id,
            "spatialCameraId": camera_id,
        },
    )
    assert preview.status_code == 200
    body = preview.json()["imageProductBody"]
    assert body["spatialMapId"] == document_id
    assert body["spatialMapVersion"] == document["updatedAt"]
    assert body["spatialCameraId"] == camera_id
    assert background_asset_id in body["referenceAssetIds"]
    assert character_asset_id in body["referenceAssetIds"]
    assert "spatial" in body["creativeContext"]
    assert "Korri" in body["creativeContext"]["spatial"]["summary"]


def test_storyboard_workspace_preserves_spatial_linkage(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client, "Spatial Storyboard")
    asset_id = _insert_asset(project_id, "image", "storyboard_spatial.png", isolated_data_dir)

    add = client.post(
        f"/api/storyboard-studio/projects/{project_id}/add-image",
        json={
            "assetId": asset_id,
            "prompt": "Storyboard from spatial map",
            "label": "Panel A",
            "spatialMapId": "map-story",
            "spatialMapVersion": "2026-08-01T20:00:00Z",
        },
    )
    assert add.status_code == 200
    panel_id = add.json()["panelId"]

    workspace = client.get(f"/api/storyboard-studio/projects/{project_id}/workspace")
    assert workspace.status_code == 200
    panel = next(item for item in workspace.json()["panels"] if item["panelId"] == panel_id)
    assert panel["spatialMapId"] == "map-story"
    assert panel["spatialMapVersion"] == "2026-08-01T20:00:00Z"


def test_spatial_map_move_delete_and_version_bump(client) -> None:
    project_id = _create_project(client)
    create = client.post(
        f"/api/spatial-map/projects/{project_id}/maps",
        json={"title": "Blocking Pass", "masterEnvironmentPrompt": "Warm lantern light across the square."},
    )
    assert create.status_code == 200
    document = create.json()["document"]
    document_id = document["id"]
    assert document["version"] == "1"

    updated = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}",
        json={"notes": "Stage the trio near the front.", "tags": ["hero", "lanterns"]},
    )
    assert updated.status_code == 200
    document = updated.json()["document"]
    assert document["version"] == "2"
    assert document["tags"] == ["hero", "lanterns"]

    placed_character = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters",
        json={"characterId": "hero-1", "label": "Hero", "x": -1.0, "z": -2.0},
    )
    assert placed_character.status_code == 200
    document = placed_character.json()["document"]
    placement_id = document["characters"][0]["id"]
    assert document["version"] == "3"

    moved_character = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/characters/{placement_id}",
        json={"x": 1.5, "z": 2.25, "yawDegrees": 45},
    )
    assert moved_character.status_code == 200
    document = moved_character.json()["document"]
    assert document["version"] == "4"
    assert document["characters"][0]["x"] == 1.5
    assert document["characters"][0]["z"] == 2.25
    assert document["characters"][0]["yawDegrees"] == 45

    placed_prop = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props",
        json={"label": "Lantern", "x": 0.0, "z": -1.0},
    )
    assert placed_prop.status_code == 200
    document = placed_prop.json()["document"]
    prop_id = document["props"][0]["id"]
    assert document["version"] == "5"

    moved_prop = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{prop_id}",
        json={"category": "lighting", "x": 2.0},
    )
    assert moved_prop.status_code == 200
    document = moved_prop.json()["document"]
    assert document["version"] == "6"
    assert document["props"][0]["category"] == "lighting"
    assert document["props"][0]["x"] == 2.0

    created_camera = client.post(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/cameras",
        json={"label": "Hero Cam", "hero": True, "yawDegrees": 0},
    )
    assert created_camera.status_code == 200
    document = created_camera.json()["document"]
    camera_id = document["cameras"][0]["id"]
    assert document["version"] == "7"

    updated_camera = client.patch(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/cameras/{camera_id}",
        json={"lensMm": 50, "yawDegrees": 90},
    )
    assert updated_camera.status_code == 200
    document = updated_camera.json()["document"]
    assert document["version"] == "8"
    assert document["cameras"][0]["lensMm"] == 50
    assert document["cameras"][0]["yawDegrees"] == 90

    warnings = client.post(f"/api/spatial-map/projects/{project_id}/maps/{document_id}/consistency-check")
    assert warnings.status_code == 200
    assert warnings.json()["warnings"] == []

    removed_prop = client.delete(
        f"/api/spatial-map/projects/{project_id}/maps/{document_id}/props/{prop_id}"
    )
    assert removed_prop.status_code == 200
    document = removed_prop.json()["document"]
    assert document["version"] == "9"
    assert document["props"] == []
