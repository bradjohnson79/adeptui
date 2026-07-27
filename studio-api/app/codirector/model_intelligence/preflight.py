"""Model-aware preflight — BLOCKED means no job / no phantom asset."""

from __future__ import annotations

from typing import Any, Optional

from .compiler import compile_intent
from .registry import binding_for_model
from .resolver import try_resolve
from .schemas import (
    NormalizedGenerationIntent,
    PreflightResult,
    PreflightStatus,
    ProductionReadiness,
)
from .selector import recommend


def run_preflight(
    intent: NormalizedGenerationIntent,
    *,
    model_id: Optional[str] = None,
    engine_id: Optional[str] = None,
    runtime_model_version: Optional[str] = None,
    bible_package: Optional[dict[str, Any]] = None,
    provider_configured: bool = True,
    provider_healthy: bool = True,
    paid_path: bool = False,
    duplicate_guard_ok: bool = True,
) -> PreflightResult:
    rec = recommend(intent)
    chosen = intent.forceModelId or model_id or rec.recommendedModel
    compile_result = compile_intent(
        intent,
        model_id=chosen,
        engine_id=engine_id,
        runtime_model_version=runtime_model_version,
        bible_package=bible_package,
    )

    errors: list[str] = []
    warnings: list[str] = list(compile_result.warnings)

    if compile_result.status == "MODEL_KNOWLEDGE_UNAVAILABLE":
        errors.append(compile_result.status)
        warnings.append("Proceeding without model-specific optimization is degraded mode")

    binding = binding_for_model(compile_result.modelId)
    if binding is None or not binding.capabilityIds:
        errors.append("Selected model is not production-wired (missing capability binding)")

    pack, err = try_resolve(
        model_id=compile_result.modelId,
        runtime_model_version=runtime_model_version,
        allow_non_active=True,
    )
    if pack is None and compile_result.status != "MODEL_KNOWLEDGE_UNAVAILABLE":
        errors.append(err or "pack resolve failed")

    if pack:
        manifest = pack["manifest"]
        if manifest.runtimeStatus == ProductionReadiness.PRODUCT_APPROVAL_REQUIRED:
            errors.append("PRODUCT_APPROVAL_REQUIRED — model cannot be used in production jobs")
        if manifest.runtimeStatus == ProductionReadiness.UNAVAILABLE:
            errors.append("Model unavailable")
        if runtime_model_version and runtime_model_version != manifest.modelVersion:
            warnings.append("Knowledge pack / runtime version mismatch — confidence reduced")

    if not provider_configured:
        errors.append("Provider is not configured")
    if not provider_healthy:
        warnings.append("Provider health check failed or degraded")

    if intent.mode in ("image_to_video", "i2v") and not intent.hasSourceImage:
        errors.append("Image-to-video requires a source image")

    max_refs = ((pack or {}).get("parameters") or {}).get("maxReferenceImages")
    if max_refs is not None and intent.referenceCount > int(max_refs):
        errors.append(f"Too many references ({intent.referenceCount} > {max_refs})")

    if paid_path and not duplicate_guard_ok:
        errors.append("Duplicate paid submission prevented")

    # Bible conflicts → approval required rather than silent proceed
    bible_conflicts = list((bible_package or {}).get("conflicts") or [])
    status = PreflightStatus.READY
    if errors:
        status = PreflightStatus.BLOCKED
    elif bible_conflicts or rec.requiresApproval:
        status = PreflightStatus.APPROVAL_REQUIRED
        warnings.extend([f"Bible conflict: {c}" for c in bible_conflicts])
    elif warnings:
        status = PreflightStatus.READY_WITH_WARNINGS

    cost = None
    if paid_path and binding and binding.providerId == "fal.api":
        cost = "estimate_unavailable; respect ~$15 milestone budget and single-submit guards"

    return PreflightResult(
        status=status,
        modelId=compile_result.modelId,
        engineId=compile_result.engineId,
        errors=errors,
        warnings=warnings,
        costEstimate=cost,
        compile=compile_result,
        recommendation=rec,
    )
