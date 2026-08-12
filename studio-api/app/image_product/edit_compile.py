"""Compile ImageEditIntent → ImageIntent + pinned runtime (M42 W4)."""

from __future__ import annotations

from typing import Any

from ..image_runtime.intent import ImageIntent
from .compile import build_creative_context, _size
from .edit_intent import ImageEditIntent, default_edit_layers, validate_basic
from .edit_ops import validate_operation
from .edit_recommend import recommend_edit
from .layers import ensure_layers_on_intent
from .prompt_intel import expand_prompt
from .recipes import apply_recipe_to_request, get_recipe
from .references import normalize_ui_refs


def _map_operation_to_runtime(operation: str) -> str:
    if operation == "image.upscale":
        return "image.upscale"
    if operation in {"image.inpaint", "image.object_remove", "image.object_replace", "image.face_restore"}:
        return "image.inpaint"
    if operation in {"image.outpaint", "image.crop_extend"}:
        return "image.outpaint"
    if operation in {"image.background_remove", "image.transparent_extract"}:
        return "image.chroma_key"
    if operation in {"image.reference_edit", "image.style_transfer", "image.multi_reference_compose"}:
        return "image.reference"
    return "image.edit"


def compile_edit_request(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """
    Full edit compile: recipe → validate op → creative context → recommend →
    ImageEditIntent → ImageIntent → resolve allow_draft=False with zimage fallback.
    """
    body = dict(body or {})
    body["projectId"] = project_id

    recipe_applied = None
    if body.get("recipeId"):
        recipe = get_recipe(project_id, str(body["recipeId"]))
        if recipe:
            recipe_applied = apply_recipe_to_request(
                recipe, detail=str(body.get("detail") or body.get("prompt") or "")
            )
            for k, v in recipe_applied.items():
                if k == "preferences":
                    body.setdefault("preferences", {}).update(v)
                elif k == "output":
                    body.setdefault("output", {}).update(v)
                else:
                    body.setdefault(k, v)
            if not body.get("prompt") and recipe_applied.get("prompt"):
                body["prompt"] = recipe_applied["prompt"]
            body.setdefault("operation", recipe_applied.get("operation"))

    operation = str(body.get("operation") or "image.inpaint")
    validate_operation(operation)

    source_ids = list(body.get("sourceAssetIds") or [])
    if body.get("sourceAssetId") and body["sourceAssetId"] not in source_ids:
        source_ids.insert(0, str(body["sourceAssetId"]))
    masks = list(body.get("masks") or [])
    ref_ids = list(body.get("referenceAssetIds") or body.get("referenceIds") or [])
    ref_ids = normalize_ui_refs(project_id, ref_ids or body.get("refs") or body.get("references"))

    edit_intent = ImageEditIntent(
        projectId=project_id,
        sourceAssetIds=source_ids,
        operation=operation,
        prompt=body.get("prompt") or body.get("acceptedPrompt"),
        negativePrompt=body.get("negativePrompt") or body.get("negative"),
        masks=masks,
        referenceAssetIds=ref_ids,
        controls=dict(body.get("controls") or {}),
        preferences=dict(body.get("preferences") or {}),
        output=dict(body.get("output") or {}),
        continuity=dict(body.get("continuity") or {}),
        metadata=dict(body.get("metadata") or {}),
        layers=list(body.get("layers") or default_edit_layers()),
        recipeId=body.get("recipeId"),
    )
    edit_dict = ensure_layers_on_intent(edit_intent.to_dict())

    validation_errors = validate_basic(edit_dict)
    if validation_errors and not body.get("allowIncomplete"):
        raise ValueError("; ".join(validation_errors))

    purpose = str((edit_dict.get("metadata") or {}).get("purpose") or body.get("purpose") or "")
    creative = build_creative_context(project_id, extras=body.get("creativeContext") or body)
    prompt_info = expand_prompt(
        str(edit_dict.get("prompt") or ""),
        purpose=purpose or operation,
        style_hints=dict(body.get("style") or {}),
        continuity_constraints=list((creative.get("prohibitedChanges") or [])[:5]),
        cinematography=dict(creative.get("cinematography") or {}),
        lighting=dict(creative.get("lighting") or {}),
    )
    accepted = body.get("acceptedPrompt") or prompt_info.get("expandedPrompt") or prompt_info.get("originalPrompt")
    edit_dict["prompt"] = accepted
    prompt_info["acceptedPrompt"] = accepted

    prefs = edit_dict.get("preferences") or {}
    recommendation = recommend_edit(
        operation=operation,
        prompt=accepted or "",
        purpose=purpose,
        model_family_preference=prefs.get("modelFamilyPreference") or body.get("modelFamilyPreference"),
        source_asset_ids=source_ids,
        has_masks=bool(masks),
        has_references=bool(ref_ids),
        quality=str(body.get("quality") or "standard"),
    )
    family = recommendation["executionFamily"]
    runtime_op = _map_operation_to_runtime(operation)

    output = edit_dict.get("output") or {}
    aspect = str(body.get("aspectRatio") or body.get("aspect") or "1:1")
    resolution = str(output.get("resolution") or body.get("resolution") or "1080p")
    width = output.get("width") or body.get("width")
    height = output.get("height") or body.get("height")
    if width is None or height is None:
        w, h = _size(aspect, resolution)
        width, height = w, h

    intent = ImageIntent(
        projectId=project_id,
        operation=runtime_op,  # type: ignore[arg-type]
        purpose=purpose or operation,
        prompt=accepted or "",
        negativePrompt=str(edit_dict.get("negativePrompt") or ""),
        referenceIds=ref_ids,
        style=dict(body.get("style") or {}),
        quality=str(body.get("quality") or "standard"),
        providerPreference="cloud" if family == "imagen" else "local",
        enginePreference=family,
        workflowPreference=None,
        seed=int(body["seed"]) if body.get("seed") is not None else None,
        width=int(width) if width else None,
        height=int(height) if height else None,
        sourceAssetId=source_ids[0] if source_ids else None,
        creativeContextDigest=creative.get("digest"),
        productionIntentId=body.get("productionIntentId"),
        metadata={
            "aspect": aspect,
            "resolution": resolution,
            "imageEditIntentId": edit_dict.get("intentId"),
            "editOperation": operation,
            "edit_op": operation.replace("image.", ""),
            "recipeId": edit_dict.get("recipeId"),
            "recommendation": recommendation,
            "promptIntel": prompt_info,
            "masks": masks,
            "controls": edit_dict.get("controls"),
            "preferences": prefs,
            "output": output,
            "continuity": edit_dict.get("continuity"),
            "layers": edit_dict.get("layers"),
        },
    )

    from ..image_runtime.contract import resolve_image_workflow

    present_inputs = {
        "prompt": intent.prompt,
        "reference_image": bool(intent.sourceAssetId or intent.referenceIds),
        "mask": bool(masks),
    }
    try:
        contract = resolve_image_workflow(
            runtime_op,
            engine=family,
            model_family=family,
            allow_draft=False,
            present_inputs=present_inputs,
            provider_preference=intent.providerPreference,
        )
    except RuntimeError:
        contract = resolve_image_workflow(
            "image.edit" if intent.sourceAssetId else runtime_op,
            engine="zimage",
            model_family="zimage",
            allow_draft=False,
            present_inputs=present_inputs,
        )
        intent.enginePreference = "zimage"
        recommendation = {
            **recommendation,
            "fallbackApplied": True,
            "executionFamily": "zimage",
            "executionNote": "Preferred family not Certified — using certified ZImage",
        }

    pinned = contract.to_pinned_snapshot()
    return {
        "imageEditIntent": edit_dict,
        "imageIntent": intent.model_dump(),
        "imageRuntime": pinned,
        "recommendation": recommendation,
        "promptIntel": prompt_info,
        "creativeContextDigest": creative.get("digest"),
        "recipeApplied": recipe_applied,
        "validationErrors": validation_errors,
        "allowDraft": False,
        "contract": contract.to_dict(),
    }
