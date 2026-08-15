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


def test_ers_generate_does_not_access_imagegenerationplan_prompt() -> None:
    """ers.generate must not read ImageGenerationPlan.prompt."""
    import inspect

    from app.codirector.capabilities.handlers import ers_generate
    from app.image_pipeline.orchestrator import prepare_plan

    src = inspect.getsource(ers_generate)
    handle_src = inspect.getsource(ers_generate.handle)
    assert "plan.prompt" not in src
    assert "image_core_prompt" in src
    assert "plan.prompt" not in handle_src
    contract_plan = prepare_plan(
        {
            "projectId": "proj-ers-contract",
            "prompt": "North view of the glass-roofed atrium.",
            "purpose": "environment_reference_sheet",
        }
    )
    try:
        unused = contract_plan.prompt  # noqa: F841
        raise AssertionError("ImageGenerationPlan.prompt should not exist")
    except AttributeError:
        pass
    assert contract_plan.request.prompt


def test_ers_generate_enqueues_image_product_jobs(monkeypatch) -> None:
    """ERS enqueues one image-product job (not hardcoded zimage.txt2img)."""
    from app.codirector.capabilities.handlers import ers_generate
    from app.environment_reference_sheet.contracts import SpatialMapReference
    from app.spatial_map.schemas import SpatialMapDocument

    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    execution_id = "279a7474-d93c-4dc7-8936-4b649ef06255"
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium, hanging gardens, cool daylight.",
        scene_id="scene-1",
    )
    sheet.spatialMap = SpatialMapReference(mapId=spatial_map_id, northLockDirection="north")
    captured: list[dict] = []

    def _fake_enqueue(db, enqueue_project_id, body, scene_id=None):
        captured.append(dict(body))
        return {"jobId": "job-ers-one", "jobs": [{"jobId": "job-ers-one"}]}

    monkeypatch.setattr("app.environment_reference_sheet.store.list_sheets", lambda pid: [sheet])
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.attach_spatial_map",
        lambda db, current, spatial_map_id: current,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.compose_sheet_metadata",
        lambda current: current,
    )
    monkeypatch.setattr(ers_generate, "_enqueue_ers_image_product", _fake_enqueue)
    monkeypatch.setattr(
        "app.spatial_map.service.get_document",
        lambda db, pid, mid: SpatialMapDocument(projectId=pid, id=mid),
    )
    monkeypatch.setattr("app.spatial_map.ers_persistence.save_ers_package", lambda *a, **k: None)
    monkeypatch.setattr("app.environment_reference_sheet.store.save_sheet", lambda current: None)

    result = ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id=execution_id,
        spatial_map_id=spatial_map_id,
        scene_id="scene-1",
    )
    assert len(captured) == 1
    assert len(result["job_ids"]) == 1
    assert len(result["child_jobs"]) == 1
    body = captured[0]
    assert body["purpose"] == "environment_reference_sheet"
    assert (body.get("creativeContext") or {}).get("ersPackageId") == result["ers_package_id"]
    assert (body.get("creativeContext") or {}).get("environmentReferenceSheetId") == sheet.sheetId
    assert body.get("modelFamilyPreference") != "zimage"
    assert "zimage.txt2img" not in str(body)
    assert (body.get("creativeContext") or {}).get("workflowKey") != "zimage.txt2img"
    assert result["child_jobs"][0]["job_id"] == "job-ers-one"
    assert result["child_jobs"][0]["status"] == "queued"
    assert result["purpose"] == "environment_reference_sheet"
    assert result["sheet_id"] == sheet.sheetId
    assert result["ers_package_id"]
    assert result["spatial_map_id"] == spatial_map_id


def test_ers_compile_uses_image_product_not_hardcoded_zimage() -> None:
    from app.codirector.capabilities.handlers.ers_generate import (
        _ERS_PURPOSE,
        _creator_model_body,
        _pin_resolved_capability,
    )
    from app.image_product.compile import compile_image_request
    from app.image_product.resolve import resolve_image_capability

    body = {
        "prompt": "Café layout / spatial reference of the atrium.",
        "purpose": _ERS_PURPOSE,
        "operation": "image.generate",
        "lockModelFamily": True,
        "creativeContext": {"objective": _ERS_PURPOSE},
        **_creator_model_body(hosted_model_id="nano-banana-kie", source="api"),
    }
    assert body["purpose"] == "environment_reference_sheet"
    assert "zimage.txt2img" not in str(body)
    assert body.get("modelFamilyPreference") != "zimage"
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is True
    assert cap["provider"] == "kie"
    assert cap["adapter"] == "kie"
    assert cap["workflowKey"] != "zimage.txt2img"
    pinned = _pin_resolved_capability(dict(body))
    assert pinned["creativeContext"]["resolvedWorkflowKey"] == "kie:nano-banana-2"
    assert pinned["creativeContext"]["workflowKey"] != "zimage.txt2img"
    compiled = compile_image_request("proj-ers-pin", body)
    runtime = compiled["imageRuntime"]
    assert runtime["provider"] == "kie"
    assert runtime["workflowKey"] == "kie:nano-banana-2"
    assert runtime["workflowKey"] != "zimage.txt2img"


def test_ers_body_local_flux_is_not_kie() -> None:
    from app.codirector.capabilities.handlers.ers_generate import (
        _ERS_PURPOSE,
        _creator_model_body,
        _pin_resolved_capability,
    )
    from app.image_product.resolve import resolve_image_capability

    body = {
        "prompt": "Café layout / spatial reference of the atrium.",
        "purpose": _ERS_PURPOSE,
        "operation": "image.generate",
        "forceWorkflowKey": "flux.txt2img",
        "allow_force_workflow_key": True,
        "lockModelFamily": True,
        "creativeContext": {"objective": _ERS_PURPOSE},
        **_creator_model_body(
            model="flux",
            model_family_preference="flux",
            source="local",
        ),
    }
    assert "zimage.txt2img" not in str(body)
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is True
    assert cap["provider"] == "local"
    assert cap["provider"] != "kie"
    assert not str(cap.get("workflowKey") or "").startswith("kie:")
    pinned = _pin_resolved_capability(dict(body))
    assert pinned["creativeContext"].get("resolvedProvider") == "local"
    assert not str(pinned["creativeContext"].get("resolvedWorkflowKey") or "").startswith("kie:")


def test_ers_handle_forwards_selected_model_not_zimage(monkeypatch) -> None:
    from app.codirector.capabilities.handlers import ers_generate
    from app.environment_reference_sheet.contracts import SpatialMapReference
    from app.spatial_map.schemas import SpatialMapDocument

    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    execution_id = "279a7474-d93c-4dc7-8936-4b649ef06255"
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium.",
        scene_id="scene-1",
    )
    sheet.spatialMap = SpatialMapReference(mapId=spatial_map_id, northLockDirection="north")
    captured: list[dict] = []

    def _fake_enqueue(db, enqueue_project_id, body, scene_id=None):
        captured.append(dict(body))
        return {"jobId": "job-ers-one", "jobs": [{"jobId": "job-ers-one"}]}

    monkeypatch.setattr("app.environment_reference_sheet.store.list_sheets", lambda pid: [sheet])
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.attach_spatial_map",
        lambda db, current, spatial_map_id: current,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.compose_sheet_metadata",
        lambda current: current,
    )
    monkeypatch.setattr(ers_generate, "_enqueue_ers_image_product", _fake_enqueue)
    monkeypatch.setattr(
        "app.spatial_map.service.get_document",
        lambda db, pid, mid: SpatialMapDocument(projectId=pid, id=mid),
    )
    monkeypatch.setattr("app.spatial_map.ers_persistence.save_ers_package", lambda *a, **k: None)
    monkeypatch.setattr("app.environment_reference_sheet.store.save_sheet", lambda current: None)

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id=execution_id,
        spatial_map_id=spatial_map_id,
        scene_id="scene-1",
        hosted_model_id="nano-banana-kie",
        source="api",
    )
    assert len(captured) == 1
    body = captured[0]
    assert body["purpose"] == "environment_reference_sheet"
    assert body.get("hostedModelId") == "nano-banana-kie"
    assert body.get("modelFamilyPreference") != "zimage"
    assert (body.get("creativeContext") or {}).get("workflowKey") != "zimage.txt2img"
    assert "zimage.txt2img" not in str(body)
    assert (body.get("creativeContext") or {}).get("resolvedProvider") == "kie"


def test_ers_persist_composite_sets_has_reference(monkeypatch) -> None:
    """Persisting the one-job Library asset sets ers_composite_asset_id."""
    from app.codirector.capabilities.handlers.ers_generate import persist_ers_composite_asset
    from app.scene_creator.ers_resolver import resolve_ers_for_sheet
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage

    project_id = f"proj-{uuid.uuid4()}"
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium.",
        scene_id="scene-1",
    )
    store.save_sheet(sheet)
    package = EnvironmentReferencePackage(
        project_id=project_id,
        scene_layout_id="map-ers",
        directional_assets={"north": None, "east": None, "south": None, "west": None},
        metadata={"sheet_id": sheet.sheetId},
    )
    saved = {package.id: package}

    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.load_ers_package",
        lambda db, pid, pkg_id: saved.get(pkg_id),
    )
    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.list_ers_packages",
        lambda db, pid: list(saved.values()),
    )

    def _save(db, pid, pkg, provenance="ers_generate"):
        saved[pkg.id] = pkg

    monkeypatch.setattr("app.spatial_map.ers_persistence.save_ers_package", _save)

    result = persist_ers_composite_asset(
        db=object(),
        project_id=project_id,
        sheet_id=sheet.sheetId,
        asset_id="asset-ers-composite-1",
        package_id=package.id,
    )
    assert result["ers_composite_asset_id"] == "asset-ers-composite-1"
    assert saved[package.id].ers_composite_asset_id == "asset-ers-composite-1"
    reloaded = store.load_sheet(project_id, sheet.sheetId)
    assert reloaded is not None
    assert reloaded.ers_composite_asset_id == "asset-ers-composite-1"
    assert reloaded.composition.renderedAssetIds.get("composite") == "asset-ers-composite-1"
    resolved, _runtime = resolve_ers_for_sheet(
        object(), project_id, sheet.sheetId, persist_runtime=False
    )
    assert resolved.ers_composite_asset_id == "asset-ers-composite-1"
    has_reference = bool(
        any((resolved.directional_assets or {}).values()) or resolved.ers_composite_asset_id
    )
    assert has_reference is True


def test_ers_persist_accepts_worker_positional_args(monkeypatch) -> None:
    """queue_worker calls persist(db, project_id, sheet_id=..., asset_id=...)."""
    from app.codirector.capabilities.handlers.ers_generate import persist_ers_composite_asset
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage

    project_id = f"proj-{uuid.uuid4()}"
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium.",
        scene_id="scene-1",
    )
    store.save_sheet(sheet)
    package = EnvironmentReferencePackage(
        project_id=project_id,
        scene_layout_id="map-ers",
        directional_assets={"north": None, "east": None, "south": None, "west": None},
        metadata={"sheet_id": sheet.sheetId},
    )
    saved = {package.id: package}

    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.load_ers_package",
        lambda db, pid, pkg_id: saved.get(pkg_id),
    )
    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.list_ers_packages",
        lambda db, pid: list(saved.values()),
    )

    def _save(db, pid, pkg, provenance="ers_generate"):
        saved[pkg.id] = pkg

    monkeypatch.setattr("app.spatial_map.ers_persistence.save_ers_package", _save)

    result = persist_ers_composite_asset(
        object(),
        project_id,
        sheet_id=sheet.sheetId,
        asset_id="asset-ers-worker-1",
        package_id=package.id,
    )
    assert result["has_reference"] is True
    assert result["ers_composite_asset_id"] == "asset-ers-worker-1"
    reloaded = store.load_sheet(project_id, sheet.sheetId)
    assert reloaded is not None
    assert reloaded.ers_composite_asset_id == "asset-ers-worker-1"
    assert reloaded.composition.renderedAssetIds.get("composite") == "asset-ers-worker-1"
    assert saved[package.id].ers_composite_asset_id == "asset-ers-worker-1"


def test_ers_handle_stamps_one_job_id_for_async_persist(monkeypatch) -> None:
    """handle enqueues one job and stamps the sheet so the worker can persist."""
    from app.codirector.capabilities.handlers import ers_generate
    from app.environment_reference_sheet.contracts import SpatialMapReference
    from app.spatial_map.schemas import SpatialMapDocument

    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    execution_id = "279a7474-d93c-4dc7-8936-4b649ef06255"
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium, hanging gardens, cool daylight.",
        scene_id="scene-1",
    )
    sheet.spatialMap = SpatialMapReference(mapId=spatial_map_id, northLockDirection="north")
    captured: list[dict] = []
    stamped: list = []

    def _fake_enqueue(db, enqueue_project_id, body, scene_id=None):
        captured.append(dict(body))
        return {"jobId": "job-ers-one", "jobs": [{"jobId": "job-ers-one"}]}

    monkeypatch.setattr("app.environment_reference_sheet.store.list_sheets", lambda pid: [sheet])
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.attach_spatial_map",
        lambda db, current, spatial_map_id: current,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.compose_sheet_metadata",
        lambda current: current,
    )
    monkeypatch.setattr(ers_generate, "_enqueue_ers_image_product", _fake_enqueue)
    monkeypatch.setattr(
        "app.spatial_map.service.get_document",
        lambda db, pid, mid: SpatialMapDocument(projectId=pid, id=mid),
    )
    monkeypatch.setattr("app.spatial_map.ers_persistence.save_ers_package", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.environment_reference_sheet.store.save_sheet",
        lambda current: stamped.append(current),
    )

    result = ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id=execution_id,
        spatial_map_id=spatial_map_id,
        scene_id="scene-1",
    )
    assert len(captured) == 1
    assert len(result["job_ids"]) == 1
    assert result["job_ids"] == ["job-ers-one"]
    assert stamped
    details = stamped[-1].provenance.details
    assert details.get("ers_image_job_id") == "job-ers-one"
    assert details.get("ers_package_id") == result["ers_package_id"]
