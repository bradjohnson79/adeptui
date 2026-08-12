"""Co-Director handlers for M3.2a Generation Tools."""

from __future__ import annotations

from typing import Any

from ....generation_tools.catalog import TOOL_CATALOG, tools_by_category
from ....generation_tools import ops
from ..definitions import ToolContext, ToolPreview


async def get_generation_tools_catalog(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    statuses = [ops.probe_tool(t["id"]) for t in TOOL_CATALOG]
    return {
        "categories": tools_by_category(),
        "status": statuses,
        "disclosure": "Local providers by default. Paid cloud never silent.",
        "workspace": f"/project/{ctx.project_id}?workspace=generationtools",
    }


def _preview(summary: str, *lines: str) -> ToolPreview:
    return ToolPreview(
        summary=summary,
        lines=list(lines) + ["Non-destructive. Local provider. Approval required."],
        warnings=["Original assets are preserved."],
    )


def preview_propose_script_document(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview(f"Create {args.get('documentType')} via Scriptwriter", str(args.get("brief") or "")[:200])


def apply_propose_script_document(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ops.run_script_document(
        ctx.db,
        project_id=ctx.project_id,
        document_type=str(args.get("documentType") or "treatment"),
        brief=str(args.get("brief") or ""),
        title=args.get("title"),
    )


def preview_propose_music_generate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview("Generate local music bed", str(args.get("prompt") or ""))


def apply_propose_music_generate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ops.run_audio_generate(
        ctx.db,
        project_id=ctx.project_id,
        kind="music",
        prompt=str(args.get("prompt") or "music"),
        duration_sec=float(args.get("durationSec") or 4),
    )


def preview_propose_sfx_generate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview("Generate local SFX", str(args.get("prompt") or ""))


def apply_propose_sfx_generate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ops.run_audio_generate(
        ctx.db,
        project_id=ctx.project_id,
        kind="sfx",
        prompt=str(args.get("prompt") or "sfx"),
        duration_sec=float(args.get("durationSec") or 2),
    )


def preview_propose_image_upscale(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview("Upscale image (non-destructive)", f"source={args.get('sourceAssetId')}")


def apply_propose_image_upscale(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # W6P: fail closed — never stub-copy as production success.
    return ops.enqueue_imagegen_specialized(
        ctx.db,
        project_id=ctx.project_id,
        source_asset_id=str(args["sourceAssetId"]),
        edit_op="upscale",
        prompt="Specialized image upscale",
        extra={"m32aUpscale": True},
    )


def preview_propose_background_remove(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview("Remove background / matte", f"source={args.get('sourceAssetId')}")


def apply_propose_background_remove(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ops.enqueue_imagegen_specialized(
        ctx.db,
        project_id=ctx.project_id,
        source_asset_id=str(args["sourceAssetId"]),
        edit_op="bg_remove",
        prompt="Background remove",
        extra={"m32aBgRemove": True},
    )


def preview_propose_chroma_key(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview("Chroma key with spill controls", f"source={args.get('sourceAssetId')}")


def apply_propose_chroma_key(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ops.run_chroma_key(
        ctx.db,
        project_id=ctx.project_id,
        source_asset_id=str(args["sourceAssetId"]),
        key_color=str(args.get("keyColor") or "green"),
    )


def preview_propose_portrait_skin(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview("Portrait skin enhance", f"source={args.get('sourceAssetId')}")


def apply_propose_portrait_skin(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    allow = bool(args.get("allowIdentityChange"))
    return ops.enqueue_imagegen_specialized(
        ctx.db,
        project_id=ctx.project_id,
        source_asset_id=str(args["sourceAssetId"]),
        edit_op="face_refine",
        prompt="Portrait skin",
        extra={"m32aSkin": True, "allowIdentityChange": allow},
    )


def preview_propose_video_upscale(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview("Temporal SeedVR2 video upscale", f"source={args.get('sourceAssetId')}")


def apply_propose_video_upscale(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ops.run_video_upscale(ctx.db, project_id=ctx.project_id, source_asset_id=str(args["sourceAssetId"]))


def preview_propose_video_extend(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview("Generative video continuation", f"source={args.get('sourceAssetId')}")


def apply_propose_video_extend(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ops.run_video_extend(
        ctx.db,
        project_id=ctx.project_id,
        source_asset_id=str(args["sourceAssetId"]),
        prompt=str(args.get("prompt") or ""),
        duration_sec=float(args.get("durationSec") or 2),
    )


def preview_propose_brand_generate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview(
        "Brand Studio locked generate",
        str(args.get("prompt") or ""),
        f"type={args.get('campaignType') or 'launch'} · format={args.get('format') or 'Square 1:1'}",
    )


def apply_propose_brand_generate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    brand_colors = [item.strip() for item in str(args.get("brandColors") or "").split(",") if item.strip()]
    return ops.run_brand_generate(
        ctx.db,
        project_id=ctx.project_id,
        prompt=str(args.get("prompt") or "promo"),
        logo_asset_ids=[str(args.get("logoAssetId"))] if args.get("logoAssetId") else [],
        product_asset_ids=[str(args.get("productAssetId"))] if args.get("productAssetId") else [],
        brand_colors=brand_colors,
        required_wording=str(args.get("requiredWording") or ""),
        campaign_name=str(args.get("campaignName") or ""),
        campaign_type=str(args.get("campaignType") or ""),
        visual_direction=str(args.get("visualDirection") or ""),
        composition=str(args.get("composition") or ""),
        background=str(args.get("background") or ""),
        format_name=str(args.get("format") or ""),
        typography_template=str(args.get("typographyTemplate") or ""),
        product_name=str(args.get("productName") or ""),
        style_notes=str(args.get("styleNotes") or ""),
        bible_summary=str(args.get("bibleSummary") or ""),
        result_lane=str(args.get("resultLane") or "concepts"),
    )
