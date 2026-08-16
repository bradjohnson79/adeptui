"""Image Core facade — capability, recommend, preflight, no Scene-chosen workflow keys."""

from __future__ import annotations

from app.image_core.capability import certified_visual_edit_path, family_region_edit_capability, normalize_family
from app.image_core.errors import UNSUPPORTED_OPERATION
from app.image_core.flag import scene_image_core_enabled
from app.image_core.preflight import preflight
from app.image_core.recommend import recommend
from app.image_core.request import ImageCoreRequest
from app.image_core.resolution import resolve_resolution


def test_flag_defaults_on(monkeypatch) -> None:
    monkeypatch.delenv("SCENE_IMAGE_CORE", raising=False)
    assert scene_image_core_enabled() is True
    monkeypatch.setenv("SCENE_IMAGE_CORE", "0")
    assert scene_image_core_enabled() is False
    monkeypatch.setenv("SCENE_IMAGE_CORE", "1")
    assert scene_image_core_enabled() is True


def test_normalize_family() -> None:
    assert normalize_family("qwen") == "qwen2512"
    assert normalize_family("illustrious-xl") == "illustrious"
    assert normalize_family("zimage") == "zimage"


def test_recommend_is_not_routing() -> None:
    rec = recommend("modify", "zimage")
    assert rec["recommendedFamily"] == "flux"
    assert rec["supported"] is True
    assert rec["keepCurrentAllowed"] is True
    assert "FLUX" in rec["message"]
    keep = recommend("modify", "flux")
    assert keep["recommended"] is True
    assert keep["message"] == ""


def test_preview_resolution_is_purpose_based() -> None:
    w, h = resolve_resolution("zimage", "image.generate", "scene_shot_preview")
    assert (w, h) == (512, 288)


def test_qwen_region_edit_preflight_unsupported() -> None:
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="region_edit",
            operation="image.inpaint",
            model_id="qwen2512",
            edit_operation="modify",
            source_asset_id="a1",
            mask_asset_id="m1",
        )
    )
    assert decision.ok is False
    assert decision.code == UNSUPPORTED_OPERATION
    assert "cannot edit a region" in decision.message.lower() or "Choose Z-Image" in decision.message


def test_qwen_final_inheritance_preflight_unsupported() -> None:
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_final",
            operation="image.edit",
            model_id="qwen2512",
            source_asset_id="approved-edit",
        )
    )
    assert decision.ok is False
    assert decision.code == UNSUPPORTED_OPERATION


def test_zimage_inpaint_preflight_ok() -> None:
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="region_edit",
            operation="image.inpaint",
            model_id="zimage",
            edit_operation="add",
            source_asset_id="a1",
            mask_asset_id="m1",
        )
    )
    assert decision.ok is True
    assert decision.workflow_key == "zimage.inpaint"
    assert decision.runtime_operation == "image.inpaint"


def test_flux_modify_preflight_uses_certified_img2img() -> None:
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="region_edit",
            operation="image.edit",
            model_id="flux",
            edit_operation="modify",
            source_asset_id="a1",
            mask_asset_id="m1",
        )
    )
    assert decision.ok is True
    assert decision.workflow_key == "flux.img2img"
    assert "txt2img" not in decision.workflow_key
    assert decision.workflow_key != "flux.edit"


def test_visual_edit_path_not_draft_flux_edit() -> None:
    path = certified_visual_edit_path("flux")
    assert path is not None
    assert path["workflowKey"] == "flux.img2img"


def test_generation_module_reexports_core() -> None:
    from app.scene_creator import generation as gen
    from app.image_core.capability import certified_visual_edit_path as core_path

    assert gen.certified_visual_edit_path is core_path
    caps = gen.family_region_edit_capability("zimage")
    assert caps["supportsInpaint"] is True
    flux = family_region_edit_capability("flux")
    assert flux["supportsEditing"] is True
    assert flux["supportsInpaint"] is False


def test_scene_service_does_not_hardcode_force_workflow_on_core_path() -> None:
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app" / "scene_creator" / "service.py"
    text = src.read_text(encoding="utf-8")
    assert "image_core_generate" in text
    assert "scene_shot_final" in text
    assert "final_region_edit" in text
    assert "purpose=purpose" in text or 'purpose="region_edit"' in text or "purpose = \"region_edit\"" in text or 'purpose = "final_region_edit"' in text
    assert 'return "zimage.inpaint", "image.inpaint", "Native Inpaint"' not in text
    assert 'return "flux.img2img", "image.edit", "Image Edit"' not in text


def test_idempotency_key_includes_purpose_source_mask() -> None:
    from app.image_core.generate import idempotency_key
    from app.image_core.request import ImageCoreRequest

    key = idempotency_key(
        ImageCoreRequest(
            project_id="p",
            purpose="region_edit",
            operation="image.edit",
            model_id="flux",
            source_asset_id="src-1",
            mask_asset_id="mask-1",
            edit_operation="modify",
            creative_context={"cinematographer": {"cameraStateHash": "hash-9"}},
        )
    )
    assert key == "region_edit|src-1|hash-9|flux|image.edit|modify|mask-1"


def test_unknown_purpose_is_rejected() -> None:
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="character_sheet",
            operation="image.generate",
            model_id="flux",
        )
    )
    assert decision.ok is False
    assert decision.code == UNSUPPORTED_OPERATION
    assert "Unknown Image Core purpose" in decision.message


def test_to_body_stamps_purpose_on_job_payload() -> None:
    from types import SimpleNamespace

    from app.image_core.generate import _to_body
    from app.image_core.request import ImageCoreRequest

    decision = SimpleNamespace(
        runtime_operation="image.edit",
        family="flux",
        width=1024,
        height=1024,
        denoise=0.35,
        grow_mask_by=None,
        workflow_key="flux.img2img",
    )
    body = _to_body(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_final",
            operation="image.edit",
            model_id="flux",
            source_asset_id="d1",
        ),
        decision,
    )
    assert body["purpose"] == "scene_shot_final"
    assert body["creativeContext"]["purpose"] == "scene_shot_final"
    assert body["operation"] == "image.edit"


def test_generate_reuses_live_job(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.image_core.generate import generate, idempotency_key
    from app.image_core.request import ImageCoreRequest

    request = ImageCoreRequest(
        project_id="p",
        purpose="region_edit",
        operation="image.edit",
        model_id="flux",
        source_asset_id="src-1",
        mask_asset_id="mask-1",
        edit_operation="modify",
        creative_context={"cinematographer": {"cameraStateHash": "h"}},
    )
    key = idempotency_key(request)
    live = SimpleNamespace(
        id="job-live",
        status="queued",
        params_json={"creativeContext": {"imageCoreIdempotencyKey": key}},
        params=None,
        message="",
    )

    class _Query:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def limit(self, n):
            return self

        def all(self):
            return [live]

    class _Db:
        def query(self, model):
            return _Query()

    enqueued = []

    def _enqueue(*a, **k):
        enqueued.append("hit")
        raise AssertionError("live job must be reused")

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)
    result = generate(_Db(), request)
    assert result.job_id == "job-live"
    assert enqueued == []


def test_image_product_preserves_masks_on_enqueue() -> None:
    from pathlib import Path

    service = Path(__file__).resolve().parents[1] / "app" / "image_product" / "service.py"
    jobs = Path(__file__).resolve().parents[1] / "app" / "storyboard_jobs.py"
    text = service.read_text(encoding="utf-8")
    assert '"masks": body.get("masks")' in text or "body.get(\"masks\")" in text
    job_src = jobs.read_text(encoding="utf-8")
    assert 'payload["operation"] = "image.edit"' in job_src
    assert "image.inpaint" in job_src
    assert recommend("modify", "zimage")["recommendedFamily"] == "flux"
    assert recommend("replace", "zimage")["recommendedFamily"] == "flux"
    assert recommend("add", "zimage")["recommendedFamily"] == "flux"
    assert recommend("remove", "zimage")["recommendedFamily"] == "flux"
    keep = recommend("remove", "zimage")
    assert keep["keepCurrentAllowed"] is True
    assert keep["recommended"] is False
    assert keep["family"] == "zimage"
