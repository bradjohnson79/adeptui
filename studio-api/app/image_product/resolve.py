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
    references = bool(
        src.get("source_asset_id")
        or src.get("sourceAssetId")
        or src.get("referenceIds")
        or src.get("referenceAssetIds")
        or src.get("refs")
        or src.get("referenceImage")
        or src.get("reference_image")
    )
    if src.get("edit") or src.get("source_asset_id") or src.get("sourceAssetId"):
        operation = "image.edit"
    if purpose == "environment_reference_sheet":
        # Generate-with-reference: pixels ride sourceAssetId / input_urls.
        # Stay image.generate so Qwen does not fall into the refused edit path.
        operation = "image.generate"
        layout = "production_ers"
    elif purpose == "codirector_image_generate" and references:
        operation = "image.generate"
    model = str(
        src.get("hostedModelId")
        or src.get("kieImageModelId")
        or src.get("falImageModelId")
        or src.get("model")
        or src.get("modelId")
        or src.get("modelFamilyPreference")
        or ""
    ).strip()
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
    """Qwen Image 2512 family. Scene Creator edit remains unsupported; ERS uses qwen2512.ref."""
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
    force = str(src.get("forceWorkflowKey") or intent.get("forceWorkflowKey") or "").strip()
    if force in {"qwen2512.ref", "flux.img2img", "flux.reference", "flux.ref"}:
        return False
    if purpose == "codirector_image_generate" and (
        src.get("referenceImage") or src.get("referenceAssetIds") or src.get("reference_image")
    ):
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


def _wavespeed_image_route(src: dict[str, Any]) -> dict[str, str] | None:
    pinned = str(src.get("wavespeedImageModelId") or src.get("wavespeed_image_model_id") or "").strip()
    provider = str(src.get("provider") or src.get("providerKind") or src.get("requested_provider") or "").strip().lower()
    if provider != "wavespeed" and not pinned:
        return None
    official = pinned or str(src.get("hostedModelId") or src.get("model") or "").strip()
    if not official:
        return None
    dock = str(src.get("hostedModelId") or official).strip() or official
    return {"dock": dock, "official": official}


def choose_imagegen_adapter(params: dict[str, Any] | None) -> str:
    """Which hosted adapter may run. An explicit provider is never replaced."""
    from .compile import explicit_hosted_provider

    src = dict(params or {})
    named = explicit_hosted_provider(src)
    if named:
        return named
    if str(src.get("wavespeedImageModelId") or src.get("wavespeed_image_model_id") or "").strip():
        return "wavespeed"
    if str(src.get("provider") or "").strip().lower() == "wavespeed":
        return "wavespeed"
    if str(src.get("falImageModelId") or src.get("fal_image_model_id") or "").strip():
        return "fal"
    if str(src.get("kieImageModelId") or src.get("kie_image_model_id") or "").strip():
        return "kie"
    return ""


def _pick_hosted_route(src: dict[str, Any]) -> tuple[dict[str, str] | None, str]:
    from .compile import _fal_image_route, _kie_image_route, explicit_hosted_provider

    named = explicit_hosted_provider(src)
    if named == "wavespeed":
        route = _wavespeed_image_route(src)
        return (route, "wavespeed") if route else (None, "")
    if named == "fal":
        route = _fal_image_route(src)
        return (route, "fal") if route else (None, "")
    if named == "kie":
        route = _kie_image_route(src)
        return (route, "kie") if route else (None, "")
    wavespeed_route = _wavespeed_image_route(src)
    if wavespeed_route:
        return wavespeed_route, "wavespeed"
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



def _ers_prompt_only_allowed(src: dict, intent: dict) -> bool:
    """Env Creator Express: ERS may run GPT T2I when a text environment prompt is present."""
    ctx = src.get("creativeContext") if isinstance(src.get("creativeContext"), dict) else {}
    if not ctx and isinstance(intent.get("creativeContext"), dict):
        ctx = intent.get("creativeContext") or {}
    prompt = str(
        src.get("environmentPrompt")
        or src.get("environment_prompt")
        or ctx.get("environmentPrompt")
        or src.get("prompt")
        or intent.get("prompt")
        or ""
    ).strip()
    grounding = ctx.get("referenceGrounding") if isinstance(ctx.get("referenceGrounding"), dict) else {}
    mode = str(grounding.get("mode") or "").lower()
    official = str(
        src.get("kieImageModelId") or src.get("kie_image_model_id") or ctx.get("resolvedOfficialModelId") or ""
    ).lower()
    return bool(prompt) or mode == "text" or "text-to-image" in official


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
        if family.lower().startswith("sensenova") or force.lower().startswith("sensenova"):
            return _refuse(
                "SenseNova U1.5 is not part of Adept UI 1.1.",
                provider="local",
                adapter="comfy",
                officialModelId=family or force,
                workflowKey="",
                intent=intent,
            )
        purpose_local = str(intent.get("purpose") or src.get("purpose") or "").strip()
        has_pixels_local = bool(
            intent.get("references")
            or src.get("sourceAssetId")
            or src.get("source_asset_id")
            or src.get("referenceImage")
            or src.get("input_urls")
        )
        if (
            purpose_local == "environment_reference_sheet"
            and not has_pixels_local
            and not _ers_prompt_only_allowed(src, intent)
        ):
            return _refuse(
                "Environment Reference Sheets require an authoritative source image "
                "or an environment prompt. Text-to-image without a prompt is not allowed.",
                provider="local",
                adapter="comfy",
                officialModelId=family,
                workflowKey="",
                intent=intent,
            )
        if _wants_edit(src, intent) and (
            _is_qwen2512_family(family) or _is_qwen2512_family(force)
        ):
            return _refuse_qwen2512_edit(intent, family or force)
        purpose_local_n = str(intent.get("purpose") or src.get("purpose") or "").strip().lower()
        cis_general = purpose_local_n in {
            "",
            "general",
            "concept",
            "keyframe",
            "character",
            "location",
            "prop",
            "mood",
            "storyboard",
        }
        has_ref_pixels = bool(
            intent.get("references")
            or src.get("sourceAssetId")
            or src.get("source_asset_id")
            or src.get("referenceImage")
            or src.get("referenceAssetIds")
            or src.get("authorityReferences")
        )
        qwen_ref_generate = (
            _is_qwen2512_family(family or force)
            and has_ref_pixels
            and (
                purpose_local_n
                in {"environment_reference_sheet", "codirector_image_generate"}
                or (cis_general and str(force or "").strip() in {"", "qwen2512.ref"})
            )
        )
        # CIS multi-ref may honestly route to Qwen Edit 2509 (force key).
        if (
            cis_general
            and has_ref_pixels
            and not force
            and _is_qwen2512_family(family)
        ):
            # Compile should have pinned .ref / 2509; if not, refuse silent T2I.
            return _refuse(
                "Qwen Image 2512 cannot silently run txt2img while reference images are "
                "selected. Use qwen2512.ref (single plate) or Qwen Edit 2509 multi-ref "
                "(character+environment).",
                provider="local",
                adapter="comfy",
                officialModelId=family or "qwen2512",
                workflowKey="",
                intent=intent,
                family=family,
            )
        workflow_key = force or (
            "qwen2512.ref" if qwen_ref_generate else (f"{family}.txt2img" if family else "")
        )
        if (
            cis_general
            and has_ref_pixels
            and str(workflow_key).endswith(".txt2img")
        ):
            return _refuse(
                "Refusing silent txt2img while reference images are selected for Image Generator.",
                provider="local",
                adapter="comfy",
                officialModelId=family,
                workflowKey="",
                intent=intent,
            )
        return _ok(
            provider="local",
            adapter="comfy",
            official=family,
            workflow_key=workflow_key,
            reason="local comfy adapter facade (not kie)",
            hostedModelId="",
            intent=intent,
        )

    route, provider = _pick_hosted_route(src)
    wants_edit = _wants_edit(src, intent)
    api_selected = _api_model_selected(src, intent)

    purpose = str(intent.get("purpose") or src.get("purpose") or "").strip()
    continuity = purpose in {"environment_reference_sheet", "atlas_shot"}
    has_pixels = bool(
        intent.get("references")
        or src.get("sourceAssetId")
        or src.get("source_asset_id")
        or src.get("input_urls")
        or src.get("image_urls")
        or src.get("referenceImage")
    )
    ers_prompt_only = _ers_prompt_only_allowed(src, intent)
    if purpose == "environment_reference_sheet" and not has_pixels and not ers_prompt_only:
        return _refuse(
            "Environment Reference Sheets require an authoritative source image "
            "or an environment prompt. Text-to-image without a prompt is not allowed.",
            provider=provider or "local",
            adapter=provider or "comfy",
            officialModelId="",
            intent=intent,
        )
    if (
        continuity
        and "gpt-image-2" in model.lower()
        and not has_pixels
        and not ers_prompt_only
    ):
        return _refuse(
            "Environment continuity requires an image-conditioned GPT Image 2 path "
            "or an environment prompt for text-to-image.",
            provider="kie",
            adapter="kie",
            officialModelId="",
            intent=intent,
        )

    if route and provider in {"kie", "fal", "wavespeed"}:
        official = str(route.get("official") or "")
        dock = str(route.get("dock") or model or official)
        if continuity and has_pixels and "text-to-image" in official:
            return _refuse(
                "Refusing text-to-image for Spatial Map / ERS: "
                + (model or dock)
                + " must use its image-to-image operation.",
                provider=provider,
                adapter=provider,
                officialModelId=official,
                hostedModelId=dock,
                intent=intent,
            )
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
