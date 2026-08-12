"""Advanced editing operation taxonomy (M42 W4)."""

from __future__ import annotations

from typing import Any

from ..image_runtime.certified_registry import get_workflow

_COMMON_STAGES = [
    "Queued",
    "Preparing",
    "LoadingModels",
    "PreparingControls",
    "PreparingMasks",
    "Sampling",
    "Compositing",
    "Saving",
    "Validating",
    "RegisteringAsset",
    "CreatingVersion",
    "Completed",
]

_PROVENANCE_DERIVED = {
    "relationships": ["derived_from", "edited_from"],
    "provenanceRequired": True,
    "registerOnSuccess": True,
}

_PROVENANCE_UPSCALE = {
    "relationships": ["upscaled_from", "derived_from"],
    "provenanceRequired": True,
    "registerOnSuccess": True,
}

_PROVENANCE_RESTORE = {
    "relationships": ["restored_from", "derived_from"],
    "provenanceRequired": True,
    "registerOnSuccess": True,
}

_FALLBACK_ZIMAGE = {
    "family": "zimage",
    "workflowKey": "zimage.ref_edit",
    "reason": "Certified local reference-edit fallback when preferred family unavailable",
    "requiresUserApproval": True,
}


def _readiness_for_keys(keys: list[str]) -> str:
    statuses = []
    for k in keys:
        wf = get_workflow(k)
        if wf:
            statuses.append(wf.status)
    if "Certified" in statuses:
        return "Certified"
    if "Draft" in statuses:
        return "Draft"
    if "Deferred" in statuses:
        return "Deferred"
    if "Blocked" in statuses:
        return "Blocked"
    return "Unknown"


def _op(
    *,
    required_sources: int = 1,
    optional_refs: list[str] | None = None,
    required_masks: bool = False,
    families: list[str],
    workflow_keys: list[str],
    provenance: dict[str, Any],
    stages: list[str] | None = None,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "requiredSources": required_sources,
        "optionalRefs": optional_refs or [],
        "requiredMasks": required_masks,
        "supportedFamilies": families,
        "candidateWorkflowKeys": workflow_keys,
        "provenancePolicy": provenance,
        "stages": stages or list(_COMMON_STAGES),
        "fallbackPolicy": fallback or dict(_FALLBACK_ZIMAGE),
        "readinessStatus": _readiness_for_keys(workflow_keys),
    }


EDIT_OPERATIONS: dict[str, dict[str, Any]] = {
    "image.inpaint": _op(
        required_masks=True,
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.inpaint", "flux.inpaint", "qwen.edit", "imagen.inpaint"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "masked_by"]},
        fallback={"family": "zimage", "workflowKey": "zimage.inpaint", "reason": "Certified inpaint fallback", "requiresUserApproval": False},
    ),
    "image.outpaint": _op(
        required_masks=False,
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.outpaint", "flux.outpaint", "qwen.edit", "imagen.outpaint"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from"]},
        fallback={"family": "zimage", "workflowKey": "zimage.outpaint", "reason": "Certified outpaint fallback", "requiresUserApproval": False},
    ),
    "image.object_remove": _op(
        required_masks=True,
        families=["zimage", "flux", "imagen"],
        workflow_keys=["zimage.inpaint", "flux.inpaint", "imagen.inpaint"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "masked_by"]},
        fallback={"family": "zimage", "workflowKey": "zimage.inpaint", "reason": "Object removal via certified inpaint", "requiresUserApproval": False},
    ),
    "image.object_replace": _op(
        required_masks=True,
        optional_refs=["appearance", "prop", "wardrobe"],
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.inpaint", "flux.inpaint", "flux.fill", "imagen.inpaint"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "masked_by", "referenced"]},
    ),
    "image.background_remove": _op(
        required_masks=False,
        families=["zimage", "flux", "imagen"],
        workflow_keys=["image.background_remove", "zimage.inpaint", "flux.fill"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from"]},
    ),
    "image.background_replace": _op(
        required_masks=True,
        optional_refs=["environment", "style", "lighting"],
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.inpaint", "zimage.ref_edit", "flux.fill", "imagen.edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "masked_by", "referenced"]},
    ),
    "image.relight": _op(
        optional_refs=["lighting", "palette", "style"],
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.ref_edit", "flux.edit", "qwen.edit", "imagen.edit"],
        provenance=_PROVENANCE_DERIVED,
    ),
    "image.recolor": _op(
        optional_refs=["palette", "style"],
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.ref_edit", "flux.edit", "qwen.edit", "imagen.edit"],
        provenance=_PROVENANCE_DERIVED,
    ),
    "image.style_transfer": _op(
        optional_refs=["style", "appearance"],
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.ref_edit", "flux.reference_edit", "qwen.reference_edit", "imagen.edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "referenced"]},
    ),
    "image.reference_edit": _op(
        optional_refs=["identity", "appearance", "wardrobe", "environment", "style", "lighting", "composition"],
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.ref_edit", "flux.reference_edit", "qwen.reference_edit", "imagen.edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "referenced"]},
        fallback={"family": "zimage", "workflowKey": "zimage.ref_edit", "reason": "Certified reference edit", "requiresUserApproval": False},
    ),
    "image.pose_guided_edit": _op(
        optional_refs=["pose"],
        families=["zimage", "flux", "qwen"],
        workflow_keys=["control.pose", "zimage.ref_edit", "flux.edit", "qwen.edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "guided_by"]},
    ),
    "image.depth_guided_edit": _op(
        optional_refs=["composition"],
        families=["zimage", "flux", "qwen"],
        workflow_keys=["control.depth", "zimage.ref_edit", "flux.edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "guided_by"]},
    ),
    "image.edge_guided_edit": _op(
        optional_refs=["composition"],
        families=["zimage", "flux", "qwen"],
        workflow_keys=["control.canny", "control.lineart", "zimage.ref_edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "guided_by"]},
    ),
    "image.structure_guided_edit": _op(
        optional_refs=["composition", "pose"],
        families=["zimage", "flux", "qwen"],
        workflow_keys=["control.pose", "control.depth", "control.canny", "zimage.ref_edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from", "guided_by"]},
    ),
    "image.multi_reference_compose": _op(
        optional_refs=["identity", "appearance", "wardrobe", "pose", "environment", "style", "lighting", "composition", "palette", "prop"],
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["qwen.multi_reference", "zimage.ref_edit", "flux.reference_edit", "imagen.edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "composited_with", "referenced"]},
    ),
    "image.composite": _op(
        required_sources=2,
        optional_refs=["foreground", "background", "style"],
        families=["zimage", "flux", "qwen"],
        workflow_keys=["image.composite", "zimage.ref_edit", "flux.edit"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "composited_with"]},
    ),
    "image.restore": _op(
        families=["zimage", "flux", "qwen"],
        workflow_keys=["image.restore", "zimage.ref_edit", "zimage.inpaint"],
        provenance=_PROVENANCE_RESTORE,
    ),
    "image.face_restore": _op(
        required_masks=True,
        optional_refs=["identity", "appearance"],
        families=["zimage", "flux"],
        workflow_keys=["image.face_restore", "zimage.inpaint", "zimage.ref_edit"],
        provenance=_PROVENANCE_RESTORE,
    ),
    "image.detail_enhance": _op(
        families=["zimage", "flux", "qwen"],
        workflow_keys=["zimage.ref_edit", "image.upscale", "flux.edit"],
        provenance=_PROVENANCE_DERIVED,
    ),
    "image.upscale": _op(
        required_masks=False,
        families=["zimage"],
        workflow_keys=["image.upscale"],
        provenance=_PROVENANCE_UPSCALE,
        fallback={"family": "zimage", "workflowKey": "zimage.ref_edit", "reason": "Upscale not certified — ref_edit interim", "requiresUserApproval": True},
    ),
    "image.crop_extend": _op(
        required_masks=False,
        families=["zimage", "flux", "qwen", "imagen"],
        workflow_keys=["zimage.outpaint", "flux.outpaint", "imagen.outpaint"],
        provenance=_PROVENANCE_DERIVED,
        fallback={"family": "zimage", "workflowKey": "zimage.outpaint", "reason": "Canvas extension via outpaint", "requiresUserApproval": False},
    ),
    "image.transparent_extract": _op(
        required_masks=True,
        families=["zimage", "flux", "imagen"],
        workflow_keys=["image.transparent_extract", "image.background_remove", "zimage.inpaint"],
        provenance={**_PROVENANCE_DERIVED, "relationships": ["derived_from", "edited_from"]},
    ),
}


def get_operation_spec(operation: str) -> dict[str, Any] | None:
    return EDIT_OPERATIONS.get(operation)


def validate_operation(operation: str) -> None:
    if operation not in EDIT_OPERATIONS:
        raise ValueError(f"Unknown edit operation: {operation}")
