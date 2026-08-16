"""Image-product Capability Resolver.

Intent in: purpose, operation, model, references, layout, source.
Out: {canExecute, provider, adapter, officialModelId, workflowKey, reason}.

Not a new service and not a parallel orchestrator. Hosted execute uses
provider adapters (submit / poll / download). Local Comfy uses
image_runtime.local_comfy_adapter (same submit / poll / download verbs).
"""

from __future__ import annotations

from typing import Any


def _intent_from_body(body: dict[str, Any] | None) -> dict[str, Any]:
    src = dict(body or {})
    ctx = src.get("creativeContext") if isinstance(src.get("creativeContext"), dict) else {}
    source = str(
        src.get("source")
        or src.get("providerKind")
        or ctx.get("providerKind")
        or ctx.get("source")
        or ""
    ).strip().lower()
    purpose = str(src.get("purpose") or ctx.get("objective") or "").strip()
    operation = str(src.get("operation") or "image.generate").strip()
    if src.get("edit") or src.get("source_asset_id") or src.get("sourceAssetId"):
        operation = "image.edit"
    if purpose == "environment_reference_sheet":
        # Plate / atlas / character-prop ids are prompt context, not I2I.
        operation = "image.generate"
        layout = "production_ers"
    model = str(
        src.get("hostedModelId")
        or src.get("kieImageModelId")
        or src.get("falImageModelId")
        or src.get("model")
        or src.get("modelId")
        or src.get("modelFamilyPreference")
        or ""
    ).strip()
    references = bool(
        src.get("source_asset_id")
        or src.get("sourceAssetId")
        or src.get("referenceIds")
        or src.get("referenceAssetIds")
        or src.get("refs")
    )
    layout = str(src.get("layout") or ctx.get("layout") or "").strip()
    return {
        "purpose": purpose,
        "operation": operation,
        "model": model,
        "references": references,
        "layout": layout,
        "source": source,
    }


def _refuse(reason: str, **extra: Any) -> dict[str, Any]:
    out = {
        "canExecute": False,
        "provider": str(extra.get("provider") or ""),
        "adapter": str(extra.get("adapter") or ""),
        "officialModelId": str(extra.get("officialModelId") or ""),
        "workflowKey": str(extra.get("workflowKey") or ""),
        "reason": reason,
    }
    out.update({k: v for k, v in extra.items() if k not in out})
    return out


def _ok(
    *,
    provider: str,
    adapter: str,
    official: str,
    workflow_key: str,
    reason: str,
    **extra: Any,
) -> dict[str, Any]:
    out = {
        "canExecute": True,
        "provider": provider,
        "adapter": adapter,
        "officialModelId": official,
        "workflowKey": workflow_key,
        "reason": reason,
    }
    out.update(extra)
    return out



def _is_qwen2512_family(name: str) -> bool:
    """Qwen Image 2512 is T2I-only. No certified edit / I2I workflow."""
    n = str(name or "").strip().lower().replace("_", "-")
    return n in {"qwen2512", "qwen-image-2512", "qwen-image2512"} or n.startswith(
        "qwen2512."
    )


def _refuse_qwen2512_edit(intent: dict[str, Any], family: str) -> dict[str, Any]:
    return _refuse(
        "Qwen Image 2512 has no certified image-to-image / edit workflow. "
        "Refusing silent substitute of zimage.ref_edit.",
        provider="local",
        adapter="comfy",
        officialModelId="qwen2512",
        workflowKey="",
        intent=intent,
        family=family,
    )


def _wants_edit(src: dict[str, Any], intent: dict[str, Any]) -> bool:
    purpose = str(intent.get("purpose") or src.get("purpose") or "").strip()
    if purpose == "environment_reference_sheet":
        return False
    if intent.get("operation") == "image.edit":
        return True
    if src.get("edit") is True:
        return True
    if src.get("source_asset_id") or src.get("sourceAssetId"):
        return True
    return False


def _api_model_selected(src: dict[str, Any], intent: dict[str, Any]) -> bool:
    """True when the creator selected a hosted API model. source=local always wins."""
    if intent.get("source") == "local":
        return False
    from .compile import _local_force_key

    if _local_force_key(src):
        return False
    if intent.get("source") in {"api", "cloud"}:
        return True
    for key in (
        "hostedModelId",
        "kieImageModelId",
        "falImageModelId",
        "kie_image_model_id",
        "fal_image_model_id",
    ):
        if str(src.get(key) or "").strip():
            return True
    return False


def _pick_hosted_route(src: dict[str, Any]) -> tuple[dict[str, str] | None, str]:
    from .compile import _fal_image_route, _kie_image_route

    explicit_kie = str(src.get("kieImageModelId") or src.get("kie_image_model_id") or "").strip()
    explicit_fal = str(src.get("falImageModelId") or src.get("fal_image_model_id") or "").strip()
    kie_route = _kie_image_route(src)
    fal_route = _fal_image_route(src)
    if explicit_kie and kie_route:
        return kie_route, "kie"
    if explicit_fal and fal_route:
        return fal_route, "fal"
    if fal_route and not explicit_kie:
        return fal_route, "fal"
    if kie_route:
        return kie_route, "kie"
    return None, ""


def _kie_supports_i2i(dock: str, official: str) -> bool:
    try:
        from ..hosted_providers.adapters.kie_adapter import kie_image_supports_i2i
    except Exception:
        return False
    return bool(kie_image_supports_i2i(dock) or kie_image_supports_i2i(official))


def resolve_image_capability(body: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve whether this image intent can execute, and on which adapter.

    Refuses (canExecute=false, honest reason — never a silent swap):
    - silent T2I-as-edit (hosted T2I-only model asked to edit)
    - qwen2512 + image.edit / i2i (no certified edit UNET; never zimage.ref_edit)
    - local flux → kie
    - substituting qwen/zimage/comfy for a selected API model
    """
    src = dict(body or {})
    intent = _intent_from_body(src)
    model = str(intent.get("model") or "")
    from .compile import _local_force_key, _request_source

    # Local always stays local. Never alias flux.txt2img / source=local to kie.
    if _request_source(src) == "local" or _local_force_key(src):
        family = str(
            src.get("modelFamilyPreference") or src.get("model") or model or ""
        ).strip()
        force = _local_force_key(src)
        if _wants_edit(src, intent) and (
            _is_qwen2512_family(family) or _is_qwen2512_family(force)
        ):
            return _refuse_qwen2512_edit(intent, family or force)
        return _ok(
            provider="local",
            adapter="comfy",
            official=family,
            workflow_key=force or (f"{family}.txt2img" if family else ""),
            reason="local comfy adapter facade (not kie)",
            hostedModelId="",
            intent=intent,
        )

    route, provider = _pick_hosted_route(src)
    wants_edit = _wants_edit(src, intent)
    api_selected = _api_model_selected(src, intent)

    if route and provider in {"kie", "fal"}:
        official = str(route.get("official") or "")
        dock = str(route.get("dock") or model or official)
        if wants_edit:
            if provider == "kie" and not _kie_supports_i2i(dock, official):
                return _refuse(
                    "Refusing silent T2I-as-edit: "
                    + (model or dock)
                    + " has no image-to-image variant.",
                    provider=provider,
                    adapter=provider,
                    officialModelId=official,
                    hostedModelId=dock,
                    intent=intent,
                )
            if provider == "fal":
                official_l = official.strip().lower()
                if "/edit" not in official_l:
                    return _refuse(
                        "Refusing silent T2I-as-edit: "
                        + (model or dock)
                        + " has no image-to-image variant.",
                        provider=provider,
                        adapter=provider,
                        officialModelId=official,
                        hostedModelId=dock,
                        intent=intent,
                    )
        return _ok(
            provider=provider,
            adapter=provider,
            official=official,
            workflow_key=provider + ":" + official,
            reason="hosted " + provider + " adapter " + official,
            hostedModelId=dock,
            intent=intent,
        )

    if api_selected:
        selected = model or "selected API model"
        return _refuse(
            "Refusing silent substitute of qwen/zimage/comfy for selected API model "
            + selected
            + ".",
            intent=intent,
        )

    family = str(src.get("modelFamilyPreference") or src.get("model") or model or "").strip()
    if _wants_edit(src, intent) and _is_qwen2512_family(family):
        return _refuse_qwen2512_edit(intent, family)
    return _ok(
        provider="local",
        adapter="comfy",
        official=family,
        workflow_key=f"{family}.txt2img" if family else "",
        reason="local comfy path",
        hostedModelId="",
        intent=intent,
    )
