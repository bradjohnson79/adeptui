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
from .errors import MODEL_NOT_INSTALLED, PROVIDER_AUTH_FAILED, UNSUPPORTED_OPERATION
from .recommend import recommend
from .request import IMAGE_CORE_PURPOSES, CapabilityDecision, ImageCoreRequest
from .resolution import resolve_resolution

REGION_EDIT_UNSUPPORTED_MESSAGE = (
    "This generator cannot edit a region. Choose Z-Image for Native Inpaint."
)

# Component ids verified by setup/diagnostics — the same authority the worker
# uses at execution time (queue_worker._zimage_stack_ready). A selected local
# model whose weights do not verify on disk must fail BEFORE enqueue with an
# actionable message; never enqueue a job that would silently substitute
# another model at execution (CDX-076).
_LOCAL_MODEL_COMPONENTS = {
    "zimage": "zimage_models",
    "qwen2512": "qwen_image_2512_models",
}


def local_model_installed(family: str) -> tuple[bool, str]:
    """Return (installed, detail) for a local model family, or (True, "") when
    the family has no component-level verification (e.g. cloud-only families,
    unknown ids, or when the verification layer itself is unavailable)."""
    component_id = _LOCAL_MODEL_COMPONENTS.get(family or "")
    if not component_id:
        return True, ""
    try:
        from ..setup.diagnostics import verify_component

        result = verify_component(component_id)
    except Exception:
        # Verification infra unavailable — do not fabricate a block here.
        return True, ""
    if getattr(result, "healthy", False):
        return True, ""
    detail = str(getattr(result, "summary", "") or "")
    return False, detail or "Model files are not verified on disk."
VISUAL_INHERITANCE_BLOCKED_MESSAGE = (
    "This generator cannot keep the painted correction. Choose Z-Image or FLUX for Final Quality Render."
)
REFERENCES_UNSUPPORTED_MESSAGE = (
    "This generator cannot use reference images (characters/props/environment). "
    "Choose Z-Image or FLUX, or clear placed references."
)
HOSTED_CREDENTIAL_MESSAGE = (
    "Hosted AI provider credential not configured. Open Setup → AI Providers "
    "(Kie.ai · WaveSpeed.ai · fal.ai)."
)

_EDIT_OPS = {"image.edit", "image.reference", "reference_edit", "image.inpaint", "native_inpaint"}
_INPAINT_OPS = {"image.inpaint", "native_inpaint", "image.object_remove", "image.object_replace"}
_GENERATE_OPS = {"image.generate", "text_to_image", "txt2img"}


def request_has_identity_refs(request: ImageCoreRequest) -> bool:
    """True when the request carries pixel references the graph must load.

    Recognizes explicit reference ids (referenceImage / referenceIds /
    reference_image_ids) and Scene Creator reference packets whose roles still
    carry an asset but were marked unsupported/semantic_only for the selected
    family — those refs must never be silently dropped by a txt2img fallback.
    prompt_only diagnostic mode intentionally omits refs and is not treated as
    a reference-bearing request.
    """
    extra = request.extra or {}
    if str(extra.get("referenceImage") or extra.get("reference_image") or "").strip():
        return True
    if extra.get("referenceIds") or extra.get("referenceAssetIds"):
        return True
    ctx = request.creative_context or {}
    ids = ctx.get("reference_image_ids") if isinstance(ctx, dict) else None
    if ids:
        return True
    if isinstance(ctx, dict):
        mode = str(ctx.get("diagnosticMode") or "").strip().lower()
        if mode == "prompt_only":
            return False
        pkt = ctx.get("referencePacket") if isinstance(ctx.get("referencePacket"), dict) else None
        if isinstance(pkt, dict):
            for role in list(pkt.get("roles") or []):
                if not isinstance(role, dict):
                    continue
                if str(role.get("consumption") or "") in {"unsupported", "semantic_only"} and str(
                    role.get("assetId") or ""
                ).strip():
                    return True
    return False


# Back-compat alias (private name was internal to this module).
_request_has_identity_refs = request_has_identity_refs


def _certified_workflow(workflow_key: str) -> bool:
    try:
        from ..image_runtime.certified_registry import get_workflow
    except Exception:
        return False
    wf = get_workflow(workflow_key)
    if wf is None:
        return False
    return str(getattr(wf, "status", "") or "") == "Certified"


def _provider_secret_configured(secret_name: str) -> bool:
    try:
        from ..secrets_store import get_secret

        return bool(get_secret(secret_name))
    except Exception:
        return False


def _fal_credential_configured() -> bool:
    """Fal key present. The add-insert path is forced to a fal job in generate."""
    return _provider_secret_configured("fal_api_key")


def _cloud_credential_missing(request: ImageCoreRequest) -> str:
    """Provider id whose credential is required for a cloud request, or "" when ok."""
    extra = request.extra or {}
    if str(extra.get("falImageModelId") or "").strip():
        return "" if _provider_secret_configured("fal_api_key") else "fal"
    if str(extra.get("kieImageModelId") or "").strip():
        return "" if _provider_secret_configured("kie_api_key") else "kie"
    hosted = str(request.hosted_model_id or extra.get("hostedModelId") or "").strip().lower()
    for suffix, secret, pid in (
        ("-fal", "fal_api_key", "fal"),
        ("-kie", "kie_api_key", "kie"),
        ("-wavespeed", "wavespeed_api_key", "wavespeed"),
    ):
        if hosted.endswith(suffix):
            return "" if _provider_secret_configured(secret) else pid
    # Provider not pinned: any configured hosted-provider credential satisfies the gate.
    for secret in ("kie_api_key", "wavespeed_api_key", "fal_api_key"):
        if _provider_secret_configured(secret):
            return ""
    return "any"


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

    if request.provider == "cloud":
        missing_provider = _cloud_credential_missing(request)
        if missing_provider:
            return CapabilityDecision(
                ok=False,
                code=PROVIDER_AUTH_FAILED,
                message=HOSTED_CREDENTIAL_MESSAGE,
                family=family,
                recommended_family=str(rec.get("recommendedFamily") or ""),
                supported=False,
                details={"missingProvider": missing_provider},
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
            if not _fal_credential_configured():
                # The add-insert path is forced to a fal job at enqueue
                # (generate._to_body sets providerPreference=cloud). Never
                # enqueue without a fal credential (CDX-078).
                return CapabilityDecision(
                    ok=False,
                    code=PROVIDER_AUTH_FAILED,
                    message=HOSTED_CREDENTIAL_MESSAGE,
                    family=family,
                    recommended_family=str(rec.get("recommendedFamily") or ""),
                    supported=False,
                    details={"missingProvider": "fal"},
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
                if request_has_identity_refs(request):
                    return CapabilityDecision(
                        ok=False,
                        code=UNSUPPORTED_OPERATION,
                        message=REFERENCES_UNSUPPORTED_MESSAGE,
                        family=family,
                        recommended_family=str(rec.get("recommendedFamily") or "flux"),
                        supported=False,
                    )
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
        if request_has_identity_refs(request):
            path = certified_visual_edit_path(family)
            if path:
                workflow_key = str(path["workflowKey"])
                runtime_op = str(path["operation"])
            else:
                # Never silently downgrade a reference-bearing request to
                # txt2img — the references would never reach the graph (CDX-079).
                return CapabilityDecision(
                    ok=False,
                    code=UNSUPPORTED_OPERATION,
                    message=REFERENCES_UNSUPPORTED_MESSAGE,
                    family=family,
                    recommended_family=str(rec.get("recommendedFamily") or ""),
                    supported=False,
                )
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
    if request.provider != "cloud" and (request.model_id or "").strip():
        installed, detail = local_model_installed(family)
        if not installed:
            return CapabilityDecision(
                ok=False,
                code=MODEL_NOT_INSTALLED,
                message=(
                    f"{family or request.model_id} is selected but its model files are not "
                    f"installed or verified: {detail} No alternate model will be used. "
                    "Open Source Manager, link the shared models root, then retry."
                ),
                family=family,
                supported=False,
                details={"component": _LOCAL_MODEL_COMPONENTS.get(family or "")},
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
