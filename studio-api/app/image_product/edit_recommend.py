"""Edit recommendation intelligence (M42 W4)."""

from __future__ import annotations

from typing import Any

from .edit_ops import EDIT_OPERATIONS, get_operation_spec
from .recommend import _estimates, _executable, _family_status, _why


def _resolve_intent_for_op(operation: str) -> str:
    """Map product edit operation to resolver intent."""
    if operation in {"image.inpaint", "image.object_remove", "image.object_replace", "image.face_restore"}:
        return "image.edit"
    if operation in {"image.outpaint", "image.crop_extend"}:
        return "image.edit"
    if operation == "image.upscale":
        return "image.upscale"
    if operation in {"image.reference_edit", "image.style_transfer", "image.relight", "image.recolor"}:
        return "image.reference"
    if operation in {"image.background_remove", "image.transparent_extract"}:
        return "image.chroma_key"
    return "image.edit"


def _mask_strategy(operation: str, spec: dict[str, Any] | None) -> str:
    if not spec or not spec.get("requiredMasks"):
        return "none"
    if operation in {"image.object_remove", "image.background_remove"}:
        return "include_region"
    if operation in {"image.object_replace", "image.background_replace"}:
        return "replace_region"
    if operation in {"image.face_restore", "image.inpaint"}:
        return "localized_brush"
    return "brush"


def recommend_edit(
    *,
    operation: str = "image.inpaint",
    prompt: str = "",
    purpose: str = "",
    model_family_preference: str | None = None,
    source_asset_ids: list[str] | None = None,
    has_masks: bool = False,
    has_references: bool = False,
    quality: str = "standard",
) -> dict[str, Any]:
    spec = get_operation_spec(operation) or EDIT_OPERATIONS.get("image.inpaint", {})
    families = list(spec.get("supportedFamilies") or ["zimage"])
    preferred = (model_family_preference or "").strip().lower() or None

    if preferred and preferred in families:
        primary = preferred
    elif operation in {"image.reference_edit", "image.style_transfer", "image.multi_reference_compose"}:
        primary = "zimage" if "zimage" in families else families[0]
    elif operation == "image.upscale":
        primary = "zimage"
    elif operation in {"image.relight", "image.recolor"}:
        primary = "flux" if "flux" in families else families[0]
    else:
        primary = "zimage" if "zimage" in families else families[0]

    exec_family = primary
    fallback_applied = False
    if not _executable(exec_family):
        for fam in ("zimage", "flux", "qwen", "imagen"):
            if fam in families and _executable(fam):
                exec_family = fam
                fallback_applied = fam != primary
                break
        if not _executable(exec_family) and _executable("zimage"):
            exec_family = "zimage"
            fallback_applied = exec_family != primary

    fallback_policy = dict(spec.get("fallbackPolicy") or {})
    required_inputs = ["sourceImage"]
    if spec.get("requiredMasks"):
        required_inputs.append("editMask")
    optional_inputs = list(spec.get("optionalRefs") or [])
    if has_references:
        optional_inputs = [r for r in optional_inputs if r]

    why = _why(primary, purpose or operation, prompt)
    if operation == "image.object_remove":
        why = "Localized inpaint workflow best for seamless object removal."
    elif operation == "image.reference_edit":
        why = "Reference-guided edit preserves identity cues while applying transformation."
    elif operation == "image.upscale":
        why = "Dedicated upscale workflow increases resolution without regenerating composition."

    return {
        "operation": operation,
        "recommendedFamily": primary,
        "executionFamily": exec_family,
        "status": _family_status(primary),
        "executable": _executable(primary),
        "fallbackApplied": fallback_applied,
        "whyThisModel": why,
        "requiredInputs": required_inputs,
        "optionalInputs": optional_inputs,
        "maskStrategy": _mask_strategy(operation, spec),
        "estimates": _estimates(primary),
        "executionEstimates": _estimates(exec_family),
        "fallback": {
            "family": fallback_policy.get("family", "zimage"),
            "workflowKey": fallback_policy.get("workflowKey"),
            "reason": fallback_policy.get("reason"),
            "requiresUserApproval": bool(fallback_policy.get("requiresUserApproval")),
        },
        "candidateWorkflowKeys": list(spec.get("candidateWorkflowKeys") or []),
        "readinessStatus": spec.get("readinessStatus", "Unknown"),
        "resolverIntent": _resolve_intent_for_op(operation),
        "overridable": True,
        "quality": quality,
        "hasMasks": has_masks,
        "hasReferences": has_references,
        "sourceAssetCount": len(source_asset_ids or []),
    }
