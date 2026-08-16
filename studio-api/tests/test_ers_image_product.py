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
    document = SpatialMapDocument(
        projectId=project_id,
        id=spatial_map_id,
        backgroundAssetId="atlas-ref-1",
    )
    _patch_handler(monkeypatch, sheet, document, captured)

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
        assert body["width"] == 2560
        assert body["height"] == 1440
        # ERS is image-to-image: the authoritative source rides with the job.
        assert body.get("sourceAssetId") == "atlas-ref-1"
        assert body.get("source_asset_id") == "atlas-ref-1"
        assert body.get("referenceImage") == "atlas-ref-1"
        assert body["creativeContext"]["operationIntent"] == "image_to_image_reference"
        assert body.get("forceWorkflowKey") == "qwen2512.ref"
        assert body.get("allow_force_workflow_key") is True
        assert body["creativeContext"]["referenceGrounding"]["mode"] == "pixel"
        assert "zimage.txt2img" not in str(body)
    assert result["purpose"] == "environment_reference_sheet"
    assert len(result["child_jobs"]) == 1
    assert result["child_jobs"][0]["status"] == "queued"


def test_ers_generate_blocks_non_i2i_hosted_model(monkeypatch) -> None:
    """Binding law: ERS requires an image-to-image-capable generator. A hosted
    model without an ERS-authorized I2I path is blocked, never silently run as
    T2I and never substituted."""
    import pytest

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

    with pytest.raises(RuntimeError, match="image-to-image"):
        ers_generate.handle(
            db=None,
            project_id=project_id,
            execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
            spatial_map_id=spatial_map_id,
            hosted_model_id="nano-banana-kie",
            source="api",
        )
    assert not captured


def test_ers_generate_blocks_t2i_only_local_family(monkeypatch) -> None:
    """Binding law: a text-to-image-only local family (flux) is blocked for ERS
    — never run as T2I and never silently routed to another provider."""
    import pytest

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

    with pytest.raises(RuntimeError, match="image-to-image"):
        ers_generate.handle(
            db=None,
            project_id=project_id,
            execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
            spatial_map_id=spatial_map_id,
            source="local",
            model="flux",
            model_family_preference="flux",
        )
    assert not captured


def test_ers_generate_gpt_image2_pixel_grounding(monkeypatch) -> None:
    """Explicit GPT Image 2 satisfies the ERS image-to-image contract via the
    Kie input_urls pixel path. Source pixels stay on the body; T2I is refused.
    """
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
        kie_image_model_id="gpt-image-2-image-to-image",
        source="api",
    )

    assert captured
    for body in captured:
        assert body["operation"] == "image.generate"
        assert body.get("sourceAssetId") == "atlas-ref-1"
        assert body.get("source_asset_id") == "atlas-ref-1"
        assert body.get("kieImageModelId") == "gpt-image-2-image-to-image"
        assert "text-to-image" not in str(body.get("kieImageModelId") or "")
        assert "not pixel image-to-image" not in str(body.get("prompt") or "")
        assert body["creativeContext"]["authoritativeSourceAssetId"] == "atlas-ref-1"
        assert body["creativeContext"]["resolvedProvider"] == "kie"
        urls = body.get("input_urls") or []
        assert urls, "explicit GPT Image 2 with atlas lineage must attach input_urls"
        assert any("atlas-ref-1" in u for u in urls)
        assert body["creativeContext"]["referenceGrounding"]["mode"] == "pixel"
        official = str(body["creativeContext"].get("resolvedOfficialModelId") or "")
        assert "text-to-image" not in official
        assert "image-to-image" in official or official == ""


def test_ers_generate_blocks_model_without_i2i(monkeypatch) -> None:
    """Binding law: no silent T2I for ERS. A model with no ERS-authorized I2I
    path raises an honest creator-readable block."""
    import pytest

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

    with pytest.raises(RuntimeError, match="image-to-image"):
        ers_generate.handle(
            db=None,
            project_id=project_id,
            execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
            spatial_map_id=spatial_map_id,
            hosted_model_id="nano-banana-kie",
            source="api",
        )
    assert not captured


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

def test_ers_qwen2512_with_atlas_enqueues_i2i_ref(monkeypatch) -> None:
    project_id = f"proj-{uuid.uuid4()}"
    spatial_map_id = f"map-{uuid.uuid4()}"
    sheet = _sheet(project_id, spatial_map_id)
    captured: list[dict] = []
    atlas_id = "caa72759-d965-41f9-b1d5-77cdcf9b9614"
    document = SpatialMapDocument(
        projectId=project_id,
        id=spatial_map_id,
        backgroundAssetId=atlas_id,
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
    assert body["creativeContext"]["operationIntent"] == "image_to_image_reference"
    assert body.get("edit") in (None, False)
    # The authoritative source image rides the job as real pixel conditioning.
    assert body.get("source_asset_id") == atlas_id
    assert body.get("sourceAssetId") == atlas_id
    assert body.get("referenceImage") == atlas_id
    assert body.get("forceWorkflowKey") == "qwen2512.ref"
    assert body.get("allow_force_workflow_key") is True
    assert body["creativeContext"]["resolvedProvider"] == "local"
    assert body["creativeContext"]["resolvedWorkflowKey"] == "qwen2512.ref"
    assert body["creativeContext"]["referenceGrounding"]["mode"] == "pixel"
    assert "zimage.ref_edit" not in str(body)
    assert "zimage" not in str(body["creativeContext"].get("resolvedWorkflowKey") or "")
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is True
    assert cap["workflowKey"] == "qwen2512.ref"

    from app.image_product.compile import compile_image_request

    # Source pixels + a stray edit flag must not flip ERS into an edit request
    # or zimage.ref_edit; the ref workflow stays pinned.
    compiled = compile_image_request(
        project_id,
        {
            **body,
            "source_asset_id": atlas_id,
            "sourceAssetId": atlas_id,
            "edit": True,
            "operation": "image.edit",
            "lockModelFamily": True,
        },
    )
    intent = compiled["imageIntent"]
    runtime = compiled["imageRuntime"]
    assert intent["operation"] == "image.generate"
    assert intent.get("sourceAssetId") == atlas_id
    assert runtime.get("canExecute") is True
    assert "zimage" not in str(runtime.get("workflowKey") or "")
    selected = str(runtime.get("workflowKey") or compiled.get("contract", {}).get("workflow_key") or "")
    assert selected == "qwen2512.ref"
    assert selected != "zimage.ref_edit"
    assert "zimage" not in selected

def test_compile_ers_qwen2512_source_stays_i2i_not_edit() -> None:
    """Phase 2: ERS + Qwen + source pixels is qwen2512.ref, not T2I and not edit."""
    from app.image_product.compile import compile_image_request
    from app.image_product.resolve import resolve_image_capability

    atlas_id = "caa72759-d965-41f9-b1d5-77cdcf9b9614"
    body = {
        "prompt": "Environment reference sheet of one locked environment.",
        "purpose": "environment_reference_sheet",
        "source": "local",
        "model": "qwen2512",
        "modelFamilyPreference": "qwen2512",
        "lockModelFamily": True,
        "operation": "image.edit",
        "edit": True,
        "source_asset_id": atlas_id,
        "sourceAssetId": atlas_id,
        "referenceImage": atlas_id,
        "width": 1280,
        "height": 720,
    }
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is True
    assert cap["workflowKey"] == "qwen2512.ref"
    compiled = compile_image_request("proj-ers-i2i", body)
    assert compiled["imageIntent"]["operation"] == "image.generate"
    assert compiled["imageIntent"].get("sourceAssetId") == atlas_id
    assert compiled["imageIntent"]["purpose"] == "environment_reference_sheet"
    runtime = compiled["imageRuntime"]
    assert runtime.get("canExecute") is True
    key = str(runtime.get("workflowKey") or (compiled.get("contract") or {}).get("workflow_key") or "")
    assert key == "qwen2512.ref"
    assert "txt2img" not in key
    assert "zimage" not in key
    assert key != "zimage.ref_edit"


def test_compile_ers_gpt_image2_uses_i2i_not_t2i() -> None:
    from app.image_product.compile import compile_image_request
    from app.image_product.resolve import resolve_image_capability

    atlas_id = "atlas-ref-1"
    body = {
        "prompt": "Environment reference sheet of one locked environment.",
        "purpose": "environment_reference_sheet",
        "source": "api",
        "hostedModelId": "gpt-image-2-kie",
        "kieImageModelId": "gpt-image-2-text-to-image",
        "sourceAssetId": atlas_id,
        "source_asset_id": atlas_id,
        "input_urls": [f"https://api-beta.adeptui.org/api/assets/{atlas_id}/file"],
        "width": 2560,
        "height": 1440,
        "lockModelFamily": True,
    }
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is True
    assert cap["officialModelId"] == "gpt-image-2-image-to-image"
    assert "text-to-image" not in cap["officialModelId"]
    assert cap["workflowKey"] == "kie:gpt-image-2-image-to-image"
    compiled = compile_image_request("proj-ers-gpt-i2i", body)
    assert compiled["imageIntent"]["sourceAssetId"] == atlas_id
    assert compiled["imageIntent"]["operation"] == "image.generate"
    runtime = compiled.get("imageRuntime") or {}
    official = str(
        compiled.get("kieImageModelId")
        or runtime.get("officialModelId")
        or cap["officialModelId"]
    )
    assert official == "gpt-image-2-image-to-image"

