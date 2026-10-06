"""Co-Director Movement Segment + Mini take tools.

Operate on the same Spatial Map document JSON. Planning does not mutate.
"""

from __future__ import annotations

from typing import Any

from ....spatial_map import service as spatial_service
from ....spatial_map.movement import compact_index, compact_segment_json, compute_transition, previous_segment
from ....spatial_map.schemas import MovementCreateBody, MovementDialogue, MovementUpdateBody
from ....spatial_map.scene_creator_mini import MiniTakeCreateBody, create_mini_take
from ..definitions import ToolContext, ToolPreview


def _string(args: dict[str, Any], key: str) -> str:
    return str(args.get(key) or "").strip()


def _required(args: dict[str, Any], key: str) -> str:
    value = _string(args, key)
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _document_id(ctx: ToolContext, args: dict[str, Any]) -> str:
    wanted = _string(args, "documentId")
    if wanted:
        return wanted
    docs = spatial_service.list_documents(ctx.db, ctx.project_id)
    if not docs:
        raise ValueError("This project does not have a Spatial Map yet.")
    return docs[0].id


def preview_save(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Save the Spatial Map.",
        lines=["Keeps the current movements and placements. Mini Takes stay blocked until this save is approved."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_save(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.commit_document(ctx.db, ctx.project_id, _document_id(ctx, args))
    return {
        "ok": True,
        "documentId": document.id,
        "savedVersion": document.savedVersion,
        "version": document.version,
        "movements": compact_index(document),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.commit_document"},
    }


def preview_create_movement(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Create the next movement from the current blocking.",
        lines=[
            "Copies placements, props, and attachments.",
            "Direction and dialogue stay blank unless you provided them.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_movement(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    body = MovementCreateBody(
        beatName=_string(args, "beatName"),
        userDirection=_string(args, "userDirection"),
        productionPrompt=_string(args, "productionPrompt"),
        inheritFromId=_string(args, "inheritFromId") or None,
    )
    if _string(args, "dialogue"):
        body.dialogue = [MovementDialogue(speaker=_string(args, "speaker") or "", text=_string(args, "dialogue"))]
    document = spatial_service.create_movement(ctx.db, ctx.project_id, _document_id(ctx, args), body)
    return {
        "ok": True,
        "document": document.model_dump(),
        "movements": compact_index(document),
        "persisted": True,
        "dirty": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.create_movement"},
    }


def preview_update_movement(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Update movement beat, direction, or dialogue.",
        lines=["Does not rewrite inherited placements unless you move them on the map."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_update_movement(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    body = MovementUpdateBody(
        beatName=_string(args, "beatName") or None,
        userDirection=args.get("userDirection"),
        productionPrompt=args.get("productionPrompt"),
    )
    if args.get("dialogue") is not None:
        body.dialogue = [MovementDialogue(speaker=_string(args, "speaker") or "", text=str(args.get("dialogue") or ""))]
    document = spatial_service.update_movement(
        ctx.db, ctx.project_id, _document_id(ctx, args), _required(args, "movementId"), body
    )
    return {
        "ok": True,
        "documentId": document.id,
        "movements": compact_index(document),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.update_movement"},
    }


def preview_activate_movement(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Switch the active movement on the Spatial Map.",
        lines=["Saves the current placements into the previous movement first."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_activate_movement(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.activate_movement(
        ctx.db, ctx.project_id, _document_id(ctx, args), _required(args, "movementId")
    )
    return {
        "ok": True,
        "documentId": document.id,
        "movements": compact_index(document),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.activate_movement"},
    }


def preview_delete_movement(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Remove a later movement.",
        lines=["Movement 1 cannot be removed. Timeline or Mini references will block delete."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_delete_movement(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.remove_movement(
        ctx.db, ctx.project_id, _document_id(ctx, args), _required(args, "movementId")
    )
    return {
        "ok": True,
        "documentId": document.id,
        "movements": compact_index(document),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "spatial_map.service.remove_movement"},
    }


async def plan_movements(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    document = spatial_service.get_document(ctx.db, ctx.project_id, _document_id(ctx, args))
    index = compact_index(document)
    suggestions = []
    count = int(index.get("movementCount") or 0)
    if count < 5:
        suggestions.append(
            {
                "action": "create",
                "beatName": _string(args, "beatName") or f"Movement {count + 1}",
                "userDirection": _string(args, "userDirection"),
                "note": "Recommendation only. Approve Build them to create it.",
            }
        )
    return {
        "ok": True,
        "recommendOnly": True,
        "movements": index,
        "suggestions": suggestions,
        "mock": False,
        "_evidence": {"source": "spatial.plan_movements"},
    }


def preview_create_mini_take(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Generate a Scene Creator Mini take for one movement.",
        lines=["Uses the selected movement and saved cameras. Does not auto-approve."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_mini_take(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    mid = _string(args, "movementSegmentId")
    if not mid:
        raise ValueError("Choose a movement. The system will not substitute Movement 1.")
    take = create_mini_take(
        ctx.db,
        ctx.project_id,
        _document_id(ctx, args),
        MiniTakeCreateBody(
            generator=_string(args, "generator") or "qwen2512",  # type: ignore[arg-type]
            aspectRatio=_string(args, "aspectRatio") or "16:9",
            movementSegmentId=mid,
        ),
    )
    return {
        "ok": True,
        "take": take,
        "mock": False,
        "_evidence": {"source": "spatial_map.scene_creator_mini.create_mini_take"},
    }


async def open_scene_creator(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Open Environment Creator Express (contentTab scene_creator). Not Spatial Map. Not Standard."""
    mode = _string(args, "mode") or "express"
    return {
        "ok": True,
        "uiAction": "open_environment_creator",
        "contentTab": "scene_creator",
        "mode": mode,
        "projectId": ctx.project_id,
        "movementSegmentId": _string(args, "movementSegmentId") or None,
        "workspaceUrl": f"/co-director?projectId={ctx.project_id}&contentTab=scene_creator",
        "_summary": "Opening Environment Creator Express for environment / ERS work.",
        "_evidence": {"source": "workspace.open_scene_creator"},
    }


async def open_image_generator(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Open Cinematic Image Generator for production stills.

    FE id: workspaces.imagegen (ProjectEditor tab imagegen), not a Co-Director
    contentTab. Env Creator uses contentTab scene_creator inside Co-Director;
    IG is a top-level workspace. Emit both workspace and contentTab as imagegen
    so WAVE 2 can consume either key the same way Env Creator consumes
    contentTab. Do not edit FE here.
    """
    # FE workspaces.imagegen -- ProjectEditor tab id (studio-web/src/core/workspaces.ts).
    imagegen_tab = "imagegen"
    return {
        "ok": True,
        "uiAction": "open_image_generator",
        "workspace": imagegen_tab,
        "contentTab": imagegen_tab,
        "projectId": ctx.project_id,
        "workspaceUrl": f"/project/{ctx.project_id}?workspace={imagegen_tab}",
        "_summary": "Opening Image Generator for production stills.",
        "_evidence": {"source": "workspace.open_image_generator"},
    }


def compact_movement_snapshot(document: Any) -> dict[str, Any]:
    hydrate = compact_index(document)
    active = next((row for row in hydrate.get("movements") or [] if row.get("active")), None)
    transitions = []
    segs = list(getattr(document, "movementSegments", None) or [])
    for segment in segs:
        prior = previous_segment(document, segment)
        if prior is not None:
            packed = compute_transition(prior, segment)
            transitions.append(
                {
                    "from": packed.get("fromAlias"),
                    "to": packed.get("toAlias"),
                    "changed": packed.get("changed"),
                }
            )
    return {
        "activeMovementId": hydrate.get("activeMovementId"),
        "movementCount": hydrate.get("movementCount"),
        "movements": hydrate.get("movements"),
        "movementTransitions": transitions[:4],
        "active": compact_segment_json(next((s for s in segs if active and s.id == active.get("id")), segs[0])) if segs else None,
    }
