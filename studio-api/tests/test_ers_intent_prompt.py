"""ers.generate plan path uses Image Core intent/prompt, never ImageGenerationPlan.prompt."""

from __future__ import annotations

import inspect
import uuid
from types import SimpleNamespace

from app.codirector.capabilities.handlers import ers_generate
from app.environment_reference_sheet import orchestrator
from app.environment_reference_sheet.contracts import (
    DirectionalViewRecord,
    SpatialMapReference,
)
from app.image_pipeline.orchestrator import prepare_plan
from app.spatial_map.schemas import SpatialMapDocument


def test_ers_generate_plan_path_uses_intent_prompt_not_plan_prompt(monkeypatch) -> None:
    handler_src = inspect.getsource(ers_generate.handle)
    helper_src = inspect.getsource(ers_generate.image_core_prompt)
    module_src = inspect.getsource(ers_generate)
    assert "plan.prompt" not in handler_src
    assert "plan.prompt" not in helper_src
    assert "image_core_prompt" in handler_src
    assert "shotIntent" in helper_src
    assert "zimage.txt2img" not in module_src

    project_id = f"proj-{uuid.uuid4()}"
    contract_plan = prepare_plan(
        {
            "projectId": project_id,
            "prompt": "North view of the glass-roofed atrium.",
            "purpose": "environment_reference_sheet",
        }
    )
    try:
        unused = contract_plan.prompt  # noqa: F841
        raise AssertionError("ImageGenerationPlan.prompt should not exist")
    except AttributeError:
        pass
    assert contract_plan.shotIntent.prompt
    assert ers_generate.image_core_prompt(contract_plan) == contract_plan.shotIntent.prompt
    assert ers_generate.image_core_prompt(contract_plan) != ""

    intent_only = SimpleNamespace(
        shotIntent=SimpleNamespace(prompt="INTENT_PROMPT from shotIntent"),
        request=SimpleNamespace(prompt="REQUEST_PROMPT should lose", spatialMapPayload={}),
    )
    assert ers_generate.image_core_prompt(intent_only) == "INTENT_PROMPT from shotIntent"

    spatial_map_id = f"map-{uuid.uuid4()}"
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

    captured: list[dict] = []

    class _Job:
        def __init__(self, job_id: str) -> None:
            self.id = job_id

    def _fake_enqueue(db, enqueue_project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job(str((body.get('creativeContext') or {}).get('direction') or 'sheet'))

    def _fake_plan(current_sheet, *, direction, quality_profile="cinematic", deployment_preference="best-match"):
        view = next(item for item in current_sheet.directionalViews if item.direction == direction)
        return SimpleNamespace(
            shotIntent=SimpleNamespace(prompt=f"INTENT::{view.prompt}"),
            request=SimpleNamespace(prompt="REQUEST_SHOULD_NOT_WIN", spatialMapPayload={}),
        )

    monkeypatch.setattr("app.environment_reference_sheet.store.list_sheets", lambda pid: [sheet])
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.attach_spatial_map",
        lambda db, current, spatial_map_id: current,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.compose_sheet_metadata",
        lambda current: current,
    )
    monkeypatch.setattr(
        "app.environment_reference_sheet.orchestrator.build_directional_view_image_plan",
        _fake_plan,
    )
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue)
    monkeypatch.setattr(
        "app.spatial_map.service.get_document",
        lambda db, pid, mid: SpatialMapDocument(projectId=pid, id=mid),
    )
    monkeypatch.setattr("app.spatial_map.ers_persistence.save_ers_package", lambda *a, **k: None)
    monkeypatch.setattr("app.environment_reference_sheet.store.save_sheet", lambda current: None)

    result = ers_generate.handle(
        db=None,
        project_id=project_id,
        execution_id="279a7474-d93c-4dc7-8936-4b649ef06255",
        spatial_map_id=spatial_map_id,
        scene_id="scene-1",
        hosted_model_id="nano-banana-kie",
        source="api",
    )

    assert captured
    expected = [f"INTENT::{view.prompt}" for view in sheet.directionalViews]
    assert captured and captured[0]["purpose"] == "environment_reference_sheet"
    assert len(captured) == 1
    for body in captured:
        assert body["purpose"] == "environment_reference_sheet"
        assert "REQUEST_SHOULD_NOT_WIN" not in body["prompt"]
        assert body.get("hostedModelId") == "nano-banana-kie"
        assert body.get("modelFamilyPreference") != "zimage"
        assert "zimage.txt2img" not in str(body)
        assert body["creativeContext"]["resolvedProvider"] == "kie"
    assert len(result["child_jobs"]) == 1
    assert result["child_jobs"][0]["status"] == "queued"
