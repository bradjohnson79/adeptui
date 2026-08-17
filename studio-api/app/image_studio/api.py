"""HTTP surface for M4.8 cinematic image helpers + Visual Continuity Sessions."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..spatial_map.reference_bundle import summarize_reference_bundle
from ..spatial_map.service import build_reference_bundle as build_spatial_reference_bundle
from .continuity import (
    VisualContinuitySession,
    approve_image,
    create_session,
    get_session,
    inherit_from_scene,
    list_sessions,
    patch_session,
    session_to_creative_extras,
)
from .color_grades import list_color_grades
from .contracts import CinematicGenerateRequest, cinematic_to_image_product_body
from .provenance import reopen_from_asset
from .providers import family_catalog, list_image_providers, providers_for_mode

router = APIRouter(prefix="/image-studio", tags=["image-studio-m48"])


class InheritBody(BaseModel):
    sceneId: str


class ContinuityCreateBody(BaseModel):
    sceneId: Optional[str] = None
    characterIds: list[str] = Field(default_factory=list)
    locationIds: list[str] = Field(default_factory=list)
    costumeIds: list[str] = Field(default_factory=list)
    projectStyleVersion: Optional[str] = None
    referenceAssetIds: list[str] = Field(default_factory=list)


class ApproveBody(BaseModel):
    assetId: str


class CompilePreviewBody(CinematicGenerateRequest):
    pass


@router.get("/providers")
def api_list_providers(includeUnready: bool = True) -> dict[str, Any]:
    providers = list_image_providers(include_unready=includeUnready)
    return {
        "providers": [p.model_dump() for p in providers],
        "families": family_catalog(),
    }


class ModeBody(BaseModel):
    mode: str = "best_match"
    prompt: str = ""
    purpose: str = ""
    preferredFamily: Optional[str] = None


@router.post("/providers/for-mode")
def api_providers_for_mode(body: ModeBody) -> dict[str, Any]:
    mode = body.mode if body.mode in {"best_match", "choose_model", "all_models"} else "best_match"
    return providers_for_mode(
        mode,  # type: ignore[arg-type]
        prompt=body.prompt,
        purpose=body.purpose,
        preferred_family=body.preferredFamily,
    )


@router.get("/families")
def api_families() -> dict[str, Any]:
    return {"families": family_catalog()}


@router.get("/color-grades")
def api_color_grades() -> dict[str, Any]:
    return {"grades": list_color_grades(), "default": "natural"}


@router.get("/projects/{project_id}/continuity-sessions")
def api_list_sessions(project_id: str) -> dict[str, Any]:
    return {"sessions": [s.model_dump() for s in list_sessions(project_id)]}


@router.post("/projects/{project_id}/continuity-sessions")
def api_create_session(project_id: str, body: ContinuityCreateBody) -> dict[str, Any]:
    session = create_session(
        project_id,
        scene_id=body.sceneId,
        character_ids=body.characterIds,
        location_ids=body.locationIds,
        costume_ids=body.costumeIds,
        project_style_version=body.projectStyleVersion,
        reference_asset_ids=body.referenceAssetIds,
    )
    return {"session": session.model_dump()}


@router.post("/projects/{project_id}/continuity-sessions/inherit-from-scene")
def api_inherit(project_id: str, body: InheritBody) -> dict[str, Any]:
    if not body.sceneId:
        raise HTTPException(status_code=400, detail="sceneId required")
    session = inherit_from_scene(project_id, body.sceneId)
    return {"session": session.model_dump()}


@router.get("/projects/{project_id}/continuity-sessions/{session_id}")
def api_get_session(project_id: str, session_id: str) -> dict[str, Any]:
    session = get_session(project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="continuity session not found")
    return {"session": session.model_dump()}


@router.patch("/projects/{project_id}/continuity-sessions/{session_id}")
def api_patch_session(project_id: str, session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    session = patch_session(project_id, session_id, body or {})
    if not session:
        raise HTTPException(status_code=404, detail="continuity session not found")
    return {"session": session.model_dump()}


@router.post("/projects/{project_id}/continuity-sessions/{session_id}/approve-image")
def api_approve(project_id: str, session_id: str, body: ApproveBody) -> dict[str, Any]:
    session = approve_image(project_id, session_id, body.assetId)
    if not session:
        raise HTTPException(status_code=404, detail="continuity session not found")
    return {"session": session.model_dump()}


@router.get("/projects/{project_id}/assets/{asset_id}/reopen")
def api_reopen_asset(project_id: str, asset_id: str) -> dict[str, Any]:
    payload = reopen_from_asset(project_id, asset_id)
    if not payload:
        raise HTTPException(status_code=404, detail="asset provenance not found")
    return {"reopen": payload}


@router.post("/projects/{project_id}/cinematic/compile-preview")
def api_compile_preview(
    project_id: str,
    body: CompilePreviewBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Map cinematic request → image_product body (and merge continuity extras)."""
    req = body.model_copy(update={"projectId": project_id})
    if req.inheritContinuityFromScene and req.sceneId and not req.continuitySessionId:
        session = inherit_from_scene(project_id, req.sceneId)
        req.continuitySessionId = session.id
    product_body = cinematic_to_image_product_body(req)
    if req.continuitySessionId:
        session = get_session(project_id, req.continuitySessionId)
        if session:
            extras = session_to_creative_extras(session)
            creative = dict(product_body.get("creativeContext") or {})
            for k, v in extras.items():
                if k not in creative or not creative.get(k):
                    creative[k] = v
            product_body["creativeContext"] = creative
            product_body["referenceAssetIds"] = list(
                dict.fromkeys(
                    list(product_body.get("referenceAssetIds") or [])
                    + list(session.referenceAssetIds)
                    + list(session.approvedImageIds[-4:])
                )
            )
    if req.spatialMapId:
        bundle = build_spatial_reference_bundle(
            db,
            project_id,
            req.spatialMapId,
            target="image",
            camera_id=req.spatialCameraId,
        )
        spatial_summary = summarize_reference_bundle(bundle)
        creative = dict(product_body.get("creativeContext") or {})
        existing_spatial = creative.get("spatial") if isinstance(creative.get("spatial"), dict) else {}
        creative["spatial"] = {
            **existing_spatial,
            **spatial_summary,
            "cameraId": req.spatialCameraId or (bundle.primaryCamera.id if bundle.primaryCamera else None),
        }
        product_body["creativeContext"] = creative
        product_body["referenceAssetIds"] = list(
            dict.fromkeys(
                list(product_body.get("referenceAssetIds") or [])
                + list(bundle.referenceAssetIds)
            )
        )
        product_body["spatialMapId"] = req.spatialMapId
        product_body["spatialMapVersion"] = req.spatialMapVersion or bundle.documentVersion
        product_body["spatialCameraId"] = req.spatialCameraId or (
            bundle.primaryCamera.id if bundle.primaryCamera else None
        )
        product_body["spatialReferenceBundle"] = bundle.model_dump()
    from ..image_product.prompt_intel import expand_prompt

    creative = dict(product_body.get("creativeContext") or {})
    prompt_info = expand_prompt(
        str(product_body.get("prompt") or ""),
        purpose=str(product_body.get("purpose") or ""),
        cinematography=dict(creative.get("cinematography") or {}),
        lighting=dict(creative.get("lighting") or {}),
        visual_language=dict(creative.get("visualLanguage") or {}),
    )
    return {
        "imageProductBody": product_body,
        "continuitySessionId": req.continuitySessionId,
        "promptIntel": prompt_info,
    }
