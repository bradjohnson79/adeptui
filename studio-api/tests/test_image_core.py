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
    assert recommend("add", "zimage")["recommendedFamily"] == "nano-banana-fal"
    assert recommend("remove", "zimage")["recommendedFamily"] == "flux"
    keep = recommend("remove", "zimage")
    assert keep["keepCurrentAllowed"] is True
    assert keep["recommended"] is False
    assert keep["family"] == "zimage"


def test_add_recommends_nano_banana_without_forcing_routing() -> None:
    rec = recommend("add", "flux")
    assert rec["recommendedFamily"] == "nano-banana-fal"
    assert rec["keepCurrentAllowed"] is True
    assert rec["recommended"] is False
    assert "Nano Banana 2" in rec["message"]
    keep = recommend("add", "nano-banana-fal")
    assert keep["recommended"] is True
    assert keep["message"] == ""
    assert recommend("remove", "nano-banana-fal")["recommendedFamily"] == "flux"
    assert recommend("modify", "nano-banana-fal")["recommendedFamily"] == "flux"
    assert recommend("replace", "nano-banana-fal")["recommendedFamily"] == "flux"


def test_add_insert_preflight_ok_only_for_add(monkeypatch) -> None:
    import importlib

    preflight_mod = importlib.import_module("app.image_core.preflight")
    monkeypatch.setattr(preflight_mod, "_fal_credential_configured", lambda: True)
    ok = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="region_edit",
            operation="image.edit",
            model_id="nano-banana-fal",
            edit_operation="add",
            source_asset_id="a1",
            mask_asset_id="m1",
        )
    )
    assert ok.ok is True
    assert ok.workflow_key == "fal:fal-ai/nano-banana-2/edit"
    assert ok.family == "nano-banana-fal"
    blocked = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="region_edit",
            operation="image.edit",
            model_id="nano-banana-fal",
            edit_operation="remove",
            source_asset_id="a1",
            mask_asset_id="m1",
        )
    )
    assert blocked.ok is False
    assert "Add only" in blocked.message


def test_add_insert_to_body_pins_fal_edit() -> None:
    from types import SimpleNamespace

    from app.image_core.generate import _to_body
    from app.image_core.request import ImageCoreRequest

    decision = SimpleNamespace(
        runtime_operation="image.edit",
        family="nano-banana-fal",
        width=1280,
        height=720,
        denoise=0.94,
        grow_mask_by=14,
        workflow_key="fal:fal-ai/nano-banana-2/edit",
    )
    body = _to_body(
        ImageCoreRequest(
            project_id="p",
            purpose="region_edit",
            operation="image.edit",
            model_id="nano-banana-fal",
            source_asset_id="a1",
            mask_asset_id="m1",
            edit_operation="add",
        ),
        decision,
    )
    assert body["falImageModelId"] == "fal-ai/nano-banana-2/edit"
    assert body["hostedModelId"] == "nano-banana-2-fal"
    assert body["source"] == "api"
    assert body["providerPreference"] == "cloud"
    assert body.get("sourceAssetId") == "a1"
    assert body.get("aspect") == "16:9"


def test_fal_edit_args_and_capability_allow_nano_banana_edit() -> None:
    from app.fal_catalog import build_fal_image_arguments
    from app.image_product.resolve import resolve_image_capability

    args = build_fal_image_arguments(
        model_id="fal-ai/nano-banana-2/edit",
        prompt="add a red apple",
        width=1280,
        height=720,
        seed=1,
        image_urls=["https://example.com/src.png"],
    )
    assert args["image_urls"] == ["https://example.com/src.png"]
    assert args["aspect_ratio"] == "16:9"
    assert "image_size" not in args
    t2i = build_fal_image_arguments(model_id="fal-ai/flux/dev", prompt="x", width=1024, height=1024, seed=7)
    assert t2i["image_size"] == {"width": 1024, "height": 1024}
    cap = resolve_image_capability(
        {
            "prompt": "add a red apple",
            "purpose": "region_edit",
            "source": "api",
            "falImageModelId": "fal-ai/nano-banana-2/edit",
            "hostedModelId": "nano-banana-2-fal",
            "source_asset_id": "a1",
            "edit": True,
        }
    )
    assert cap["canExecute"] is True
    assert cap["officialModelId"] == "fal-ai/nano-banana-2/edit"
    refuse = resolve_image_capability(
        {
            "prompt": "edit the mug",
            "purpose": "project_prop",
            "source": "api",
            "hostedModelId": "flux-fal",
            "falImageModelId": "fal-ai/flux/dev",
            "source_asset_id": "a1",
            "edit": True,
        }
    )
    assert refuse["canExecute"] is False
    assert "t2i-as-edit" in str(refuse.get("reason") or "").lower()




def test_add_insert_preflight_requires_fal_credential(monkeypatch) -> None:
    """CDX-078: Nano-Banana Add forces a fal job — preflight must refuse before
    enqueue when no fal API key is configured."""
    import importlib

    from app.image_core.errors import PROVIDER_AUTH_FAILED

    preflight_mod = importlib.import_module("app.image_core.preflight")
    monkeypatch.setattr(preflight_mod, "_fal_credential_configured", lambda: False)
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="region_edit",
            operation="image.edit",
            model_id="nano-banana-fal",
            edit_operation="add",
            source_asset_id="a1",
            mask_asset_id="m1",
        )
    )
    assert decision.ok is False
    assert decision.code == PROVIDER_AUTH_FAILED
    assert "credential not configured" in decision.message.lower()
    assert decision.details.get("missingProvider") == "fal"


def test_cloud_preflight_requires_provider_credential(monkeypatch) -> None:
    """CDX-078: any cloud request must fail before enqueue when the executing
    provider's credential is missing."""
    import importlib

    from app.image_core.errors import PROVIDER_AUTH_FAILED

    preflight_mod = importlib.import_module("app.image_core.preflight")
    monkeypatch.setattr(preflight_mod, "_provider_secret_configured", lambda secret: False)
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_final",
            operation="image.generate",
            model_id="flux",
            provider="cloud",
            hosted_model_id="flux-fal",
        )
    )
    assert decision.ok is False
    assert decision.code == PROVIDER_AUTH_FAILED
    assert decision.details.get("missingProvider") == "fal"

    # With a credential present, the request proceeds past the credential gate.
    monkeypatch.setattr(preflight_mod, "_provider_secret_configured", lambda secret: True)
    ok = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_final",
            operation="image.generate",
            model_id="flux",
            provider="cloud",
            hosted_model_id="flux-fal",
        )
    )
    assert ok.ok is True
    assert ok.code != PROVIDER_AUTH_FAILED


def test_refs_without_certified_path_refused_not_downgraded() -> None:
    """CDX-079: identity refs + a family with no Certified visual-edit path must
    be refused explicitly — never silently downgraded to txt2img."""
    from app.image_core.errors import UNSUPPORTED_OPERATION

    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_preview",
            operation="image.generate",
            model_id="hosted",
            extra={"referenceImage": "cast-korri"},
            creative_context={"reference_image_ids": ["cast-korri"]},
        )
    )
    assert decision.ok is False
    assert decision.code == UNSUPPORTED_OPERATION
    assert "reference" in decision.message.lower()
    # The forbidden outcome: ok=True with a txt2img downgrade.
    assert not (decision.ok and decision.runtime_operation == "image.generate")


def test_refs_via_reference_packet_unsupported_refused() -> None:
    """CDX-079: Scene Creator reference packets that mark a role unsupported
    (asset present, no Certified visual-edit path) must refuse, not drop."""
    from app.image_core.errors import UNSUPPORTED_OPERATION

    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_preview",
            operation="image.generate",
            model_id="hosted",
            creative_context={
                "referencePacket": {
                    "roles": [
                        {
                            "role": "character_reference",
                            "entityId": "char-1",
                            "assetId": "cast-korri",
                            "consumption": "unsupported",
                        }
                    ]
                }
            },
        )
    )
    assert decision.ok is False
    assert decision.code == UNSUPPORTED_OPERATION
    assert "reference" in decision.message.lower()
    assert not (decision.ok and decision.runtime_operation == "image.generate")


def test_refs_prompt_only_mode_is_not_reference_bearing() -> None:
    """CDX-079: prompt_only diagnostic mode intentionally omits refs — it must
    not be refused as a reference-bearing request."""
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_preview",
            operation="image.generate",
            model_id="flux",
            creative_context={
                "diagnosticMode": "prompt_only",
                "referencePacket": {
                    "roles": [
                        {
                            "role": "character_reference",
                            "entityId": "char-1",
                            "assetId": "cast-korri",
                            "consumption": "unsupported",
                        }
                    ]
                },
            },
        )
    )
    assert decision.ok is True
    assert decision.runtime_operation == "image.generate"


def test_refs_with_certified_path_still_route_to_edit() -> None:
    """CDX-079: refs + a family WITH a Certified visual-edit path keep routing
    to the edit workflow (zimage.ref_edit) — no regression."""
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_preview",
            operation="image.generate",
            model_id="zimage",
            extra={"referenceImage": "cast-korri"},
            creative_context={"reference_image_ids": ["cast-korri"]},
        )
    )
    assert decision.ok is True
    assert decision.workflow_key == "zimage.ref_edit"
    assert decision.runtime_operation == "image.edit"


def test_to_body_refuses_txt2img_with_refs() -> None:
    """CDX-079: body assembly must honor the refusal — refs + a txt2img
    decision raises instead of silently dropping the references."""
    from types import SimpleNamespace

    from app.image_core.errors import ImageCoreError, UNSUPPORTED_OPERATION
    from app.image_core.generate import _to_body

    decision = SimpleNamespace(
        runtime_operation="image.generate",
        family="hosted",
        width=512,
        height=288,
        denoise=None,
        grow_mask_by=None,
        workflow_key="",
    )
    try:
        _to_body(
            ImageCoreRequest(
                project_id="p",
                purpose="scene_shot_preview",
                operation="image.generate",
                model_id="hosted",
                extra={"referenceImage": "cast-korri"},
                creative_context={"reference_image_ids": ["cast-korri"]},
            ),
            decision,
        )
        raise AssertionError("expected ImageCoreError for txt2img-with-refs")
    except ImageCoreError as exc:
        assert exc.code == UNSUPPORTED_OPERATION
        assert "reference" in exc.message.lower()
