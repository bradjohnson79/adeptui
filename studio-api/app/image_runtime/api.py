"""HTTP surfaces for M42 Image Runtime (Wave 2)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .certified_registry import get_workflow, list_workflows, production_ready_keys
from .contract import resolve_image_workflow
from .identities import identity_registry_snapshot
from .production_gate import evaluate_image_gate, evaluate_image_wave2_gate, evaluate_modern_model_foundation
from .reference_assets import REFERENCE_TYPES

router = APIRouter(prefix="/image-runtime", tags=["image-runtime"])


@router.get("/registry")
def image_registry(
    category: Optional[str] = Query(None),
    modelFamily: Optional[str] = Query(None),
) -> dict[str, Any]:
    return {
        "phase": "M42-W2",
        "entries": [w.to_dict() for w in list_workflows(category=category, model_family=modelFamily)],
        "productionReadyKeys": production_ready_keys(),
        "note": "Certified only with live dual-stage evidence. Modern families may be Draft/Deferred/Blocked.",
    }


@router.get("/registry/{workflow_key}")
def image_workflow(workflow_key: str) -> dict[str, Any]:
    wf = get_workflow(workflow_key)
    if not wf:
        raise HTTPException(404, f"Unknown image workflow: {workflow_key}")
    return wf.to_dict()


@router.get("/gate")
def image_gate() -> dict[str, Any]:
    return evaluate_image_gate()


@router.get("/gate/wave2")
def image_gate_wave2() -> dict[str, Any]:
    return evaluate_image_wave2_gate()


@router.get("/foundation")
def modern_foundation() -> dict[str, Any]:
    return evaluate_modern_model_foundation()


@router.get("/readiness")
def image_readiness() -> dict[str, Any]:
    from .readiness import generate_readiness_report

    return generate_readiness_report()


@router.get("/capabilities")
def image_capabilities() -> dict[str, Any]:
    from pathlib import Path
    import json

    w2 = Path(__file__).resolve().parents[3] / "artifacts" / "m42" / "w2" / "runtime_capabilities.json"
    if w2.is_file():
        return json.loads(w2.read_text(encoding="utf-8"))
    from .capability_probe import probe_runtime_capabilities

    return probe_runtime_capabilities()


@router.get("/providers")
def image_providers() -> dict[str, Any]:
    from .provider_registry import provider_inventory

    return provider_inventory()


@router.get("/reference-types")
def reference_types() -> dict[str, Any]:
    return {"phase": "M42-W2", "types": list(REFERENCE_TYPES)}


@router.get("/identities")
def identities() -> dict[str, Any]:
    return identity_registry_snapshot()


class ResolveBody(BaseModel):
    intent: str
    engine: str = "zimage"
    modelFamily: str | None = None
    presentInputs: dict[str, Any] = Field(default_factory=dict)
    forceWorkflowKey: str | None = None
    providerPreference: str | None = None
    allowDraft: bool = False  # Wave 2 production default


@router.post("/resolve")
def resolve(body: ResolveBody) -> dict[str, Any]:
    try:
        contract = resolve_image_workflow(
            body.intent,
            engine=body.engine,
            model_family=body.modelFamily,
            present_inputs=body.presentInputs,
            force_workflow_key=body.forceWorkflowKey,
            allow_draft=body.allowDraft,
            provider_preference=body.providerPreference,
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return contract.to_dict()
