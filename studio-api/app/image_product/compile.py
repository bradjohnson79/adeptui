"""Compile CreativeContext + request → ImageIntent (M42 W3)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..image_runtime.intent import ImageIntent
from .presets import apply_preset_to_request, get_preset
from .prompt_intel import expand_prompt
from .recommend import recommend_image_family
from .references import normalize_ui_refs


def _request_source(body: dict[str, Any] | None) -> str:
    src = dict(body or {})
    ctx = src.get("creativeContext") if isinstance(src.get("creativeContext"), dict) else {}
    return str(
        src.get("source")
        or src.get("providerKind")
        or ctx.get("providerKind")
        or ctx.get("source")
        or ""
    ).strip().lower()


def _local_force_key(body: dict[str, Any] | None) -> str:
    key = str((body or {}).get("forceWorkflowKey") or "").strip()
    if not key:
        return ""
    if key.startswith("kie:") or key.startswith("fal:") or key.startswith("fal-ai/"):
        return ""
    return key


def _kie_image_route(body: dict[str, Any] | None) -> dict[str, str] | None:
    """If the request selected a Kie API dock, return dock + official Market model.

    Local family "flux" / source=local / forceWorkflowKey flux.txt2img is NOT a
    Kie dock. Bare "flux" and modelFamilyPreference=flux stay local. Hosted
    flux-kie is a separate path only when the user selected that API model
    (hostedModelId / kieImageModelId / dock id flux-kie).
    """
    src = dict(body or {})
    if _request_source(src) == "local":
        return None
    if _local_force_key(src):
        return None
    i2i = bool(src.get("source_asset_id") or src.get("sourceAssetId") or src.get("edit"))
    try:
        from ..hosted_providers.adapters.kie_adapter import (
            KIE_IMAGE_T2I_BY_DOCK,
            kie_image_model_id_for_dock,
        )
    except Exception:
        return None
    official_ids = set(KIE_IMAGE_T2I_BY_DOCK.values())
    pinned = str(src.get("kieImageModelId") or src.get("kie_image_model_id") or "").strip()
    if pinned:
        official = kie_image_model_id_for_dock(pinned, image_to_image=i2i)
        if not official and pinned in official_ids:
            official = pinned
        if official:
            dock = str(src.get("hostedModelId") or "").strip() or pinned
            return {"dock": dock, "official": official}
    for raw in (
        src.get("hostedModelId"),
        src.get("model"),
        src.get("modelId"),
    ):
        dock = str(raw or "").strip()
        if not dock:
            continue
        official = kie_image_model_id_for_dock(dock, image_to_image=i2i)
        if official:
            return {"dock": dock, "official": official}
    return None


def _fal_image_route(body: dict[str, Any] | None) -> dict[str, str] | None:
    src = dict(body or {})
    if _request_source(src) == "local":
        return None
    if _local_force_key(src):
        return None
    try:
        from ..fal_catalog import fal_image_model_id_for_dock
    except Exception:
        return None
    pinned = str(src.get("falImageModelId") or src.get("fal_image_model_id") or "").strip()
    if pinned:
        dock = str(src.get("hostedModelId") or "").strip() or pinned
        return {"dock": dock, "official": pinned}
    for raw in (src.get("hostedModelId"), src.get("model"), src.get("modelId")):
        dock = str(raw or "").strip()
        if not dock:
            continue
        official = fal_image_model_id_for_dock(dock)
        if official:
            return {"dock": dock, "official": official}
    return None


def _hosted_execution_pin(body: dict[str, Any] | None) -> dict[str, Any] | None:
    src = dict(body or {})
    if _request_source(src) == "local":
        return None
    if _local_force_key(src):
        return None
    explicit_kie = str(src.get("kieImageModelId") or src.get("kie_image_model_id") or "").strip()
    explicit_fal = str(src.get("falImageModelId") or src.get("fal_image_model_id") or "").strip()
    kie_route = _kie_image_route(src)
    fal_route = _fal_image_route(src)
    route = None
    provider = ""
    if explicit_kie and kie_route:
        route, provider = kie_route, "kie"
    elif explicit_fal and fal_route:
        route, provider = fal_route, "fal"
    elif fal_route and not explicit_kie:
        route, provider = fal_route, "fal"
    elif kie_route:
        route, provider = kie_route, "kie"
    if not route or provider not in {"kie", "fal"}:
        return None
    official = str(route.get("official") or "")
    dock = str(route.get("dock") or official)
    pin = {
        "workflowKey": f"{provider}:{official}",
        "workflowVersion": "1.0.0",
        "workflowId": f"{provider}:{official}",
        "modelFamily": provider,
        "modelVariant": official,
        "provider": provider,
        "adapter": provider,
        "engine": provider,
        "status": "Certified",
        "officialModelId": official,
        "hostedModelId": dock,
        "canExecute": True,
        "reason": "hosted " + provider + " adapter " + official,
    }
    if provider == "kie":
        pin["kieImageModelId"] = official
    else:
        pin["falImageModelId"] = official
    return pin


def _local_execution_pin(snapshot: dict[str, Any] | None, family: str = "") -> dict[str, Any]:
    out = dict(snapshot or {})
    provider = str(out.get("provider") or "local").strip().lower()
    if provider in {"", "comfy", "comfyui"}:
        provider = "local"
    out["provider"] = provider
    adapter = str(out.get("adapter") or out.get("engine") or "comfy").strip().lower()
    if adapter in {"", "comfyui", "local"}:
        adapter = "comfy"
    out["adapter"] = adapter
    out["officialModelId"] = str(out.get("officialModelId") or out.get("modelVariant") or out.get("modelFamily") or family or "").strip()
    return out


_ASPECT = {
    "1:1": (1024, 1024),
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "2:3": (1024, 1536),
    "3:2": (1536, 1024),
    "21:9": (1920, 820),
    "4:3": (1440, 1080),
}

_RES_SCALE = {"720p": 0.67, "1080p": 1.0, "2K": 1.25, "4K": 2.0}


def _size(aspect: str, resolution: str) -> tuple[int, int]:
    w, h = _ASPECT.get(aspect, (1024, 1024))
    scale = _RES_SCALE.get(resolution, 1.0)
    return max(64, int(w * scale / 8) * 8), max(64, int(h * scale / 8) * 8)


def _digest(ctx: dict[str, Any] | None) -> str | None:
    if not ctx:
        return None
    payload = json.dumps(ctx, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_creative_context(project_id: str, *, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    """Best-effort Bible / identity digest — never sends full Bible into runtime."""
    ctx: dict[str, Any] = {"projectId": project_id}
    extras = extras or {}
    try:
        from ..codirector.production_intent.compiler import compile_creative_context

        packaged = compile_creative_context(
            project_id=project_id,
            scene_id=extras.get("sceneId"),
            objective=str(extras.get("objective") or extras.get("purpose") or ""),
            extra=extras,
        )
        if hasattr(packaged, "model_dump"):
            ctx.update(packaged.model_dump())
        elif isinstance(packaged, dict):
            ctx.update(packaged)
    except Exception:
        pass
    # Professional Wiki projection as shared tool context (image/video/script/audio).
    try:
        from ..db import SessionLocal
        from ..codirector.wiki_intelligence.maintenance import tool_wiki_context

        with SessionLocal() as db:
            wiki_ctx = tool_wiki_context(db, project_id)
            if wiki_ctx.get("ok"):
                ctx["wikiToolContext"] = {
                    "title": wiki_ctx.get("title"),
                    "context": wiki_ctx.get("context") or {},
                    "sourceOfTruth": wiki_ctx.get("sourceOfTruth"),
                }
    except Exception:
        pass
    for k in (
        "visualLanguage",
        "cinematography",
        "cinematographer",
        "lighting",
        "continuity",
        "approvedReferences",
        "spatial",
        "spatialHints",
    ):
        if k in extras:
            ctx[k] = extras[k]
    ctx["digest"] = _digest({k: v for k, v in ctx.items() if k != "digest"})
    return ctx


def compile_image_request(
    project_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """
    Full product compile: preset → prompt intel → recommend → ImageIntent → resolve pin.
    """
    body = dict(body or {})
    preset_applied = None
    if body.get("presetId"):
        preset = get_preset(project_id, str(body["presetId"]))
        if preset:
            preset_applied = apply_preset_to_request(
                preset, subject=str(body.get("subject") or body.get("prompt") or "")
            )
            for k, v in preset_applied.items():
                body.setdefault(k if k != "modelFamilyPreference" else "modelFamilyPreference", v)
            if not body.get("prompt") and preset_applied.get("prompt"):
                body["prompt"] = preset_applied["prompt"]
            body.setdefault("modelFamilyPreference", preset_applied.get("modelFamilyPreference"))

    purpose = str(body.get("purpose") or "")
    if purpose != "environment_reference_sheet":
        try:
            from ..character_identity.four_view_sheet import (
                attach_four_view_sheet_intent,
                is_single_image_four_view,
                strengthen_four_view_prompt,
                four_view_sheet_intent,
            )
            # Full Character Sheet (not a per-view tile): stamp law BEFORE the adapter.
            # A single reference is identity conditioning only and does not change layout.
            if is_single_image_four_view(body):
                attach_four_view_sheet_intent(body)
                if body.get("prompt"):
                    body["prompt"] = strengthen_four_view_prompt(str(body.get("prompt") or ""))
                purpose = "character_sheet"
        except Exception:
            pass
    else:
        from ..codirector.knowledgebase.ers_compiler import apply_ers_compile_to_body

        apply_ers_compile_to_body(body, project_id=project_id)
        purpose = "environment_reference_sheet"
        has_model = any(
            str(body.get(k) or "").strip()
            for k in (
                "hostedModelId",
                "kieImageModelId",
                "falImageModelId",
                "model",
                "modelFamilyPreference",
                "forceWorkflowKey",
            )
        )
        if not has_model:
            body.setdefault("modelFamilyPreference", "qwen2512")
            body.setdefault("model", "qwen2512")
            body.setdefault("source", "local")
    operation = str(body.get("operation") or "image.generate")
    if body.get("edit") or body.get("source_asset_id") or body.get("sourceAssetId"):
        operation = "image.edit"
    if purpose in {"storyboard", "storyboard_frame"}:
        operation = "image.storyboard_frame"
    if purpose == "environment_reference_sheet":
        # ERS is always one Image Core T2I. Atlas / background / map plate /
        # character-prop refs are prompt context only — never I2I pixels.
        operation = "image.generate"
        body.pop("edit", None)
        body.pop("source_asset_id", None)
        body.pop("sourceAssetId", None)
        body.pop("referenceImage", None)
        body.pop("reference_image", None)

    creative_extras = dict(body.get("creativeContext") or {})
    continuity_session_id = body.get("continuitySessionId") or body.get("continuityId")
    if continuity_session_id and not creative_extras.get("continuitySessionId"):
        try:
            from ..image_studio.continuity import get_session, session_to_creative_extras

            session = get_session(project_id, str(continuity_session_id))
            if session:
                for k, v in session_to_creative_extras(session).items():
                    if k not in creative_extras or not creative_extras.get(k):
                        creative_extras[k] = v
                # Prefer session reference/approved frames when UI refs empty
                if not body.get("referenceAssetIds") and not body.get("refs"):
                    body["referenceAssetIds"] = list(
                        dict.fromkeys(
                            list(session.referenceAssetIds)
                            + list(session.approvedImageIds[-4:])
                        )
                    )
        except Exception:
            pass
    if body.get("cinematic") and isinstance(body.get("cinematic"), dict):
        cine = body["cinematic"]
        creative_extras.setdefault(
            "cinematography",
            {
                "lens": cine.get("lens"),
                "shotIntent": cine.get("shotIntent"),
                "aspectRatio": body.get("aspect") or cine.get("aspectRatio"),
            },
        )
        if cine.get("lighting"):
            creative_extras.setdefault("lighting", {"setup": cine.get("lighting")})
        creative_extras.setdefault(
            "visualLanguage",
            {
                "colorTreatment": cine.get("colorTreatment"),
                "visualEra": cine.get("visualEra"),
                "productionStyle": cine.get("productionStyle"),
            },
        )

    creative = build_creative_context(project_id, extras=creative_extras)
    pi = body.get("promptIntelligence") if isinstance(body.get("promptIntelligence"), dict) else None
    creator_prompt = str(
        (pi or {}).get("creatorPrompt")
        or body.get("acceptedPrompt")
        or body.get("prompt")
        or ""
    )
    if body.get("runPromptIntelligence") and creator_prompt and not (pi or {}).get("finalProviderPrompt"):
        try:
            from ..codirector.prompt_intelligence.models import ModulesEnabled, PromptIntelligenceRequest
            from ..codirector.prompt_intelligence.pipeline import enhance as pi_enhance

            mods = body.get("promptIntelligenceModules") or {}
            result = pi_enhance(
                PromptIntelligenceRequest(
                    creatorPrompt=creator_prompt,
                    domain="image",
                    providerId=body.get("providerId"),
                    modelId=body.get("modelId") or body.get("modelFamilyPreference"),
                    engineId=body.get("engineId"),
                    negativePrompt=str(body.get("negative") or body.get("negativePrompt") or "") or None,
                    modulesEnabled=ModulesEnabled.model_validate(mods) if isinstance(mods, dict) and mods else ModulesEnabled(),
                    languageBalance=str(body.get("languageBalance") or "balanced"),  # type: ignore[arg-type]
                )
            )
            pi = result.record.model_dump(mode="json")
        except Exception:
            pi = pi or None

    prompt_info = expand_prompt(
        str((pi or {}).get("finalProviderPrompt") or body.get("acceptedPrompt") or body.get("prompt") or ""),
        purpose=purpose,
        style_hints=dict(body.get("style") or {}),
        continuity_constraints=list((creative.get("prohibitedChanges") or [])[:5]),
        cinematography=dict(creative.get("cinematography") or {}),
        lighting=dict(creative.get("lighting") or {}),
        spatial_hints=list(
            (
                dict(creative.get("spatial") or {}).get("promptHints")
                if isinstance(creative.get("spatial"), dict)
                else creative.get("spatialHints")
            )
            or []
        )[:4],
    )
    if pi and pi.get("finalProviderPrompt"):
        prompt_info["originalPrompt"] = str(pi.get("creatorPrompt") or creator_prompt)
        prompt_info["acceptedPrompt"] = str(pi["finalProviderPrompt"])
        prompt_info["promptIntelligence"] = pi
    elif body.get("acceptedPrompt"):
        prompt_info["acceptedPrompt"] = str(body["acceptedPrompt"])
    elif body.get("useExpandedPrompt", True):
        prompt_info["acceptedPrompt"] = prompt_info["expandedPrompt"]
    else:
        prompt_info["acceptedPrompt"] = prompt_info["originalPrompt"]

    # Resolve a creator-facing visual_style for data-driven style→engine routing.
    # Sources (in priority order): creativeContext.visualStyle,
    # creativeContext.style_layers.user, body.style.styleKey, body.style.key.
    _vs = (
        creative_extras.get("visualStyle")
        or (creative_extras.get("style_layers") or {}).get("user")
        or (body.get("style") or {}).get("styleKey")
        or (body.get("style") or {}).get("key")
        or ""
    )
    visual_style_for_routing = str(_vs or "").strip() or None

    recommendation = recommend_image_family(
        prompt=prompt_info["acceptedPrompt"],
        purpose=purpose,
        operation=operation,
        model_family_preference=body.get("modelFamilyPreference") or body.get("model"),
        quality=str(body.get("quality") or "standard"),
        style=visual_style_for_routing,
    )
    family = recommendation["executionFamily"]
    if body.get("lockModelFamily"):
        locked = str(body.get("modelFamilyPreference") or body.get("model") or "").strip().lower()
        if locked in {"qwen-image-2512", "qwen_image_2512"}:
            locked = "qwen2512"
        if locked:
            family = locked
            recommendation = {
                **recommendation,
                "executionFamily": family,
                "fallbackApplied": False,
                "lockModelFamily": True,
            }

    aspect = str(body.get("aspectRatio") or body.get("aspect") or "1:1")
    resolution = str(body.get("resolution") or "1080p")
    width = int(body["width"]) if body.get("width") else None
    height = int(body["height"]) if body.get("height") else None
    if width is None or height is None:
        width, height = _size(aspect, resolution)

    ref_ids = normalize_ui_refs(project_id, body.get("refs") or body.get("references"))
    if body.get("referenceIds"):
        ref_ids = list(dict.fromkeys(ref_ids + list(body["referenceIds"])))

    source_asset = body.get("sourceAssetId") or body.get("source_asset_id")
    if purpose == "environment_reference_sheet":
        source_asset = None
    spatial_bundle = body.get("spatialReferenceBundle") if isinstance(body.get("spatialReferenceBundle"), dict) else None
    spatial_block = creative_extras.get("spatial") if isinstance(creative_extras.get("spatial"), dict) else {}
    intent = ImageIntent(
        projectId=project_id,
        operation=operation if operation in {
            "image.generate", "image.edit", "image.upscale", "image.inpaint",
            "image.outpaint", "image.chroma_key", "image.reference", "image.storyboard_frame",
        } else ("image.edit" if source_asset else "image.generate"),
        purpose=purpose,
        prompt=prompt_info["acceptedPrompt"],
        negativePrompt=str(body.get("negative") or body.get("negativePrompt") or ""),
        referenceIds=ref_ids,
        style=dict(body.get("style") or {}),
        quality=str(body.get("quality") or "standard"),
        providerPreference="cloud" if family in {"imagen", "kie"} or bool(_kie_image_route(body)) else "local",
        enginePreference=family,
        workflowPreference=None,  # resolver chooses — no product workflow key
        seed=int(body["seed"]) if body.get("seed") is not None else None,
        width=width,
        height=height,
        sourceAssetId=str(source_asset) if source_asset else None,
        creativeContextDigest=creative.get("digest"),
        productionIntentId=body.get("productionIntentId"),
        metadata={
            "aspect": aspect,
            "resolution": resolution,
            "presetId": body.get("presetId"),
            "recommendation": recommendation,
            "promptIntel": prompt_info,
            "sceneId": body.get("sceneId"),
            "shotId": body.get("shotId"),
            "cameraId": body.get("cameraId"),
            "continuityId": body.get("continuityId") or continuity_session_id,
            "continuitySessionId": continuity_session_id,
            "spatialMapId": body.get("spatialMapId") or spatial_block.get("mapId") or (spatial_bundle or {}).get("documentId"),
            "spatialMapVersion": body.get("spatialMapVersion")
            or spatial_block.get("mapVersion")
            or (spatial_bundle or {}).get("documentVersion"),
            "spatialCameraId": body.get("spatialCameraId") or spatial_block.get("cameraId"),
            "spatialSummary": spatial_block.get("summary"),
            "panelId": body.get("panel_id") or body.get("panelId"),
            "characterSheetIntent": body.get("characterSheetIntent") or (
                four_view_sheet_intent() if str(body.get("layout") or "") == "four_view" else None
            ),
            "layout": body.get("layout") or (
                "production_ers" if purpose == "environment_reference_sheet" else None
            ),
            "ersCompiler": (body.get("creativeContext") or {}).get("ersCompiler")
            if purpose == "environment_reference_sheet"
            else None,
            "requiredViews": body.get("requiredViews"),
            "referenceMode": body.get("referenceMode"),
            "fourViewSingleOutput": body.get("fourViewSingleOutput"),
            "batchIndex": body.get("batchIndex"),
            "guidance": body.get("guidance"),
            "edit_op": body.get("edit_op") or body.get("editOp"),
            "masks": body.get("masks") or [],
        },
    )
    try:
        from ..character_identity.four_view_sheet import (
            four_view_sheet_intent,
            is_four_view_sheet_request,
        )

        if purpose != "environment_reference_sheet" and (
            is_four_view_sheet_request(body) or str(body.get("layout") or "") == "four_view"
        ):
            intent.metadata = {**intent.metadata, **four_view_sheet_intent()}
    except Exception:
        pass

    from .resolve import resolve_image_capability

    capability = resolve_image_capability(body)
    if not capability.get("canExecute"):
        raise RuntimeError(str(capability.get("reason") or "Image capability refused"))

    hosted_pin = _hosted_execution_pin(body)
    if hosted_pin:
        provider = hosted_pin["provider"]
        official = hosted_pin["officialModelId"]
        dock = hosted_pin["hostedModelId"]
        intent.providerPreference = "cloud"
        intent.enginePreference = provider
        out = {
            "imageIntent": intent.model_dump(),
            "imageRuntime": hosted_pin,
            "recommendation": {
                "executionFamily": provider,
                "recommendedFamily": provider,
                "fallbackApplied": False,
                "lockModelFamily": True,
                "whyThisModel": "Selected " + provider + " model " + str(dock),
                "estimates": {"costLabel": "Paid hosted API"},
            },
            "promptIntel": prompt_info,
            "creativeContextDigest": creative.get("digest"),
            "presetApplied": preset_applied,
            "allowDraft": False,
            "hostedModelId": dock,
            "officialModelId": official,
        }
        if provider == "kie":
            out["kieImageModelId"] = official
        else:
            out["falImageModelId"] = official
        return out

    from ..image_runtime.contract import resolve_image_workflow

    op_for_resolve = (
        "image.generate" if intent.operation == "image.storyboard_frame" else intent.operation
    )
    force_key = body.get("forceWorkflowKey") if body.get("allow_force_workflow_key") else None
    purpose = str(body.get("purpose") or "")
    requested_draft = bool(body.get("allowDraft") or body.get("allow_draft")) or purpose == "scene_shot_preview"
    try:
        contract = resolve_image_workflow(
            op_for_resolve if not force_key else "txt2img",
            engine=family,
            model_family=family,
            allow_draft=requested_draft,
            force_workflow_key=force_key,
            present_inputs={
                "prompt": intent.prompt,
                "reference_image": (
                    bool(intent.sourceAssetId or intent.referenceIds)
                    and purpose != "environment_reference_sheet"
                ),
                "mask": bool(body.get("masks") or body.get("maskAssetId")),
            },
            provider_preference=intent.providerPreference,
        )
        allow_draft = requested_draft
        if force_key:
            forced_family = str(
                getattr(contract, "model_family", None) or str(force_key).split(".", 1)[0]
            ).strip()
            if forced_family:
                intent.enginePreference = forced_family
                family = forced_family
    except RuntimeError as exc:
        if force_key:
            # Character Sheet / explicit workflow pin: fail visibly. Never silently
            # substitute Z-Image for Illustrious, Qwen, or any forced family.
            msg = str(exc)
            low = msg.lower()
            flux_local = str(family or "").lower() == "flux" or str(force_key).startswith("flux.")
            missing = any(
                s in low
                for s in ("not executable", "not certified", "unknown image workflow")
            )
            if flux_local and missing and "not installed" not in low:
                raise RuntimeError(
                    "FLUX is Not Installed / not supported locally. " + msg
                ) from exc
            raise
        if requested_draft or purpose == "scene_shot_preview":
            raise
        if body.get("lockModelFamily"):
            raise
        purpose = str(body.get("purpose") or "")
        creative_ctx = body.get("creativeContext") or {}
        if not isinstance(creative_ctx, dict):
            creative_ctx = {}
        objective = str(creative_ctx.get("objective") or "")
        if purpose == "project_prop" or objective == "project_prop":
            # Prop Creator pins the requested family. Never silently become zimage.
            raise
        if purpose == "environment_reference_sheet":
            # ERS stays honest T2I on the selected family. Never zimage.ref_edit.
            raise
        # Certified ZImage fallback (unpinned requests only)
        contract = resolve_image_workflow(
            "image.edit" if (intent.sourceAssetId or intent.operation == "image.edit") else "image.generate",
            engine="zimage",
            model_family="zimage",
            allow_draft=False,
            present_inputs={
                "prompt": intent.prompt,
                "reference_image": (
                    bool(intent.sourceAssetId or intent.referenceIds)
                    and purpose != "environment_reference_sheet"
                ),
                "mask": bool(body.get("masks") or body.get("maskAssetId")),
            },
        )
        intent.enginePreference = "zimage"
        allow_draft = False
        recommendation = {
            **recommendation,
            "fallbackApplied": True,
            "executionFamily": "zimage",
            "executionNote": "Preferred family not Certified — using certified ZImage",
        }

    pinned = _local_execution_pin(contract.to_pinned_snapshot(), family)
    pinned["canExecute"] = True
    pinned.setdefault("reason", "local comfy path")
    return {
        "imageIntent": intent.model_dump(),
        "imageRuntime": pinned,
        "recommendation": recommendation,
        "promptIntel": prompt_info,
        "creativeContextDigest": creative.get("digest"),
        "presetApplied": preset_applied,
        "allowDraft": allow_draft,
        "contract": contract.to_dict(),
    }
