"""HTTP surfaces for M41 4.1A/4.1B Video Runtime + Certified Workflow Library."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from .compatibility_registry import catalog_as_dict, get_entry
from .certified_registry import (
    get_by_id,
    get_workflow,
    list_workflows,
    production_ready_keys,
    registry_as_dict,
)
from .diagnostics import build_diagnostics, engine_to_workflow_key
from .graph_validation import validate_comfy_graph
from .preflight import run_preflight
from .vram_safety import estimate_vram
from .workflow_resolver import resolve_workflow

router = APIRouter(prefix="/video-runtime", tags=["video-runtime"])


class PreflightBody(BaseModel):
    workflowKey: str
    width: int | None = None
    height: int | None = None
    frames: int | None = None
    presentInputs: list[str] = Field(default_factory=list)
    applySafeConfig: bool = False
    engine: str | None = None


@router.get("/compatibility")
def list_compatibility() -> dict[str, Any]:
    return {"entries": catalog_as_dict()}


@router.get("/compatibility/{workflow_key}")
def get_compatibility(workflow_key: str) -> dict[str, Any]:
    entry = get_entry(workflow_key)
    if not entry:
        raise HTTPException(404, f"Unknown workflowKey: {workflow_key}")
    return entry.to_dict()


@router.post("/preflight")
async def preflight(body: PreflightBody) -> dict[str, Any]:
    key = body.workflowKey
    if not key and body.engine:
        key = engine_to_workflow_key(body.engine) or ""
    if not key:
        raise HTTPException(400, "workflowKey or engine is required")
    return await run_preflight(
        key,
        width=body.width,
        height=body.height,
        frames=body.frames,
        present_inputs=body.presentInputs,
        apply_safe_config=body.applySafeConfig,
    )


@router.get("/vram-estimate")
def vram_estimate(
    workflowKey: str = Query(...),
    width: int | None = None,
    height: int | None = None,
    frames: int | None = None,
) -> dict[str, Any]:
    return estimate_vram(workflowKey, width=width, height=height, frames=frames).to_dict()


@router.get("/diagnostics")
async def diagnostics(db: Session = Depends(get_db)) -> dict[str, Any]:
    return await build_diagnostics(db)


@router.get("/certified-registry")
def certified_registry(
    modality: str | None = Query("video"),
) -> dict[str, Any]:
    """Single authoritative Certified Workflow Library."""
    return {
        "phase": "M41-4.1B-L",
        "entries": [w.to_dict() for w in list_workflows(modality=modality)],
        "productionReadyKeys": production_ready_keys(),
    }


@router.get("/certified-registry/{workflow_key}")
def certified_workflow(workflow_key: str) -> dict[str, Any]:
    wf = get_workflow(workflow_key) or get_by_id(workflow_key)
    if not wf:
        raise HTTPException(404, f"Unknown workflow: {workflow_key}")
    return wf.to_dict()


class ResolveBody(BaseModel):
    intent: str
    engine: str = "ltx"
    modality: str = "video"  # M42: "video" | "image" — unified resolver domains
    presentInputs: dict[str, Any] = Field(default_factory=dict)
    paidFalApproved: bool = False
    falEngine: str | None = None
    wantsIngredients: bool = False
    forceWorkflowKey: str | None = None
    allowDraft: bool = True


@router.post("/resolve")
def resolve(body: ResolveBody) -> dict[str, Any]:
    try:
        if (body.modality or "video").lower() == "image":
            from ..workflow_runtime import resolve_workflow as resolve_unified

            contract = resolve_unified(
                body.intent,
                modality="image",
                engine=body.engine,
                present_inputs=body.presentInputs,
                force_workflow_key=body.forceWorkflowKey,
                allow_draft=body.allowDraft,
            )
        else:
            contract = resolve_workflow(
                body.intent,
                engine=body.engine,
                present_inputs=body.presentInputs,
                paid_fal_approved=body.paidFalApproved,
                fal_engine=body.falEngine,
                wants_ingredients=body.wantsIngredients,
                force_workflow_key=body.forceWorkflowKey,
            )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return contract.to_dict()


class ValidateGraphBody(BaseModel):
    workflowKey: str
    graph: dict[str, Any]


@router.post("/validate-graph")
def validate_graph(body: ValidateGraphBody) -> dict[str, Any]:
    return validate_comfy_graph(body.graph, workflow_key=body.workflowKey).to_dict()


@router.get("/gate")
def wave6_gate() -> dict[str, Any]:
    """Wave 6 gate: required-set inclusion (local + enabled cloud), not mere count."""
    from .diagnostics import _wave6_wiring_unlocked
    from .production_gate import evaluate_gate
    from .wave6p_gate import evaluate_wave6p_gate

    wiring = _wave6_wiring_unlocked()
    gate = evaluate_gate()
    production = bool(gate.get("wave6ProductionActivationUnlocked"))
    w6p = evaluate_wave6p_gate()
    if production:
        message = (
            "Wave 6 production activation unlocked "
            "(requiredLocalProductionWorkflowKeys ⊆ certifiedWorkflowKeys)."
        )
    elif wiring:
        missing = gate.get("missingRequiredLocalKeys") or []
        message = (
            "Wave 6 wiring may begin; production activation blocked until local required "
            f"set is CERTIFIED (missing={missing})."
        )
    else:
        message = "Wave 6 remains hard-blocked pending runtime + certified workflow GO."
    return {
        "wave6WiringUnlocked": wiring,
        "wave6ProductionActivationUnlocked": production,
        "wave6MediaExecutionUnlocked": production,
        "certifiedWorkflowCount": len(gate.get("certifiedWorkflowKeys") or []),
        "message": message,
        "wave6p": w6p,
        **gate,
    }


@router.get("/wave6p-gate")
def wave6p_gate() -> dict[str, Any]:
    """Wave 6P product/beta gate — exact required-condition inclusion."""
    from .wave6p_gate import evaluate_wave6p_gate

    return evaluate_wave6p_gate()


@router.get("/hunyuan/library")
def hunyuan_library() -> dict[str, Any]:
    """Video Model Library matrix — LTX default, dual Hunyuan, WAN optional, MiniMax Coming Soon."""
    from .hunyuan_providers import video_library_matrix

    return video_library_matrix()


@router.get("/hunyuan/providers")
def hunyuan_providers() -> dict[str, Any]:
    from .hunyuan_providers import list_hunyuan_providers

    return {"ok": True, "providers": list_hunyuan_providers(), "mock": False}


@router.get("/hunyuan/providers/{provider_id}/preflight")
def hunyuan_preflight(provider_id: str) -> dict[str, Any]:
    from .hunyuan_install import hardware_preflight
    from .hunyuan_providers import OFFICIAL_SOURCES

    if provider_id not in OFFICIAL_SOURCES:
        raise HTTPException(404, f"Unknown Hunyuan provider {provider_id}")
    return hardware_preflight(provider_id)


@router.get("/hunyuan/providers/{provider_id}/health")
def hunyuan_health(provider_id: str) -> dict[str, Any]:
    from .hunyuan_install import health_check
    from .hunyuan_providers import OFFICIAL_SOURCES

    if provider_id not in OFFICIAL_SOURCES:
        raise HTTPException(404, f"Unknown Hunyuan provider {provider_id}")
    return health_check(provider_id)


@router.post("/hunyuan/providers/{provider_id}/install")
def hunyuan_install(provider_id: str) -> dict[str, Any]:
    """Queue one independent install job (never both models)."""
    from .hunyuan_install import enqueue_install
    from .hunyuan_providers import COMPONENT_BY_PROVIDER, OFFICIAL_SOURCES

    if provider_id not in OFFICIAL_SOURCES:
        raise HTTPException(404, f"Unknown Hunyuan provider {provider_id}")
    return enqueue_install(COMPONENT_BY_PROVIDER[provider_id])


@router.post("/hunyuan/providers/{provider_id}/remove")
def hunyuan_remove(provider_id: str) -> dict[str, Any]:
    from .hunyuan_install import remove_provider
    from .hunyuan_providers import OFFICIAL_SOURCES

    if provider_id not in OFFICIAL_SOURCES:
        raise HTTPException(404, f"Unknown Hunyuan provider {provider_id}")
    result = remove_provider(provider_id)
    return {"ok": result.ok, "message": result.message, "evidence": result.evidence}


@router.post("/hunyuan/providers/{provider_id}/repair")
def hunyuan_repair(provider_id: str) -> dict[str, Any]:
    from .hunyuan_install import repair_component
    from .hunyuan_providers import COMPONENT_BY_PROVIDER, OFFICIAL_SOURCES

    if provider_id not in OFFICIAL_SOURCES:
        raise HTTPException(404, f"Unknown Hunyuan provider {provider_id}")
    result = repair_component(COMPONENT_BY_PROVIDER[provider_id])
    return {"ok": result.ok, "message": result.message, "evidence": result.evidence}


@router.post("/hunyuan/providers/{provider_id}/benchmark")
def hunyuan_benchmark(provider_id: str) -> dict[str, Any]:
    from .hunyuan_benchmark import run_benchmark
    from .hunyuan_providers import OFFICIAL_SOURCES

    if provider_id not in OFFICIAL_SOURCES:
        raise HTTPException(404, f"Unknown Hunyuan provider {provider_id}")
    return run_benchmark(provider_id)


@router.get("/hunyuan/providers/{provider_id}/benchmark")
def hunyuan_benchmark_get(provider_id: str) -> dict[str, Any]:
    from .hunyuan_benchmark import latest_benchmark
    from .hunyuan_providers import OFFICIAL_SOURCES

    if provider_id not in OFFICIAL_SOURCES:
        raise HTTPException(404, f"Unknown Hunyuan provider {provider_id}")
    return latest_benchmark(provider_id)
