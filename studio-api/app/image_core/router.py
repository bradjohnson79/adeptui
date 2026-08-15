"""Thin Image Core discovery — recommend and preflight. No enqueue."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .preflight import preflight
from .recommend import recommend
from .request import ImageCoreRequest

router = APIRouter(prefix="/image-core", tags=["image-core"])


@router.get("/recommend")
def api_recommend(operation: str = "", family: str = "") -> dict[str, Any]:
    return recommend(operation, family)


@router.post("/preflight")
def api_preflight(body: dict[str, Any]) -> dict[str, Any]:
    request = ImageCoreRequest(
        project_id=str(body.get("projectId") or body.get("project_id") or ""),
        purpose=str(body.get("purpose") or ""),
        operation=str(body.get("operation") or ""),
        model_id=str(body.get("modelId") or body.get("model_id") or body.get("family") or ""),
        source_asset_id=str(body.get("sourceAssetId") or body.get("source_asset_id") or ""),
        mask_asset_id=str(body.get("maskAssetId") or body.get("mask_asset_id") or ""),
        edit_operation=str(body.get("editOperation") or body.get("edit_operation") or ""),
        expand=str(body.get("expand") or ""),
        feather=str(body.get("feather") or ""),
        provider=str(body.get("provider") or "local"),
        hosted_model_id=str(body.get("hostedModelId") or body.get("hosted_model_id") or ""),
    )
    decision = preflight(request)
    return {
        "ok": decision.ok,
        "code": decision.code,
        "message": decision.message,
        "family": decision.family,
        "workflowKey": decision.workflow_key,
        "operation": decision.runtime_operation,
        "width": decision.width,
        "height": decision.height,
        "recommendedFamily": decision.recommended_family,
        "supported": decision.supported,
        "details": decision.details,
    }
