"""ERS edit enqueue — mask required, frozen prompt, Image Core region_edit, no sheet mutate."""

from __future__ import annotations

from pathlib import Path

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.environment_reference_sheet import edit as ers_edit
from app.image_core.request import ImageCoreRequest, NormalizedEnqueue


FROZEN_PROMPT = "Replace the hanging lantern with a warm oil lamp."


class _Sheet:
    def __init__(self, sheet_id: str, project_id: str, composite: str | None) -> None:
        self.sheetId = sheet_id
        self.projectId = project_id
        self.ers_composite_asset_id = composite
        self.composition = SimpleNamespace(renderedAssetIds={"composite": composite} if composite else {})


def _core_result(job_id: str = "job-ers-edit-1") -> NormalizedEnqueue:
    job = SimpleNamespace(id=job_id, status="queued", params_json="{}", asset_id=None, output_asset_id=None)
    return NormalizedEnqueue(
        job_id=job_id,
        status="queued",
        workflow_key="zimage.inpaint",
        family="zimage",
        operation="image.inpaint",
        width=64,
        height=64,
        job=job,
    )


@pytest.fixture()
def edit_harness(monkeypatch):
    captured: dict[str, object] = {}
    sheet = _Sheet("sheet-ers-1", "proj-ers-1", "asset-composite-1")
    source = SimpleNamespace(id="asset-composite-1", project_id="proj-ers-1", path="", prompt_meta_json="{}")
    save_sheet_calls: list[object] = []
    persist_calls: list[object] = []

    monkeypatch.setattr(ers_edit, "load_sheet", lambda pid, sid: sheet, raising=False)
    monkeypatch.setattr("app.environment_reference_sheet.store.load_sheet", lambda pid, sid: sheet)
    monkeypatch.setattr("app.environment_reference_sheet.store.save_sheet", lambda current: save_sheet_calls.append(current) or None)

    def _fake_generate(db, request: ImageCoreRequest):
        captured["request"] = request
        return _core_result()

    import importlib
    gen_mod = importlib.import_module("app.image_core.generate")
    monkeypatch.setattr(gen_mod, "generate", _fake_generate)
    monkeypatch.setattr(ers_edit, "mask_store", MagicMock())
    ers_edit.mask_store.get_mask.return_value = {"maskId": "mask-live-1", "dimensions": {"width": 64, "height": 64}}
    ers_edit.mask_store.save_mask.side_effect = lambda *a, **k: (_ for _ in ()).throw(AssertionError("save_mask should not run when maskAssetId given"))

    def _forbid_persist(*args, **kwargs):
        persist_calls.append((args, kwargs))
        raise AssertionError("persist_ers_composite_asset must not run on ERS edit")

    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.ers_generate.persist_ers_composite_asset",
        _forbid_persist,
        raising=False,
    )

    db = MagicMock()
    db.get.side_effect = lambda model, key: source if str(key) == "asset-composite-1" else None

    return SimpleNamespace(
        db=db,
        sheet=sheet,
        captured=captured,
        save_sheet_calls=save_sheet_calls,
        persist_calls=persist_calls,
        source=source,
    )


def test_mask_required(edit_harness):
    with pytest.raises(ValueError, match="maskPng or maskAssetId required"):
        ers_edit.enqueue_ers_edit(
            edit_harness.db,
            "proj-ers-1",
            "sheet-ers-1",
            edit_prompt=FROZEN_PROMPT,
            mask_asset_id=None,
            mask_png=None,
        )


def test_edit_prompt_required(edit_harness):
    with pytest.raises(ValueError, match="editPrompt required"):
        ers_edit.enqueue_ers_edit(
            edit_harness.db,
            "proj-ers-1",
            "sheet-ers-1",
            edit_prompt="   ",
            mask_asset_id="mask-live-1",
        )


def test_prompt_frozen_and_image_core_region_edit(edit_harness):
    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=f"  {FROZEN_PROMPT}  ",
        mask_asset_id="mask-live-1",
    )
    req: ImageCoreRequest = edit_harness.captured["request"]
    assert req.purpose == "region_edit"
    assert req.operation == "image.inpaint"
    assert req.model_id == "zimage"
    assert req.prompt == FROZEN_PROMPT
    assert req.mask_asset_id == "mask-live-1"
    assert req.source_asset_id == "asset-composite-1"
    ctx = req.creative_context
    assert ctx["ersEdit"] is True
    assert ctx["sheetId"] == "sheet-ers-1"
    assert ctx["frozenCreatorPrompt"] == FROZEN_PROMPT
    assert ctx["coDirectorRewrite"] is False
    assert ctx["derivativeOnly"] is True
    assert "spatialMapCorrect" not in ctx
    assert ctx.get("environmentReferenceSheetId") in (None, "")
    assert req.prompt == ctx["frozenCreatorPrompt"]
    assert out["workflowKey"] == "zimage.inpaint"
    assert out["jobId"] == out["queueJobId"] == "job-ers-edit-1"
    assert out["derivativeOnly"] is True
    assert out["derivativeAssetId"] == out["resultAssetId"]
    assert out["sourceAssetId"] == "asset-composite-1"
    assert out["sheetId"] == "sheet-ers-1"
    assert out["purpose"] == "region_edit"
    assert out["engine"] == "zimage.inpaint"


def test_sheet_not_mutated(edit_harness):
    source_src = inspect.getsource(ers_edit.enqueue_ers_edit)
    assert "persist_ers_composite_asset(" not in source_src
    assert "save_sheet(" not in source_src
    assert "ers_composite_asset_id =" not in source_src

    before = edit_harness.sheet.ers_composite_asset_id
    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=FROZEN_PROMPT,
        mask_asset_id="mask-live-1",
    )
    assert edit_harness.sheet.ers_composite_asset_id == before
    assert out["ersCompositeAssetId"] == before
    assert edit_harness.save_sheet_calls == []
    assert edit_harness.persist_calls == []


def test_mask_png_persists_via_image_product_helper(edit_harness, monkeypatch):
    saved = {}

    def _save(**kwargs):
        saved.update(kwargs)
        return {"maskId": "mask-from-png", "dimensions": {"width": 64, "height": 64}}

    ers_edit.mask_store.get_mask.return_value = None
    ers_edit.mask_store.save_mask.side_effect = lambda *a, **k: _save(**k)

    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=FROZEN_PROMPT,
        mask_png="iVBORw0KGgo=",
        width=64,
        height=64,
    )
    assert saved["png_base64"] == "iVBORw0KGgo="
    assert saved["creator"] == "ers.edit"
    assert saved["source_asset_id"] == "asset-composite-1"
    req: ImageCoreRequest = edit_harness.captured["request"]
    assert req.mask_asset_id == "mask-from-png"
    assert out["maskAssetId"] == "mask-from-png"


def test_route_path_matches_locked_contract():
    from app.environment_reference_sheet.api import api_ers_edit_enqueue, router

    routes = {getattr(r, "path", None) for r in router.routes}
    assert "/environment-reference-sheets/projects/{project_id}/{sheet_id}/edit/enqueue" in routes
    assert "/environment-reference-sheets/projects/{project_id}/{sheet_id}/edit/jobs/{job_id}" in routes
    assert "/sheets/{sheetId}/edit/enqueue" not in routes
    src = inspect.getsource(api_ers_edit_enqueue)
    assert "enqueue_ers_edit" in src
    assert "persist_ers_composite_asset" not in src


def test_queued_job_message_is_not_failure(edit_harness, monkeypatch):
    import importlib
    from app.image_core.request import ImageCoreRequest, NormalizedEnqueue
    from types import SimpleNamespace

    def _queued_with_label(db, request: ImageCoreRequest):
        job = SimpleNamespace(id="job-queued-msg", status="queued", params_json="{}", asset_id=None, output_asset_id=None)
        return NormalizedEnqueue(
            job_id="job-queued-msg",
            status="queued",
            workflow_key="zimage.inpaint",
            family="zimage",
            operation="image.inpaint",
            error="ImageGen · zimage.inpaint · z_image_turbo_bf16.safetensors",
            job=job,
        )

    gen_mod = importlib.import_module("app.image_core.generate")
    monkeypatch.setattr(gen_mod, "generate", _queued_with_label)
    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=FROZEN_PROMPT,
        mask_asset_id="mask-live-1",
    )
    assert out["jobId"] == "job-queued-msg"
    assert out["status"] == "queued"
    assert out["workflowKey"] == "zimage.inpaint"


def test_overlay_guidance_in_creative_context(edit_harness, monkeypatch, tmp_path):
    """Overlay/labels/markers accepted; source path unchanged; guidance_only; no bake."""
    import base64
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (255, 0, 0, 128)).save(buf, format="PNG")
    raster_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    # Point overlay persist at temp image_product root
    import app.image_product.store as ip_store

    monkeypatch.setattr(ip_store, "project_dir", lambda pid: tmp_path / pid)

    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=FROZEN_PROMPT,
        mask_asset_id="mask-live-1",
        drawing_overlay={
            "rasterPngBase64": raster_b64,
            "vectors": [{"type": "stroke", "points": [[1, 1], [2, 2]]}],
            "width": 8,
            "height": 8,
        },
        text_labels=[{"id": "t1", "text": "door", "x": 0.2, "y": 0.3, "normalized": True}],
        numbered_markers=[{"number": 1, "label": "lantern", "x": 0.5, "y": 0.4}],
    )
    req: ImageCoreRequest = edit_harness.captured["request"]
    # Source ERS path unchanged — overlay not composited into source
    assert req.source_asset_id == "asset-composite-1"
    assert req.prompt == FROZEN_PROMPT
    assert req.prompt == req.creative_context["frozenCreatorPrompt"]
    ctx = req.creative_context
    assert ctx["overlayBakePolicy"] == "guidance_only"
    assert ctx["textLabels"][0]["text"] == "door"
    assert ctx["numberedMarkers"][0]["number"] == 1
    assert ctx["drawingOverlay"]["hasRaster"] is True
    assert ctx["drawingOverlay"]["vectors"]
    assert ctx.get("overlayAssetId")
    assert ctx["guidanceModel"]["bakeIntoSource"] is False
    assert ctx["guidanceModel"]["bakeIntoDerivative"] is False
    # Prompt not rewritten with overlay note
    assert "overlay" not in req.prompt.lower()
    assert "door" not in req.prompt.lower()
    # Response surfaces guidance; composite id frozen
    assert out["sourceAssetId"] == "asset-composite-1"
    assert out["ersCompositeAssetId"] == "asset-composite-1"
    assert out["overlayBakePolicy"] == "guidance_only"
    assert out["guidanceOnly"] is True
    assert out["overlayAssetId"]
    assert edit_harness.sheet.ers_composite_asset_id == "asset-composite-1"
    assert edit_harness.save_sheet_calls == []
    # Extra provenance only — not wired as inpaint source/mask
    assert req.extra.get("ersOverlayGuidanceAssetId") == out["overlayAssetId"]
    assert req.mask_asset_id == "mask-live-1"
    assert req.source_asset_id != out["overlayAssetId"]


def test_overlay_absent_when_not_provided(edit_harness):
    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=FROZEN_PROMPT,
        mask_asset_id="mask-live-1",
    )
    req: ImageCoreRequest = edit_harness.captured["request"]
    assert req.creative_context.get("drawingOverlay") is None
    assert req.creative_context.get("textLabels") is None
    assert req.creative_context.get("numberedMarkers") is None
    assert out.get("guidanceOnly") is None
    assert out.get("overlayAssetId") is None


def test_fal_provider_routes_to_hosted_edit(edit_harness, monkeypatch):
    """Selected fal.ai must hit hosted edit path with /edit endpoint — never Kie/zimage."""
    captured: dict[str, object] = {}

    def _fake_enqueue(db, project_id, body, scene_id=None):
        captured["body"] = dict(body)
        return SimpleNamespace(id="job-fal-edit-1", status="queued", asset_id=None, output_asset_id=None, message="")

    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        _fake_enqueue,
    )
    import importlib
    gen_mod = importlib.import_module("app.image_core.generate")

    def _boom(*a, **k):
        raise AssertionError("Image Core zimage path must not run when fal selected")

    monkeypatch.setattr(gen_mod, "generate", _boom)

    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=FROZEN_PROMPT,
        mask_asset_id="mask-live-1",
        width=64,
        height=64,
        requested_provider="fal",
        hosted_model_id="gpt-image-2-fal",
        fal_image_model_id="openai/gpt-image-2",
        official_model_id="openai/gpt-image-2",
    )
    body = captured["body"]
    assert body["provider"] == "fal"
    assert body["requested_provider"] == "fal"
    assert body["edit"] is True
    assert body["sourceAssetId"] == "asset-composite-1"
    assert "/edit" in str(body.get("falImageModelId") or "")
    assert not body.get("kieImageModelId")
    assert out["jobId"] == "job-fal-edit-1"
    assert str(out.get("engine") or "").startswith("fal:")
    assert out["provider"] == "fal"


def test_fal_prompt_only_no_mask(edit_harness, monkeypatch):
    captured: dict[str, object] = {}

    def _fake_enqueue(db, project_id, body, scene_id=None):
        captured["body"] = dict(body)
        return SimpleNamespace(id="job-fal-prompt-1", status="queued", asset_id=None, output_asset_id=None, message="")

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue)

    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=FROZEN_PROMPT,
        mask_asset_id=None,
        mask_png=None,
        width=64,
        height=64,
        requested_provider="fal",
        fal_image_model_id="openai/gpt-image-2",
        hosted_model_id="gpt-image-2-fal",
    )
    body = captured["body"]
    assert body.get("masks") in (None, [], ())
    assert body["operation"] == "image.edit"
    assert "/edit" in str(body.get("falImageModelId") or "")
    assert out["jobId"] == "job-fal-prompt-1"


def test_fal_selected_never_falls_back_to_kie(edit_harness, monkeypatch):
    captured: dict[str, object] = {}

    def _fake_enqueue(db, project_id, body, scene_id=None):
        captured["body"] = dict(body)
        return SimpleNamespace(id="job-fal-strict", status="queued", asset_id=None, output_asset_id=None, message="")

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake_enqueue)
    out = ers_edit.enqueue_ers_edit(
        edit_harness.db,
        "proj-ers-1",
        "sheet-ers-1",
        edit_prompt=FROZEN_PROMPT,
        mask_asset_id="mask-live-1",
        width=64,
        height=64,
        requested_provider="fal",
        fal_image_model_id="openai/gpt-image-2",
        kie_image_model_id="should-not-win",
        hosted_model_id="gpt-image-2-fal",
    )
    body = captured["body"]
    assert body["provider"] == "fal"
    assert not body.get("kieImageModelId")
    assert out["provider"] == "fal"


def test_save_ers_edit_annotations_legend_only(edit_harness, tmp_path, monkeypatch):
    """Legend-only blank prompt path must not enqueue image edit."""
    from app.image_product import store as ip_store

    monkeypatch.setattr(ip_store, "project_dir", lambda pid: tmp_path / pid)
    out = ers_edit.save_ers_edit_annotations(
        "proj-ers-1",
        "sheet-ers-1",
        source_asset_id="asset-composite-1",
        legend={
            "position": {"left": 0.5, "top": 0.3, "width": 0.16, "height": 0.3},
            "characters": [{"color": "#ef4444", "label": "Maya"}],
            "props": [],
            "userMoved": True,
        },
    )
    assert out["ok"] is True
    assert out["imageEditInvoked"] is False
    assert out["hasLegend"] is True
    assert out["hasGuidance"] is False
    assert Path(out["path"]).is_file()


def test_save_ers_edit_annotations_markers_only(edit_harness, tmp_path, monkeypatch):
    from app.image_product import store as ip_store

    monkeypatch.setattr(ip_store, "project_dir", lambda pid: tmp_path / pid)
    out = ers_edit.save_ers_edit_annotations(
        "proj-ers-1",
        "sheet-ers-1",
        source_asset_id="asset-composite-1",
        numbered_markers=[{"id": "m1", "number": 1, "x": 0.2, "y": 0.4, "label": "door"}],
    )
    assert out["ok"] is True
    assert out["imageEditInvoked"] is False
    assert out["hasGuidance"] is True


def test_save_ers_edit_annotations_empty_rejected(edit_harness, tmp_path, monkeypatch):
    from app.image_product import store as ip_store

    monkeypatch.setattr(ip_store, "project_dir", lambda pid: tmp_path / pid)
    with pytest.raises(ValueError, match="Nothing to save"):
        ers_edit.save_ers_edit_annotations(
            "proj-ers-1",
            "sheet-ers-1",
            source_asset_id="asset-composite-1",
        )


def test_annotations_route_registered():
    from app.environment_reference_sheet import api as ers_api

    paths = {getattr(r, "path", "") for r in ers_api.router.routes}
    assert any(p.endswith("/edit/annotations") for p in paths)
