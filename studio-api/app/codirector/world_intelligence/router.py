"""World Intelligence API routes for Co-Director."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from .contracts import CoDirectorWorldIntelligencePolicy
from .health import world_intelligence_status
from .worker_client import schedule_cuda_probe
from .service import (
    evaluate_project_assets,
    get_policy,
    get_supported_advisories,
    latest_advisory,
    mark_intentional_change,
    set_policy,
    world_consistency_text,
)

router = APIRouter(prefix="/world-intelligence", tags=["codirector-world-intelligence"])


class EvaluateBody(BaseModel):
    projectId: str
    assetId: str
    referenceAssetIds: list[str] = Field(default_factory=list)
    sceneId: str = ""
    intentional: bool = False


class PolicyBody(BaseModel):
    projectId: str
    enabled: Optional[bool] = None
    policy: Optional[str] = None
    showDiagnostics: Optional[bool] = None


class IntentionalBody(BaseModel):
    projectId: str
    fromAssetId: str
    toAssetId: str
    sceneId: str = ""
    label: str = ""
    creatorNote: str = ""


@router.get("/status")
def api_status() -> dict[str, Any]:
    """Creator/status reads never block the API on a torch import."""
    schedule_cuda_probe()
    status = world_intelligence_status(probe=False)
    return {
        "ok": bool(status.get("available")),
        "available": bool(status.get("available")),
        "installed": bool(status.get("installed")),
        "status": status,
        "advisoryOnly": True,
    }


@router.get("/policy")
def api_get_policy(projectId: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    policy = get_policy(projectId, db)
    return policy.model_dump()


@router.post("/policy")
def api_set_policy(body: PolicyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    policy = get_policy(body.projectId, db)
    if body.enabled is not None:
        policy.enabled = body.enabled
    if body.policy is not None:
        policy.policy = body.policy  # type: ignore[assignment]
    if body.showDiagnostics is not None:
        policy.showDiagnostics = body.showDiagnostics
    set_policy(body.projectId, policy, db)
    return {"ok": True, "policy": policy.model_dump()}


@router.post("/mark-intentional")
def api_mark_intentional(body: IntentionalBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    mark_intentional_change(
        from_asset_id=body.fromAssetId,
        to_asset_id=body.toAssetId,
        project_id=body.projectId,
        scene_id=body.sceneId,
        label=body.label or f"Transition: {body.fromAssetId} → {body.toAssetId}",
        creator_note=body.creatorNote,
        db=db,
    )
    return {"ok": True}


@router.get("/advisories")
def api_advisories() -> list[dict]:
    return get_supported_advisories()


@router.get("/advisory")
def api_advisory(
    projectId: str,
    sceneId: str = "",
    assetId: str = "",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return latest_advisory(db, projectId, scene_id=sceneId, asset_id=assetId)


@router.post("/evaluate")
def api_evaluate(body: EvaluateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Evaluate a generated asset against approved world references in the same project."""
    if not body.assetId:
        raise HTTPException(
            status_code=400,
            detail={"code": "ASSET_REQUIRED", "message": "A generated image is required."},
        )
    packet = evaluate_project_assets(
        db,
        project_id=body.projectId,
        asset_id=body.assetId,
        reference_asset_ids=body.referenceAssetIds,
        scene_id=body.sceneId,
        intentional_change=body.intentional,
    )
    from .persist import save_advisory

    text = world_consistency_text(packet)
    save_advisory(
        db,
        body.projectId,
        packet,
        text,
        scene_id=body.sceneId,
        asset_id=body.assetId,
    )
    return {
        "packet": packet.model_dump(mode="json"),
        "advisoryText": text,
    }
