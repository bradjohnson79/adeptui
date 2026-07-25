"""Co-Director M2.4 storyboard generation proposal handler."""

from __future__ import annotations

import asyncio
from typing import Any

from ....comfy_client import comfy
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
        "Does not claim a render completed — execution may be blocked when Comfy/packs are unavailable.",
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


def _comfy_reachable_sync() -> bool:
    """Best-effort sync probe for apply-time honesty. Never invents a successful render."""

    async def _probe() -> bool:
        try:
            await comfy.health()
            return True
        except Exception:  # noqa: BLE001
            return False

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return bool(asyncio.run(_probe()))
    # Nested event loop — fail closed (execution blocked) rather than claim readiness.
    return False


def apply_propose_storyboard_generation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(args.get("sceneId") or ctx.scene_id or "")
    if not scene_id:
        raise CoDirectorError(
            TOOL_ARGUMENTS_INVALID,
            "sceneId is required to prepare storyboard generation.",
            recoverable=True,
        )
    package = ContextRetrievalService.generation_package(ctx.db, ctx.project_id, scene_id=scene_id)
    comfy_ok = _comfy_reachable_sync()
    execution_blocked = not comfy_ok
    status = "execution_blocked" if execution_blocked else "proposal_prepared"
    message = (
        "Storyboard generation package prepared, but render execution is blocked "
        "(ComfyUI/packs unavailable). No asset was created. Visual validation remains pending (M2.5)."
        if execution_blocked
        else "Storyboard generation package prepared. Render not started here; visual validation remains pending (M2.5)."
    )
    return {
        "sceneId": scene_id,
        "generationPackage": package,
        "visualValidationPending": True,
        "workflow": args.get("workflow") or "configured_storyboard_image_workflow",
        "status": status,
        "executionBlocked": execution_blocked,
        "missingCapabilities": ([] if comfy_ok else ["comfyui.health", "storyboard.generate"]),
        "assetCreated": False,
        "renderCompleted": False,
        "message": message,
    }
