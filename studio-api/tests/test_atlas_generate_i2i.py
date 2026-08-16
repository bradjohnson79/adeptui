"""Atlas generation: I2I when a source image exists; T2I only for true no-source creation."""

from __future__ import annotations

import uuid

from app.codirector.capabilities.handlers import atlas_generate


def _patch_enqueue(monkeypatch, captured: list[dict]):
    class _Job:
        def __init__(self) -> None:
            self.id = "job-atlas-1"

    def _fake(db, project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job()

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake)


def test_atlas_without_source_may_use_t2i_creation(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="A neighborhood coffee shop.",
        scene_description="A neighborhood coffee shop.",
        scene_intent={"sceneTitle": "Cafe", "summary": "A neighborhood coffee shop interior."},
    )
    assert captured
    body = captured[0]
    assert body["purpose"] == "atlas_shot"
    assert body["creativeContext"]["workflowKey"] == "zimage.txt2img"
    assert not body.get("sourceAssetId")


def test_atlas_with_source_uses_qwen_ref_not_t2i(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    source = "4d3062e8-8c30-4230-8376-bc25d1d4f735"
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Preserve this coffee shop as a top-down atlas.",
        scene_description="Schnick Coffee",
        scene_intent={"sceneTitle": "Schnick Coffee", "summary": "A neighborhood coffee shop interior."},
        attachment_asset_ids=[source],
    )
    assert captured
    body = captured[0]
    assert body["sourceAssetId"] == source
    assert body["forceWorkflowKey"] == "qwen2512.ref"
    assert body["creativeContext"]["workflowKey"] == "qwen2512.ref"
    assert body["creativeContext"]["authoritativeSourceAssetId"] == source
    assert "zimage.txt2img" not in str(body)


def test_atlas_with_source_gpt_uses_i2i_not_t2i(monkeypatch) -> None:
    captured: list[dict] = []
    _patch_enqueue(monkeypatch, captured)
    source = "4d3062e8-8c30-4230-8376-bc25d1d4f735"
    atlas_generate.handle(
        db=None,
        project_id=f"proj-{uuid.uuid4()}",
        execution_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        prompt="Preserve this coffee shop as a top-down atlas.",
        scene_intent={"sceneTitle": "Schnick Coffee", "summary": "A neighborhood coffee shop interior."},
        hosted_model_id="gpt-image-2-kie",
        kieImageModelId="gpt-image-2-image-to-image",
        attachment_asset_ids=[source],
    )
    assert captured
    body = captured[0]
    assert body["sourceAssetId"] == source
    assert body["kieImageModelId"] == "gpt-image-2-image-to-image"
    assert "text-to-image" not in str(body.get("kieImageModelId") or "")
    assert body.get("input_urls")
    assert any(source in u for u in body["input_urls"])
    assert "zimage.txt2img" not in str(body)
