"""Co-Director curated tool: deposit completed Omni video onto Timeline Visual.

Wave 4 — thin wrapper around Wave 2B `export_completed_video_to_timeline`.
No regeneration. Video-only.
"""

from __future__ import annotations

from typing import Any

from ..definitions import ToolContext, ToolPreview
from ...capabilities.handlers import timeline_deposit_video as deposit


def _project_id(ctx: ToolContext) -> str:
    return str(getattr(ctx, "project_id", "") or "")


def _text(args: dict[str, Any], key: str) -> str:
    return str(args.get(key) or "").strip()


def preview_deposit_video_to_timeline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    asset = _text(args, "assetId")
    scene = _text(args, "sceneId")
    surface = _text(args, "sourceSurface") or "codirector"
    return ToolPreview(
        summary="Deposit a completed Library VIDEO onto Timeline Visual (Wave 2B contract).",
        lines=[
            f"Asset: {asset or '(resolve from attachments / latest Omni video)'}",
            f"Scene: {scene or '(active Timeline scene)'}",
            f"Source surface: {surface}",
            "mediaType=video → video_clips / media_mode=video",
            "No regenerate",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_deposit_video_to_timeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    attachments = args.get("attachmentAssetIds") or args.get("attachment_asset_ids") or []
    if isinstance(attachments, str):
        attachments = [attachments]
    result = deposit.handle(
        ctx.db,
        _project_id(ctx),
        execution_id=f"tool-deposit-{_text(args, 'assetId') or 'auto'}",
        prompt=_text(args, "prompt") or "deposit completed video to timeline visual",
        attachment_asset_ids=[str(x) for x in attachments if str(x or "").strip()],
        reference_asset_id=_text(args, "assetId"),
        scene_id=_text(args, "sceneId"),
        label=_text(args, "label"),
        source_surface=_text(args, "sourceSurface"),
    )
    ok = result.get("status") == "completed" and not result.get("error")
    return {
        "ok": bool(ok),
        **result,
        "_evidence": {
            "source": "director_timeline_w46.generation.omni_visual_export.export_completed_video_to_timeline",
            "wave": "wave4_cd_deposit",
        },
    }
