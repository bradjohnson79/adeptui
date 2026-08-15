"""ERS generate must pin through image-product, not hardcoded zimage.txt2img."""

from __future__ import annotations

import inspect
import uuid

from app.codirector.capabilities.handlers import ers_generate
from app.codirector.execution.dispatcher import _creator_readable_handler_error
from app.environment_reference_sheet import orchestrator
from app.environment_reference_sheet.contracts import (
    DirectionalViewRecord,
    SpatialMapReference,
)
from app.image_product.resolve import resolve_image_capability
from app.spatial_map.schemas import SpatialMapDocument


def _sheet(project_id: str, spatial_map_id: str):
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium, hanging gardens, cool daylight.",
        scene_id="scene-1",
    )
    sheet.spatialMap = SpatialMapReference(
        mapId=spatial_map_id,
        northLockDirection="north",
    )
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

    monkeypatch.setattr(
        "app.environment_reference_sheet.store.list_sheets",
        lambda pid: [sheet],
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.attach_spatial_map",
        lambda db, current, spatial_map_id: current,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.compose_sheet_metadata",
        lambda current: current,
    )
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue)
    monkeypatch.setattr(ers_generate, "_enqueue_ers_image_product", lambda db, pid, body, scene_id=None: {"jobId": _fake_enqueue(db, pid, body, scene_id).id})
    monkeypatch.setattr(
        "app.spatial_map.service.get_document",
        lambda db, pid, mid: document,
    )
    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.save_ers_package",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.store.save_sheet",
        lambda current: None,
    )


def test_ers_generate_source_has_no_hardcoded_zimage_txt2img() -> None:
    src = inspect.getsource(ers_generate)
    assert "zimage.txt2img" not in src
    assert 'modelFamilyPreference": "zimage"' not in src


def test_ers_generate_pins_environment_reference_sheet_purpose(monkeypatch) -> None:
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

    result = ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
        spatial_map_id=spatial_map_id,
        scene_id="scene-1",
    )

    assert len(captured) == 1
    for body in captured:
        assert body["purpose"] == "environment_reference_sheet"
        assert body["operation"] == "image.generate"
        assert body["creativeContext"]["operationIntent"] == "text_to_image"
        assert body["creativeContext"].get("workflowKey") != "zimage.txt2img"
        assert "zimage.txt2img" not in str(body)
    assert result["purpose"] == "environment_reference_sheet"
    assert len(result["child_jobs"]) == 1
    assert result["child_jobs"][0]["status"] == "queued"


def test_ers_generate_pins_creator_selected_kie_model(monkeypatch) -> None:
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

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
        spatial_map_id=spatial_map_id,
        hosted_model_id="nano-banana-kie",
        source="api",
    )

    assert captured
    for body in captured:
        assert body["purpose"] == "environment_reference_sheet"
        assert body.get("hostedModelId") == "nano-banana-kie"
        assert body.get("kieImageModelId") == "nano-banana-2"
        assert body["creativeContext"]["resolvedProvider"] == "kie"
        assert body["creativeContext"]["resolvedWorkflowKey"] == "kie:nano-banana-2"
        assert body["creativeContext"]["workflowKey"] == "kie:nano-banana-2"
        cap = resolve_image_capability(body)
        assert cap["canExecute"] is True
        assert cap["provider"] == "kie"
        assert cap["officialModelId"] == "nano-banana-2"


def test_ers_generate_local_flux_is_not_kie(monkeypatch) -> None:
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

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
        spatial_map_id=spatial_map_id,
        source="local",
        model="flux",
        model_family_preference="flux",
    )

    assert captured
    for body in captured:
        assert body.get("source") == "local"
        assert body.get("modelFamilyPreference") == "flux"
        assert not str(body.get("kieImageModelId") or "")
        assert not str(body["creativeContext"].get("resolvedWorkflowKey") or "").startswith("kie:")
        cap = resolve_image_capability(body)
        assert cap["canExecute"] is True
        assert cap["provider"] == "local"
        assert cap["provider"] != "kie"


def test_ers_generate_uses_i2i_only_when_model_supports_it(monkeypatch) -> None:
    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    sheet = _sheet(project_id, spatial_map_id)
    captured: list[dict] = []
    document = SpatialMapDocument(
        projectId=project_id,
        id=spatial_map_id,
        backgroundAssetId="atlas-ref-1",
    )
    _patch_handler(monkeypatch, sheet, document, captured)

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
        spatial_map_id=spatial_map_id,
        hosted_model_id="gpt-image-2-kie",
        source="api",
    )

    assert captured
    for body in captured:
        assert body["operation"] == "image.edit"
        assert body["creativeContext"]["operationIntent"] == "i2i"
        assert body.get("source_asset_id") == "atlas-ref-1"
        assert body["creativeContext"]["resolvedProvider"] == "kie"
        assert "image-to-image" in str(body["creativeContext"]["resolvedOfficialModelId"])


def test_ers_generate_keeps_t2i_when_model_has_no_i2i(monkeypatch) -> None:
    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    sheet = _sheet(project_id, spatial_map_id)
    captured: list[dict] = []
    document = SpatialMapDocument(
        projectId=project_id,
        id=spatial_map_id,
        backgroundAssetId="atlas-ref-1",
    )
    _patch_handler(monkeypatch, sheet, document, captured)

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
        spatial_map_id=spatial_map_id,
        hosted_model_id="nano-banana-kie",
        source="api",
    )

    assert captured
    for body in captured:
        assert body["operation"] == "image.generate"
        assert body["creativeContext"]["operationIntent"] == "text_to_image"
        assert body.get("hostedModelId") == "nano-banana-kie"
        assert body.get("kieImageModelId") == "nano-banana-2"
        assert not body.get("edit")


def test_handler_error_normalization_is_creator_readable() -> None:
    err = _creator_readable_handler_error(
        TypeError("unsupported operand type(s) for -: 'NoneType' and 'float'")
    )
    assert "HANDLER_ERROR" not in err
    assert "TypeError" in err
    assert "None" in err
    assert "could not run" in err.lower()
    assert "Details:" in err


def test_ers_generate_source_has_no_imagegenerationplan_prompt() -> None:
    src = inspect.getsource(ers_generate)
    assert "plan.prompt" not in src


def test_persist_ers_composite_sets_has_reference(monkeypatch) -> None:
    """No live generate. Persist a real Library asset id onto the sheet composite."""
    from app.environment_reference_sheet.store import load_sheet, save_sheet
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage
    from app.spatial_map.ers_persistence import persist_ers_composite_asset

    project_id = f"proj-{uuid.uuid4()}"
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name="Helios Research Atrium",
        description="Glass-roofed atrium.",
        scene_id="scene-1",
    )
    save_sheet(sheet)
    package = EnvironmentReferencePackage(
        project_id=project_id,
        scene_layout_id="map-1",
        metadata={"sheet_id": sheet.sheetId},
    )
    saved = {"package": package}

    class _Asset:
        def __init__(self) -> None:
            self.id = "asset-ers-1"
            self.project_id = project_id

    class _Query:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return _Asset()

    class _DB:
        def query(self, model):
            return _Query()

    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.save_ers_package",
        lambda db, pid, pkg, provenance="ers_generate": saved.update(package=pkg),
    )
    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.list_ers_packages",
        lambda db, pid: [saved["package"]],
    )
    monkeypatch.setattr(
        "app.spatial_map.ers_persistence.load_ers_package",
        lambda db, pid, pkg_id: saved["package"],
    )

    result = persist_ers_composite_asset(
        _DB(),
        project_id,
        sheet_id=sheet.sheetId,
        asset_id="asset-ers-1",
        package=package,
    )
    assert result["has_reference"] is True
    assert result["ers_composite_asset_id"] == "asset-ers-1"
    reloaded = load_sheet(project_id, sheet.sheetId)
    assert reloaded is not None
    assert reloaded.composition.renderedAssetIds.get("composite") == "asset-ers-1"
    from app.environment_reference_sheet.api import _summary

    summary = _summary(reloaded)
    assert summary["has_reference"] is True
    assert summary["ers_composite_asset_id"] == "asset-ers-1"
    assert saved["package"].ers_composite_asset_id == "asset-ers-1"

def test_ers_qwen2512_with_atlas_enqueues_honest_t2i(monkeypatch) -> None:
    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    sheet = _sheet(project_id, spatial_map_id)
    captured: list[dict] = []
    document = SpatialMapDocument(
        projectId=project_id,
        id=spatial_map_id,
        backgroundAssetId="caa72759-d965-41f9-b1d5-77cdcf9b9614",
    )
    _patch_handler(monkeypatch, sheet, document, captured)

    ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id="420b8388-1c09-4909-aeb6-122bc901f15b",
        spatial_map_id=spatial_map_id,
        source="local",
        model="qwen2512",
        model_family_preference="qwen2512",
    )

    assert len(captured) == 1
    body = captured[0]
    assert body["purpose"] == "environment_reference_sheet"
    assert body["operation"] == "image.generate"
    assert body["creativeContext"]["operationIntent"] == "text_to_image"
    assert body.get("edit") in (None, False)
    assert not body.get("source_asset_id")
    assert not body.get("sourceAssetId")
    assert body["creativeContext"]["resolvedProvider"] == "local"
    assert body["creativeContext"]["resolvedWorkflowKey"] == "qwen2512.txt2img"
    assert "zimage.ref_edit" not in str(body)
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is True
    assert cap["workflowKey"] == "qwen2512.txt2img"

