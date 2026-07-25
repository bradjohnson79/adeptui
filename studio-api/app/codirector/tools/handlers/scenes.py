"""Scene read handlers plus the preview/apply pairs for scene mutations.

`apply_*` functions are the only place in the tool registry that writes to `scenes`, and they
are called exclusively by `ToolExecutionService.execute_approved_proposal` after a human has
approved the recorded arguments. Nothing in a chat turn can reach them.

CRUD goes through PSR `SceneService` (patch-only-present-fields). Compact tool-facing summaries
and proposal fingerprints remain in `app.scene_service` helpers.
"""

from __future__ import annotations

from typing import Any

from .... import scene_service as scene_helpers
from ....capabilities.errors import CapabilityError
from ....db import Project, Scene
from ....services.scene_service import SceneService
from ...errors import TOOL_TARGET_NOT_FOUND, CoDirectorError
from ..definitions import ToolContext, ToolPreview

DEFAULT_SCENE_LIMIT = 40


def _require_project(ctx: ToolContext) -> Project:
    try:
        return SceneService.require_project(ctx.db, ctx.project_id)
    except CapabilityError as exc:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Project not found.",
            details={"projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        ) from exc


def _require_scene(ctx: ToolContext, scene_id: str) -> Scene:
    try:
        return SceneService.get(ctx.db, ctx.project_id, scene_id)
    except CapabilityError as exc:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "That scene isn't part of this project.",
            details={"projectId": ctx.project_id, "sceneId": scene_id},
            recoverable=False,
            recommended_action="none",
        ) from exc


async def list_scenes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = int(args.get("limit") or DEFAULT_SCENE_LIMIT)
    scenes = SceneService.list_for_project(ctx.db, ctx.project_id)
    return {
        "projectId": ctx.project_id,
        "sceneCount": len(scenes),
        "returned": min(limit, len(scenes)),
        "scenes": [scene_helpers.scene_summary(s) for s in scenes[:limit]],
    }


async def get_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _require_scene(ctx, str(args["sceneId"]))
    detail = scene_helpers.scene_summary(scene)
    detail["continuityNote"] = (scene.continuity_json or "")[:1000]
    detail["summary"] = getattr(scene, "summary", "") or ""
    return detail


async def get_active_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """The selected scene is client state, so it arrives with the turn rather than from the DB."""

    if not ctx.scene_id:
        return {"projectId": ctx.project_id, "activeScene": None, "reason": "No scene is selected."}
    try:
        scene = SceneService.get(ctx.db, ctx.project_id, ctx.scene_id)
    except CapabilityError:
        return {"projectId": ctx.project_id, "activeScene": None, "reason": "The selected scene no longer exists."}
    return {"projectId": ctx.project_id, "activeScene": scene_helpers.scene_summary(scene)}


def preview_create_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _require_project(ctx)
    next_index = SceneService.count_for_project(ctx.db, ctx.project_id)
    name = str(args.get("name") or f"Scene {next_index + 1}")
    engine = str(args.get("engine") or "")
    duration = args.get("durationSec")
    prompt = str(args.get("prompt") or "")
    lines = [f"Add scene “{name}” at position {next_index + 1}"]
    if engine:
        lines.append(f"Engine: {engine}")
    if duration:
        lines.append(f"Duration: {duration}s")
    if prompt:
        lines.append(f"Prompt: {prompt[:160]}")
    return ToolPreview(
        summary=f"Create a new scene “{name}” at the end of the timeline.",
        lines=lines,
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project = _require_project(ctx)
    scene = SceneService.create(
        ctx.db,
        ctx.project_id,
        {
            "name": str(args.get("name") or ""),
            "engine": str(args.get("engine") or project.engine_default or "ltx"),
            "prompt": str(args.get("prompt") or ""),
            "duration_sec": float(args.get("durationSec") or 5.0),
        },
    )
    return {"created": "scene", "scene": scene_helpers.scene_summary(scene)}


def preview_update_scene_title(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene = _require_scene(ctx, str(args["sceneId"]))
    new_name = str(args["name"])
    return ToolPreview(
        summary=f"Rename scene {scene.index + 1} to “{new_name}”.",
        lines=[f"Current title: {scene.name}", f"New title: {new_name}"],
        resourceKind="scene",
        resourceId=scene.id,
        warnings=[] if new_name != scene.name else ["The new title is the same as the current one."],
    )


def apply_update_scene_title(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _require_scene(ctx, str(args["sceneId"]))
    previous = scene.name
    scene = SceneService.update(ctx.db, ctx.project_id, scene.id, {"name": str(args["name"])})
    return {"updated": "scene.name", "previous": previous, "scene": scene_helpers.scene_summary(scene)}


def preview_set_scene_prompt(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene = _require_scene(ctx, str(args["sceneId"]))
    new_prompt = str(args["prompt"])
    warnings = ["This replaces the scene's existing prompt."] if (scene.prompt or "").strip() else []
    return ToolPreview(
        summary=f"Set the prompt for scene {scene.index + 1} (“{scene.name}”).",
        lines=[
            f"Current prompt: {(scene.prompt or '(empty)')[:200]}",
            f"New prompt: {new_prompt[:200]}",
        ],
        resourceKind="scene",
        resourceId=scene.id,
        warnings=warnings,
    )


def apply_set_scene_prompt(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _require_scene(ctx, str(args["sceneId"]))
    previous = scene.prompt or ""
    scene = SceneService.update(ctx.db, ctx.project_id, scene.id, {"prompt": str(args["prompt"])})
    return {
        "updated": "scene.prompt",
        "previousLength": len(previous),
        "scene": scene_helpers.scene_summary(scene),
    }
