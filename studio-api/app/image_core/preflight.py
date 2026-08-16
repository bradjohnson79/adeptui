"""Fail before enqueue when the selected model cannot perform the operation."""

from __future__ import annotations

from .capability import (
    ADD_INSERT_SIZE,
    ADD_INSERT_WORKFLOW,
    certified_visual_edit_path,
    family_region_edit_capability,
    generate_workflow_key,
    inpaint_workflow,
    is_add_insert_family,
    normalize_family,
)
from .errors import UNSUPPORTED_OPERATION
from .recommend import recommend
from .request import IMAGE_CORE_PURPOSES, CapabilityDecision, ImageCoreRequest
from .resolution import resolve_resolution

REGION_EDIT_UNSUPPORTED_MESSAGE = (
    "This generator cannot edit a region. Choose Z-Image for Native Inpaint."
)
VISUAL_INHERITANCE_BLOCKED_MESSAGE = (
    "This generator cannot keep the painted correction. Choose Z-Image or FLUX for Final Quality Render."
)

_EDIT_OPS = {"image.edit", "image.reference", "reference_edit", "image.inpaint", "native_inpaint"}
_INPAINT_OPS = {"image.inpaint", "native_inpaint", "image.object_remove", "image.object_replace"}
_GENERATE_OPS = {"image.generate", "text_to_image", "txt2img"}


def _request_has_identity_refs(request: ImageCoreRequest) -> bool:
    extra = request.extra or {}
    if str(extra.get("referenceImage") or extra.get("reference_image") or "").strip():
        return True
    if extra.get("referenceIds") or extra.get("referenceAssetIds"):
        return True
    ctx = request.creative_context or {}
    ids = ctx.get("reference_image_ids") if isinstance(ctx, dict) else None
    return bool(ids)


def _certified_workflow(workflow_key: str) -> bool:
    try:
        from ..image_runtime.certified_registry import get_workflow
    except Exception:
        return False
    wf = get_workflow(workflow_key)
    if wf is None:
        return False
    return str(getattr(wf, "status", "") or "") == "Certified"


def preflight(request: ImageCoreRequest) -> CapabilityDecision:
    family = normalize_family(request.model_id)
    purpose = (request.purpose or "").strip().lower()
    operation = (request.operation or "").strip().lower()
    rec = recommend(request.edit_operation or operation, family)
    caps = family_region_edit_capability(family)
    if purpose and purpose not in IMAGE_CORE_PURPOSES:
        return CapabilityDecision(
            ok=False,
            code=UNSUPPORTED_OPERATION,
            message=f"Unknown Image Core purpose: {purpose}",
            family=family,
            recommended_family=str(rec.get("recommendedFamily") or ""),
            supported=False,
        )

    if request.provider == "cloud" and not (request.hosted_model_id or request.extra.get("hostedModelId")):
        return CapabilityDecision(
            ok=False,
            code=UNSUPPORTED_OPERATION,
            message="API Generation — Not Available",
            family=family,
            recommended_family=str(rec.get("recommendedFamily") or ""),
            supported=False,
        )

    workflow_key = ""
    runtime_op = operation or "image.generate"
    denoise = None
    grow = None

    if purpose in {"region_edit", "final_region_edit"} or request.edit_operation:
        if is_add_insert_family(family):
            if (request.edit_operation or "").strip().lower() != "add":
                return CapabilityDecision(
                    ok=False,
                    code=UNSUPPORTED_OPERATION,
                    message="Nano Banana 2 is recommended for Add only. Choose FLUX for Remove, Modify, or Replace.",
                    family=family,
                    recommended_family=str(rec.get("recommendedFamily") or "flux"),
                    supported=False,
                )
            workflow_key = ADD_INSERT_WORKFLOW
            runtime_op = "image.edit"
            try:
                from ..scene_creator.region_edit_profiles import operation_profile

                profile = operation_profile("add", expand=request.expand, feather=request.feather)
                denoise = float(profile["denoise"])
                grow = int(profile["grow_mask_by"])
            except Exception:
                denoise = None
                grow = None
            width, height = ADD_INSERT_SIZE
            return CapabilityDecision(
                ok=True,
                family=family,
                workflow_key=workflow_key,
                runtime_operation=runtime_op,
                width=width,
                height=height,
                denoise=denoise,
                grow_mask_by=grow,
                recommended_family=str(rec.get("recommendedFamily") or ""),
                supported=True,
                details={"recommend": rec},
            )
        if not caps.get("supportsInpaint") and not caps.get("supportsEditing"):
            return CapabilityDecision(
                ok=False,
                code=UNSUPPORTED_OPERATION,
                message=REGION_EDIT_UNSUPPORTED_MESSAGE,
                family=family,
                recommended_family=str(rec.get("recommendedFamily") or ""),
                supported=False,
            )
        if caps.get("supportsInpaint"):
            pair = inpaint_workflow(family)
            if not pair or not _certified_workflow(pair[0]):
                return CapabilityDecision(
                    ok=False,
                    code=UNSUPPORTED_OPERATION,
                    message=REGION_EDIT_UNSUPPORTED_MESSAGE,
                    family=family,
                    recommended_family=str(rec.get("recommendedFamily") or ""),
                    supported=False,
                )
            workflow_key, runtime_op = pair
        else:
            path = certified_visual_edit_path(family)
            if not path:
                return CapabilityDecision(
                    ok=False,
                    code=UNSUPPORTED_OPERATION,
                    message=REGION_EDIT_UNSUPPORTED_MESSAGE,
                    family=family,
                    recommended_family=str(rec.get("recommendedFamily") or ""),
                    supported=False,
                )
            workflow_key = str(path["workflowKey"])
            runtime_op = str(path["operation"])
        try:
            from ..scene_creator.region_edit_profiles import operation_profile

            profile = operation_profile(request.edit_operation or "modify", expand=request.expand, feather=request.feather)
            denoise = float(profile["denoise"])
            grow = int(profile["grow_mask_by"])
        except Exception:
            denoise = None
            grow = None

    elif operation in _INPAINT_OPS:
        pair = inpaint_workflow(family)
        if not pair or not _certified_workflow(pair[0]):
            return CapabilityDecision(
                ok=False,
                code=UNSUPPORTED_OPERATION,
                message=REGION_EDIT_UNSUPPORTED_MESSAGE,
                family=family,
                recommended_family=str(rec.get("recommendedFamily") or ""),
                supported=False,
            )
        workflow_key, runtime_op = pair

    elif operation in _EDIT_OPS or (request.source_asset_id and purpose in {"scene_shot_final", "scene_shot_preview"}):
        path = certified_visual_edit_path(family)
        if not path:
            if purpose == "scene_shot_preview" and not request.source_asset_id:
                workflow_key = generate_workflow_key(family) or ""
                runtime_op = "image.generate"
            else:
                return CapabilityDecision(
                    ok=False,
                    code=UNSUPPORTED_OPERATION,
                    message=VISUAL_INHERITANCE_BLOCKED_MESSAGE,
                    family=family,
                    recommended_family=str(rec.get("recommendedFamily") or "flux"),
                    supported=False,
                )
        else:
            workflow_key = str(path["workflowKey"])
            runtime_op = str(path["operation"])

    elif operation in _GENERATE_OPS or purpose in {"scene_shot_preview", "scene_shot_final"}:
        if _request_has_identity_refs(request):
            path = certified_visual_edit_path(family)
            if path:
                workflow_key = str(path["workflowKey"])
                runtime_op = str(path["operation"])
            else:
                workflow_key = generate_workflow_key(family) or ""
                runtime_op = "image.generate"
        else:
            workflow_key = generate_workflow_key(family) or ""
            runtime_op = "image.generate"
        if workflow_key and not _certified_workflow(workflow_key) and purpose != "scene_shot_preview":
            # Draft preview may allowDraft; Final must be Certified.
            if purpose == "scene_shot_final":
                return CapabilityDecision(
                    ok=False,
                    code=UNSUPPORTED_OPERATION,
                    message=f"No certified generate workflow for {family}.",
                    family=family,
                    supported=False,
                )

    else:
        workflow_key = generate_workflow_key(family) or ""
        runtime_op = operation or "image.generate"

    if workflow_key and "txt2img" in workflow_key and (
        purpose in {"region_edit", "final_region_edit"} or request.edit_operation
    ):
        return CapabilityDecision(
            ok=False,
            code=UNSUPPORTED_OPERATION,
            message=REGION_EDIT_UNSUPPORTED_MESSAGE,
            family=family,
            supported=False,
        )

    width, height = resolve_resolution(
        family,
        runtime_op,
        purpose,
        workflow_key=workflow_key,
        aspect_ratio=request.aspect_ratio or str((request.extra or {}).get("aspectRatio") or ""),
    )
    return CapabilityDecision(
        ok=True,
        family=family,
        workflow_key=workflow_key,
        runtime_operation=runtime_op,
        width=width,
        height=height,
        denoise=denoise,
        grow_mask_by=grow,
        recommended_family=str(rec.get("recommendedFamily") or ""),
        supported=True,
        details={"recommend": rec},
    )
