"""HTTP API for M3.2a Generation Tools."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from .catalog import TOOL_CATALOG, get_tool, tools_by_category
from . import ops

router = APIRouter(tags=["generation-tools"])


class RunBody(BaseModel):
    toolId: str
    sourceAssetId: Optional[str] = None
    prompt: str = ""
    durationSec: float = 4.0
    documentType: str = "treatment"
    title: Optional[str] = None
    keyColor: str = "green"
    tolerance: float = 0.28
    spill: float = 0.65
    edgeFeather: float = 1.5
    fidelity: float = 0.8
    allowIdentityChange: bool = False
    logoAssetIds: list[str] = Field(default_factory=list)
    productAssetIds: list[str] = Field(default_factory=list)
    brandColors: list[str] = Field(default_factory=list)
    requiredWording: str = ""
    campaignName: str = ""
    campaignType: str = ""
    visualDirection: str = ""
    composition: str = ""
    background: str = ""
    format: str = ""
    campaignFormats: list[str] = Field(default_factory=list)
    typographyTemplate: str = ""
    productName: str = ""
    styleNotes: str = ""
    bibleSummary: str = ""
    resultLane: str = "concepts"
    confirmPaidCloud: bool = False


@router.get("/generation-tools/catalog")
def catalog() -> dict[str, Any]:
    return {
        "categories": tools_by_category(),
        "tools": TOOL_CATALOG,
        "disclosure": "All tools default to local providers. Paid cloud requires explicit confirmation and is blocked when unset.",
    }


@router.get("/generation-tools/{tool_id}/status")
def tool_status(tool_id: str) -> dict[str, Any]:
    return ops.probe_tool(tool_id)


@router.get("/projects/{project_id}/generation-tools/status")
def project_tool_status(project_id: str) -> dict[str, Any]:
    statuses = [ops.probe_tool(t["id"]) for t in TOOL_CATALOG]
    return {"projectId": project_id, "tools": statuses}


@router.post("/projects/{project_id}/generation-tools/run")
def run_tool(project_id: str, body: RunBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    tool = get_tool(body.toolId)
    if not tool:
        raise HTTPException(404, f"Unknown tool {body.toolId}")
    if tool.get("cloudPaid") and not body.confirmPaidCloud:
        raise HTTPException(400, "Paid cloud tools require explicit confirmPaidCloud=true")
    if body.confirmPaidCloud and tool.get("cloudPaid"):
        # Still block silent paid — none of our catalog is paid; keep gate for future.
        pass
    if tool.get("blocked"):
        raise HTTPException(
            503,
            detail={
                "status": "BLOCKED",
                "toolId": body.toolId,
                "remediation": tool.get("blockedReason"),
                "honesty": "Do not use color correction as a substitute for de-lighting.",
            },
        )

    try:
        if body.toolId == "image.chroma_key":
            if not body.sourceAssetId:
                raise HTTPException(400, "sourceAssetId required")
            return ops.run_chroma_key(
                db,
                project_id=project_id,
                source_asset_id=body.sourceAssetId,
                key_color=body.keyColor,
                tolerance=body.tolerance,
                spill=body.spill,
                edge_feather=body.edgeFeather,
            )
        if body.toolId == "image.upscale":
            if not body.sourceAssetId:
                raise HTTPException(400, "sourceAssetId required")
            try:
                return ops.enqueue_imagegen_specialized(
                    db,
                    project_id=project_id,
                    source_asset_id=body.sourceAssetId,
                    edit_op="upscale",
                    prompt=body.prompt or "Specialized image upscale",
                    extra={"m32aUpscale": True, "modelFamily": "RealESRGAN"},
                )
            except Exception as exc:
                # W6P: fail closed — no stub-copy production success
                raise HTTPException(503, f"image.upscale unavailable: {exc}") from exc
        if body.toolId == "image.background_remove":
            if not body.sourceAssetId:
                raise HTTPException(400, "sourceAssetId required")
            try:
                return ops.enqueue_imagegen_specialized(
                    db,
                    project_id=project_id,
                    source_asset_id=body.sourceAssetId,
                    edit_op="bg_remove",
                    prompt="Specialized background remove / matte",
                    extra={"m32aBgRemove": True, "modelFamily": "BiRefNet"},
                )
            except Exception as exc:
                raise HTTPException(503, f"image.background_remove unavailable: {exc}") from exc
        if body.toolId == "image.portrait_skin":
            if not body.sourceAssetId:
                raise HTTPException(400, "sourceAssetId required")
            meta = {
                "fidelity": body.fidelity,
                "allowIdentityChange": body.allowIdentityChange,
                "identityPreservation": not body.allowIdentityChange,
            }
            try:
                return ops.enqueue_imagegen_specialized(
                    db,
                    project_id=project_id,
                    source_asset_id=body.sourceAssetId,
                    edit_op="face_refine",
                    prompt="Portrait skin enhance; preserve identity"
                    if not body.allowIdentityChange
                    else "Portrait skin enhance; intentional change allowed",
                    extra={"m32aSkin": True, "modelFamily": "CodeFormer", **meta},
                )
            except Exception as exc:
                raise HTTPException(503, f"image.portrait_skin unavailable: {exc}") from exc
        if body.toolId == "audio.music.generate":
            return ops.run_audio_generate(
                db, project_id=project_id, kind="music", prompt=body.prompt or "cinematic underscore", duration_sec=body.durationSec
            )
        if body.toolId == "audio.sfx.generate":
            return ops.run_audio_generate(
                db, project_id=project_id, kind="sfx", prompt=body.prompt or "foley hit", duration_sec=body.durationSec
            )
        if body.toolId == "scriptwriter":
            return ops.run_script_document(
                db,
                project_id=project_id,
                document_type=body.documentType,
                brief=body.prompt or body.title or "story brief",
                title=body.title,
            )
        if body.toolId == "brand.studio":
            return ops.run_brand_generate(
                db,
                project_id=project_id,
                prompt=body.prompt or "promotional hero",
                logo_asset_ids=body.logoAssetIds,
                product_asset_ids=body.productAssetIds,
                brand_colors=body.brandColors,
                required_wording=body.requiredWording,
                campaign_name=body.campaignName,
                campaign_type=body.campaignType,
                visual_direction=body.visualDirection,
                composition=body.composition,
                background=body.background,
                format_name=body.format,
                campaign_formats=body.campaignFormats,
                typography_template=body.typographyTemplate,
                product_name=body.productName,
                style_notes=body.styleNotes,
                bible_summary=body.bibleSummary,
                result_lane=body.resultLane,
            )
        if body.toolId == "video.extend":
            if not body.sourceAssetId:
                raise HTTPException(400, "sourceAssetId required")
            return ops.run_video_extend(
                db,
                project_id=project_id,
                source_asset_id=body.sourceAssetId,
                prompt=body.prompt,
                duration_sec=body.durationSec,
            )
        if body.toolId == "video.upscale":
            if not body.sourceAssetId:
                raise HTTPException(400, "sourceAssetId required")
            return ops.run_video_upscale(db, project_id=project_id, source_asset_id=body.sourceAssetId)
        if body.toolId == "image.delighting":
            raise HTTPException(
                503,
                detail={
                    "status": "BLOCKED",
                    "toolId": body.toolId,
                    "remediation": get_tool(body.toolId).get("blockedReason"),
                },
            )
        raise HTTPException(400, f"Tool {body.toolId} has no runner")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Generation tool failed: {e}") from e
