"""Phase A: one compile pin provider/adapter/officialModelId/workflowKey."""

from __future__ import annotations

from app.hosted_providers.adapters.kie_adapter import kie_image_model_id_for_dock
from app.image_product.compile import (
    _fal_image_route,
    _hosted_execution_pin,
    _kie_image_route,
    compile_image_request,
)
from app.image_runtime.provenance import executed_image_stamp


def test_routing_laws_bare_flux_is_not_kie() -> None:
    assert kie_image_model_id_for_dock("flux") is None
    assert kie_image_model_id_for_dock("flux-kie") == "flux"
    assert _kie_image_route({"source": "local", "modelFamilyPreference": "flux"}) is None
    assert _kie_image_route({"forceWorkflowKey": "flux.txt2img", "model": "flux"}) is None
    assert _kie_image_route({"modelFamilyPreference": "flux", "model": "flux"}) is None
    assert _fal_image_route({"source": "local", "hostedModelId": "flux-fal"}) is None
    hosted = _kie_image_route({"hostedModelId": "flux-kie", "prompt": "a mug"})
    assert hosted == {"dock": "flux-kie", "official": "flux"}

    # source=local must win even if a Kie dock / official id leaked onto the body.
    assert _kie_image_route({"source": "local", "hostedModelId": "flux-kie", "kieImageModelId": "flux"}) is None
    assert _hosted_execution_pin({"source": "local", "hostedModelId": "nano-banana-kie", "kieImageModelId": "nano-banana-2"}) is None
    assert _hosted_execution_pin({"source": "local", "modelFamilyPreference": "flux", "model": "flux"}) is None


def test_source_local_never_routes_to_imagegen_kie() -> None:
    """local flux / source=local must not produce a Kie pin (queue_worker gate)."""
    local_bodies = (
        {"source": "local", "modelFamilyPreference": "flux", "model": "flux", "prompt": "a mug"},
        {"source": "local", "hostedModelId": "flux-kie", "prompt": "a mug"},
        {"providerKind": "local", "model": "flux", "prompt": "a mug"},
        {"creativeContext": {"providerKind": "local"}, "hostedModelId": "nano-banana-kie", "prompt": "a mug"},
        {"source": "local", "forceWorkflowKey": "flux.txt2img", "hostedModelId": "flux-kie"},
    )
    for body in local_bodies:
        assert _kie_image_route(body) is None, body
        assert _hosted_execution_pin(body) is None, body

def test_compile_kie_pin_shape() -> None:
    compiled = compile_image_request(
        "proj-pin",
        {
            "prompt": "Prop: Coffee Cup",
            "purpose": "project_prop",
            "source": "api",
            "hostedModelId": "nano-banana-kie",
            "lockModelFamily": True,
        },
    )
    runtime = compiled["imageRuntime"]
    assert set(runtime).issuperset({"provider", "adapter", "officialModelId", "workflowKey"})
    assert runtime["provider"] == "kie"
    assert runtime["adapter"] == "kie"
    assert runtime["officialModelId"] == "nano-banana-2"
    assert runtime["workflowKey"] == "kie:nano-banana-2"
    assert compiled.get("kieImageModelId") == "nano-banana-2"


def test_compile_fal_pin_shape_not_kie() -> None:
    compiled = compile_image_request(
        "proj-pin",
        {
            "prompt": "Prop: Chair",
            "purpose": "project_prop",
            "source": "api",
            "hostedModelId": "flux-fal",
            "lockModelFamily": True,
        },
    )
    runtime = compiled["imageRuntime"]
    assert runtime["provider"] == "fal"
    assert runtime["adapter"] == "fal"
    assert runtime["officialModelId"] == "fal-ai/flux/dev"
    assert runtime["workflowKey"] == "fal:fal-ai/flux/dev"
    assert compiled.get("kieImageModelId") in (None, "")
    assert compiled.get("falImageModelId") == "fal-ai/flux/dev"

def test_compile_local_flux_pin_is_not_kie() -> None:
    pin = _hosted_execution_pin({"source": "local", "modelFamilyPreference": "flux", "forceWorkflowKey": "flux.txt2img"})
    assert pin is None
    try:
        compiled = compile_image_request(
            "proj-pin",
            {
                "prompt": "a mug",
                "purpose": "project_prop",
                "source": "local",
                "modelFamilyPreference": "flux",
                "model": "flux",
                "lockModelFamily": True,
                "forceWorkflowKey": "flux.txt2img",
                "allow_force_workflow_key": True,
            },
        )
    except RuntimeError as exc:
        msg = str(exc).lower()
        assert "kie:" not in msg
        return
    runtime = compiled["imageRuntime"]
    assert runtime.get("provider") != "kie"
    assert not str(runtime.get("workflowKey") or "").startswith("kie:")
    assert compiled.get("kieImageModelId") in (None, "")


def test_executed_stamp_uses_compile_pin_official() -> None:
    compiled = compile_image_request(
        "proj-pin",
        {
            "prompt": "Character sheet",
            "purpose": "character_sheet",
            "source": "api",
            "hostedModelId": "nano-banana-kie",
        },
    )
    provider, runtime, official = executed_image_stamp(
        {"imageRuntime": compiled["imageRuntime"]},
        contract_key=compiled["imageRuntime"]["workflowKey"],
        model="nano-banana-kie",
    )
    assert provider == "kie"
    assert runtime == "kie"
    assert official == "nano-banana-2"
    assert provider != "local"


def test_resolver_refuses_t2i_as_edit() -> None:
    from app.image_product.resolve import resolve_image_capability

    for body in (
        {
            "prompt": "edit the mug",
            "purpose": "project_prop",
            "source": "api",
            "hostedModelId": "nano-banana-kie",
            "source_asset_id": "asset-ref-1",
        },
        {
            "prompt": "edit the mug",
            "purpose": "project_prop",
            "source": "api",
            "hostedModelId": "flux-kie",
            "edit": True,
        },
    ):
        cap = resolve_image_capability(body)
        assert cap["canExecute"] is False, body
        reason = str(cap.get("reason") or "").lower()
        assert "t2i-as-edit" in reason or "t2i" in reason
        assert "image-to-image" in reason or "edit" in reason
        try:
            compile_image_request("proj-refuse-t2i", body)
            raise AssertionError("compile must refuse T2I-as-edit, not pin or swap")
        except RuntimeError as exc:
            msg = str(exc).lower()
            assert "t2i" in msg or "edit" in msg
            assert "kie:nano-banana-2" not in msg
            assert "zimage" not in msg or "substitut" in msg


def test_resolver_refuses_silent_sub_of_qwen_zimage_comfy() -> None:
    from app.image_product.resolve import resolve_image_capability

    body = {
        "prompt": "a mug",
        "purpose": "project_prop",
        "source": "api",
        "hostedModelId": "unknown-hosted-model",
        "lockModelFamily": True,
    }
    cap = resolve_image_capability(body)
    assert cap["canExecute"] is False
    reason = str(cap.get("reason") or "").lower()
    assert "substitut" in reason
    assert "qwen" in reason and "zimage" in reason and "comfy" in reason
    try:
        compiled = compile_image_request("proj-refuse-sub", body)
        runtime = compiled.get("imageRuntime") or {}
        raise AssertionError(
            "compile must refuse silent local substitute, got "
            + str(runtime.get("provider"))
            + " "
            + str(runtime.get("workflowKey"))
        )
    except RuntimeError as exc:
        msg = str(exc).lower()
        assert "substitut" in msg
        assert "qwen" in msg or "zimage" in msg or "comfy" in msg


def test_resolver_allows_kie_i2i_edit_when_official_variant_exists() -> None:
    from app.image_product.resolve import resolve_image_capability

    cap = resolve_image_capability(
        {
            "prompt": "edit the chair",
            "purpose": "project_prop",
            "source": "api",
            "hostedModelId": "gpt-image-2-kie",
            "source_asset_id": "asset-ref-2",
        }
    )
    assert cap["canExecute"] is True
    assert cap["provider"] == "kie"
    assert cap["adapter"] == "kie"
    assert cap["officialModelId"] == "gpt-image-2-image-to-image"
    assert cap["workflowKey"] == "kie:gpt-image-2-image-to-image"


def test_resolver_local_flux_is_not_kie() -> None:
    from app.image_product.resolve import resolve_image_capability

    cap = resolve_image_capability(
        {
            "prompt": "a mug",
            "purpose": "project_prop",
            "source": "local",
            "modelFamilyPreference": "flux",
            "model": "flux",
            "forceWorkflowKey": "flux.txt2img",
        }
    )
    assert cap["canExecute"] is True
    assert cap["provider"] != "kie"
    assert cap["provider"] == "local"
    assert not str(cap.get("workflowKey") or "").startswith("kie:")

def test_resolver_refuses_qwen2512_edit_never_zimage_ref_edit() -> None:
    from app.image_product.resolve import resolve_image_capability

    for body in (
        {
            "prompt": "edit the room",
            "purpose": "image_edit",
            "source": "local",
            "model": "qwen2512",
            "modelFamilyPreference": "qwen2512",
            "operation": "image.edit",
            "edit": True,
            "source_asset_id": "caa72759-d965-41f9-b1d5-77cdcf9b9614",
        },
        {
            "prompt": "edit the room",
            "purpose": "image_edit",
            "source": "local",
            "model": "qwen-image-2512",
            "operation": "image.edit",
            "sourceAssetId": "atlas-ref-1",
        },
    ):
        cap = resolve_image_capability(body)
        assert cap["canExecute"] is False, body
        reason = str(cap.get("reason") or "").lower()
        assert "qwen" in reason
        assert "zimage.ref_edit" in reason or "zimage" in reason
        assert cap.get("workflowKey") != "zimage.ref_edit"
        assert "zimage.ref_edit" not in str(cap.get("workflowKey") or "")


def test_resolver_ers_purpose_with_plate_uses_qwen_ref() -> None:
    """purpose=environment_reference_sheet + plate must resolve I2I, never T2I."""
    from app.image_product.resolve import resolve_image_capability

    cap = resolve_image_capability(
        {
            "prompt": "Environment reference sheet of one locked environment.",
            "purpose": "environment_reference_sheet",
            "source": "local",
            "model": "qwen2512",
            "modelFamilyPreference": "qwen2512",
            "operation": "image.edit",
            "edit": True,
            "source_asset_id": "caa72759-d965-41f9-b1d5-77cdcf9b9614",
            "sourceAssetId": "caa72759-d965-41f9-b1d5-77cdcf9b9614",
            "referenceImage": "caa72759-d965-41f9-b1d5-77cdcf9b9614",
        }
    )
    assert cap["canExecute"] is True
    assert cap["provider"] == "local"
    assert cap["workflowKey"] == "qwen2512.ref"
    assert "txt2img" not in str(cap.get("workflowKey") or "")
    assert "zimage" not in str(cap.get("workflowKey") or "")
    assert cap["intent"]["operation"] == "image.generate"


def test_resolver_ers_without_source_cannot_execute_t2i() -> None:
    from app.image_product.resolve import resolve_image_capability

    cap = resolve_image_capability(
        {
            "prompt": "a coffee shop",
            "purpose": "environment_reference_sheet",
            "source": "local",
            "model": "qwen2512",
            "modelFamilyPreference": "qwen2512",
            "operation": "image.generate",
        }
    )
    assert cap["canExecute"] is False
    assert "text-to-image" in str(cap.get("reason") or "").lower()
    assert cap.get("workflowKey") != "qwen2512.txt2img"

