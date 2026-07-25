"""Co-Director M2.4 storyboard generation proposal handler."""

from __future__ import annotations

from typing import Any

from ...bible.context_retrieval import ContextRetrievalService
from ...errors import TOOL_ARGUMENTS_INVALID, CoDirectorError
from ..definitions import ToolContext, ToolPreview


def preview_propose_storyboard_generation(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id = args.get("sceneId") or ctx.scene_id
    if not scene_id:
        raise CoDirectorError(
            TOOL_ARGUMENTS_INVALID,
            "sceneId is required to propose storyboard generation.",
            recoverable=True,
        )
    shot_purpose = str(args.get("shotPurpose") or "Next consistent storyboard shot")[:200]
    lines = [
        f"Scene: {scene_id}",
        f"Purpose: {shot_purpose}",
        "Creates a generation package proposal for storyboard image workflow.",
        "Visual validation will be marked pending for M2.5 review.",
    ]
    if args.get("prompt"):
        lines.append(f"Prompt excerpt: {str(args['prompt'])[:120]}")
    return ToolPreview(
        summary="Propose storyboard image generation (approval required).",
        lines=lines,
        resourceKind="scene",
        resourceId=str(scene_id),
        warnings=[] if args.get("referencesReady", True) else ["Primary references may be incomplete."],
    )


def apply_propose_storyboard_generation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(args.get("sceneId") or ctx.scene_id or "")
    if not scene_id:
        raise CoDirectorError(
            TOOL_ARGUMENTS_INVALID,
            "sceneId is required to prepare storyboard generation.",
            recoverable=True,
        )
    package = ContextRetrievalService.generation_package(ctx.db, ctx.project_id, scene_id=scene_id)
    return {
        "sceneId": scene_id,
        "generationPackage": package,
        "visualValidationPending": True,
        "workflow": args.get("workflow") or "configured_storyboard_image_workflow",
        "status": "proposal_prepared",
        "message": "Storyboard generation package prepared. Awaiting render execution after approval pipeline.",
    }
