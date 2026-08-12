from __future__ import annotations

import uuid
from pathlib import Path

from PIL import Image

from app.codirector.tools.definitions import ToolContext
from app.codirector.tools.handlers import environment_reference_sheet as ers_tools
from app.environment_reference_sheet.contracts import DirectionalViewRecord
from app.environment_reference_sheet import orchestrator, store


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(client, name: str = "ERS Test Project") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def _create_scene(project_id: str, name: str = "Atrium") -> str:
    from app.db import Scene

    db = _session()
    try:
        scene = Scene(id=str(uuid.uuid4()), project_id=project_id, name=name)
        db.add(scene)
        db.commit()
        return scene.id
    finally:
        db.close()


def _insert_image_asset(project_id: str, filename: str, isolated_data_dir: Path) -> str:
    from app.db import Asset

    asset_id = str(uuid.uuid4())
    dest = isolated_data_dir / "projects" / project_id / "assets" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (320, 180), color=(48, 76, 120)).save(dest)
    db = _session()
    try:
        asset = Asset(
            id=asset_id,
            project_id=project_id,
            kind="image",
            tag=filename.rsplit(".", 1)[0],
            filename=filename,
            path=str(dest),
        )
        db.add(asset)
        db.commit()
        return asset_id
    finally:
        db.close()


def test_ers_store_round_trip() -> None:
    project_id = f"proj-{uuid.uuid4()}"
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium, hanging gardens, cool daylight, reflective stone, quiet research campus.",
        scene_id="scene-1",
    )
    store.save_sheet(sheet)
    loaded = store.load_sheet(project_id, sheet.sheetId)
    assert loaded is not None
    assert loaded.name == "Helios Research Atrium"
    assert loaded.creationPlan.creatorPreview
    assert loaded.revisionLaw.requireNorthLockBeforeViews is True


def test_ers_attach_spatial_map_builds_north_locked_views(client) -> None:
    project_id = _create_project(client)
    scene_id = _create_scene(project_id)
    response = client.post(
        f"/api/spatial-map/projects/{project_id}/maps",
        json={
            "title": "Atrium Spatial Map",
            "sceneId": scene_id,
            "masterEnvironmentPrompt": "Glass-roofed research atrium with layered gardens and cool daylight.",
        },
    )
    assert response.status_code == 200
    spatial_map_id = response.json()["document"]["id"]

    db = _session()
    try:
        sheet = orchestrator.create_sheet(
            project_id=project_id,
            name="Helios Research Atrium",
            description="Glass-roofed atrium, hanging gardens, cool daylight, reflective stone, quiet research campus.",
            scene_id=scene_id,
        )
        sheet = orchestrator.attach_spatial_map(db, sheet, spatial_map_id=spatial_map_id)
        assert sheet.spatialMap is not None
        assert sheet.spatialMap.northLockDirection == "north"
        assert [view.direction for view in sheet.directionalViews] == ["north", "east", "south", "west"]
        assert all(view.prompt for view in sheet.directionalViews)
    finally:
        db.close()


def test_ers_export_registers_assets(client, isolated_data_dir: Path) -> None:
    project_id = _create_project(client)
    north = _insert_image_asset(project_id, "north.png", isolated_data_dir)
    east = _insert_image_asset(project_id, "east.png", isolated_data_dir)
    south = _insert_image_asset(project_id, "south.png", isolated_data_dir)
    west = _insert_image_asset(project_id, "west.png", isolated_data_dir)

    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium, hanging gardens, cool daylight, reflective stone, quiet research campus.",
    )
    sheet.directionalViews = [
        DirectionalViewRecord(
            direction=direction,
            title=f"{direction.title()} View",
            prompt=f"{direction.title()} view of the atrium.",
            sourceDirection=direction,
            approvedAssetId=asset_id,
            status="approved",
        )
        for direction, asset_id in zip(("north", "east", "south", "west"), [north, east, south, west])
    ]
    sheet = orchestrator.compose_sheet_metadata(sheet)
    store.save_sheet(sheet)

    db = _session()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        png_result = ers_tools.apply_export_sheet(ctx, {"sheetId": sheet.sheetId, "exportKind": "png"})
        html_result = ers_tools.apply_export_sheet(ctx, {"sheetId": sheet.sheetId, "exportKind": "offline_html"})
        assert png_result["export"]["status"] == "created"
        assert html_result["export"]["status"] == "created"
        reloaded = store.load_sheet(project_id, sheet.sheetId)
        assert reloaded is not None
        assert {item.exportKind for item in reloaded.exports} >= {"png", "offline_html"}
        assert any(Path(item.filePath or "").is_file() for item in reloaded.exports if item.exportKind == "png")
        assert any(Path(item.filePath or "").is_file() for item in reloaded.exports if item.exportKind == "offline_html")
    finally:
        db.close()
