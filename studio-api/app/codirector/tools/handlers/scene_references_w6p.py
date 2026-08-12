"""Wave 6P Scene Reference Co-Director tools — grounded reads + propose→approve→execute mutations."""

from __future__ import annotations

from typing import Any

from ....scene_references import service as sr
from ...errors import CoDirectorError, TOOL_TARGET_NOT_FOUND
from ..definitions import ToolContext, ToolPreview


async def list_references(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scope_type = str(args.get("scopeType") or "scene")
    scope_id = str(args.get("scopeId") or ctx.scene_id or "")
    if not scope_id:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "scopeId required")
    items = sr.list_for_scope(
        ctx.db,
        ctx.project_id,
        scope_type,
        scope_id,
        include_inherited=bool(args.get("includeInherited", True)),
        scene_id=args.get("sceneId") or (scope_id if scope_type == "scene" else None),
    )
    return {"items": items, "count": len(items), "_evidence": {"source": "scene_references.list"}}


async def get_reference(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    binding_id = str(args.get("bindingId") or "")
    from ....scene_references import repository as repo

    row = repo.get_binding(ctx.db, ctx.project_id, binding_id)
    if not row:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "Binding not found")
    return {**repo.binding_to_dict(row), "_evidence": {"source": "scene_references.get"}}


async def get_inherited(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scope_type = str(args.get("scopeType") or "shot")
    scope_id = str(args.get("scopeId") or "")
    items = sr.list_for_scope(
        ctx.db,
        ctx.project_id,
        scope_type,
        scope_id,
        include_inherited=True,
        scene_id=args.get("sceneId"),
        sequence_id=args.get("sequenceId"),
        shot_id=args.get("shotId"),
    )
    return {"items": items, "_evidence": {"source": "scene_references.inherited"}}


async def get_readiness(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {
        **sr.readiness(
            ctx.db,
            ctx.project_id,
            str(args.get("scopeType") or "scene"),
            str(args.get("scopeId") or ctx.scene_id or ""),
            str(args.get("workflowKey") or "timeline"),
        ),
        "_evidence": {"source": "scene_references.readiness", "notContinuityScore": True},
    }


async def preview_selection(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = sr.preflight(
        ctx.db,
        ctx.project_id,
        scope_type=str(args.get("scopeType") or "scene"),
        scope_id=str(args.get("scopeId") or ctx.scene_id or ""),
        workflow_key=str(args.get("workflowKey") or "timeline"),
    )
    return {**result, "_evidence": {"source": "scene_references.preflight", "mode": "preview"}}


async def preflight(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return await preview_selection(ctx, args)


async def open_pane(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "workspace": "timeline",
        "pane": "references",
        "scopeType": args.get("scopeType") or "scene",
        "scopeId": args.get("scopeId") or ctx.scene_id,
        "_evidence": {"source": "scene_references.navigation"},
    }


def preview_attach(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Attach asset {args.get('assetId')} as {args.get('referenceType')} to {args.get('scopeType')}:{args.get('scopeId')}",
        lines=["Create SceneReferenceBinding (server-side persistence)", "Asset is not duplicated"],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_attach(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    out = sr.attach(
        ctx.db,
        ctx.project_id,
        {
            "asset_id": str(args.get("assetId") or ""),
            "scope_type": str(args.get("scopeType") or "scene"),
            "scope_id": str(args.get("scopeId") or ctx.scene_id or ""),
            "reference_type": str(args.get("referenceType") or "other"),
            "usage_modes": list(args.get("usageModes") or ["informational"]),
            "reference_roles": list(args.get("referenceRoles") or []),
            "identity_id": args.get("identityId"),
            "identity_version_id": args.get("identityVersionId"),
        },
        actor="codirector",
    )
    return {**out, "_evidence": {"source": "scene_references.attach", "persisted": True}}


def preview_update(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Update binding {args.get('bindingId')}",
        lines=["Patch SceneReferenceBinding fields"],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_update(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    patch = {}
    if "enabled" in args:
        patch["enabled"] = bool(args["enabled"])
    if args.get("referenceType"):
        patch["reference_type"] = args["referenceType"]
    if args.get("notes") is not None:
        patch["notes"] = args["notes"]
    out = sr.update(ctx.db, ctx.project_id, str(args.get("bindingId") or ""), patch, actor="codirector")
    return {**out, "_evidence": {"source": "scene_references.update", "persisted": True}}


def preview_remove(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Remove binding {args.get('bindingId')} (asset retained)",
        lines=["Soft-delete SceneReferenceBinding; asset not deleted"],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_remove(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    out = sr.remove(ctx.db, ctx.project_id, str(args.get("bindingId") or ""), actor="codirector")
    return {**out, "_evidence": {"source": "scene_references.remove", "persisted": True}}


def preview_copy(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Copy references {args.get('sourceScopeId')} → {args.get('targetScopeId')}",
        lines=["Duplicate enabled bindings onto target scope"],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_copy(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    items = sr.copy_scope(
        ctx.db,
        ctx.project_id,
        source_scope_type=str(args.get("sourceScopeType") or "scene"),
        source_scope_id=str(args.get("sourceScopeId") or ""),
        target_scope_type=str(args.get("targetScopeType") or "scene"),
        target_scope_id=str(args.get("targetScopeId") or ""),
        actor="codirector",
    )
    return {"items": items, "_evidence": {"source": "scene_references.copy", "persisted": True}}
