"""Legacy imagegen params → ImageIntent normalization (sunset path for Wave 3)."""

from __future__ import annotations

from typing import Any

from .intent import ImageIntent


def normalize_legacy_image_params(
    params: dict[str, Any],
    *,
    project_id: str,
    job_kind: str = "imagegen",
) -> tuple[ImageIntent, dict[str, Any]]:
    """
    Normalize once into ImageIntent. Record compatibility for Wave 3 elimination.
    No permanent second execution language.
    """
    edit_op = params.get("edit_op") or ("generate" if job_kind == "imagegen" else "edit")
    source_asset_id = params.get("source_asset_id")
    is_edit = job_kind == "imagegen_edit" or bool(params.get("edit")) or bool(source_asset_id)

    model = (params.get("model") or params.get("engine") or "zimage").lower()
    if model in {"z-image", "z_image", "auto"}:
        engine = "zimage"
    elif model.startswith("flux"):
        engine = "flux"
    elif model.startswith("qwen"):
        engine = "qwen"
    elif model.startswith("imagen"):
        engine = "imagen"
    else:
        engine = model if model not in {"", "auto"} else "zimage"

    operation = "image.edit" if is_edit else "image.generate"
    if edit_op in {"upscale", "image.upscale"}:
        operation = "image.upscale"

    workflow_pref = params.get("workflow_key") or params.get("workflowKey")
    if not workflow_pref:
        if is_edit and engine == "zimage":
            workflow_pref = "zimage.ref_edit"
        elif not is_edit and engine == "zimage":
            workflow_pref = "zimage.txt2img"

    intent = ImageIntent(
        projectId=project_id,
        operation=operation,  # type: ignore[arg-type]
        purpose=str(params.get("purpose") or edit_op or ""),
        prompt=str(params.get("prompt") or ""),
        negativePrompt=str(params.get("negative") or ""),
        referenceIds=list(params.get("reference_ids") or params.get("referenceIds") or []),
        style=dict(params.get("style")) if isinstance(params.get("style"), dict) else {},
        providerPreference=str(params.get("provider") or params.get("providerPreference") or "local"),
        workflowPreference=workflow_pref,
        enginePreference=engine,
        seed=int(params["seed"]) if params.get("seed") is not None else None,
        width=int(params["width"]) if params.get("width") is not None else None,
        height=int(params["height"]) if params.get("height") is not None else None,
        sourceAssetId=str(source_asset_id) if source_asset_id else None,
        metadata={
            "edit_op": edit_op,
            "checkpoint": params.get("checkpoint"),
            "denoise": params.get("denoise"),
            "steps": params.get("steps"),
            "cfg": params.get("cfg"),
            "tag": params.get("tag"),
            "labels": params.get("labels"),
            "loras": params.get("loras") or [],
            "aspect": params.get("aspect"),
        },
        productionIntentId=params.get("productionIntentId") or params.get("production_intent_id"),
        creativeContextDigest=params.get("creative_context_digest") or params.get("creativeContextDigest"),
    )

    compatibility = {
        "legacyInputUsed": True,
        "normalizedBy": "m42-wave2-adapter",
        "jobKind": job_kind,
        "originalModel": params.get("model"),
    }
    return intent, compatibility


def extract_legacy_caller_hint(params: dict[str, Any]) -> str:
    return str(
        params.get("legacyCaller")
        or params.get("caller")
        or params.get("toolId")
        or params.get("m32a")
        or "unknown"
    )
