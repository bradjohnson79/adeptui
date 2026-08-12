"""Co-Director read/mutating handlers for Studio Project Library awareness."""

from __future__ import annotations

from typing import Any

from ....project_library.codirector import (
    get_folder_map_for_codirector,
    get_library_context,
    link_bible_entity_folder,
    resolve_library_location,
    search_library_assets,
    storage_preflight,
)
from ....project_library.service import assign_asset, enrich_library_item
from ....db import Asset
from ...errors import TOOL_TARGET_NOT_FOUND, CoDirectorError
from ..definitions import ToolContext, ToolPreview


def _require_asset(ctx: ToolContext, asset_id: str) -> Asset:
    asset = ctx.db.get(Asset, asset_id)
    if not asset or asset.project_id != ctx.project_id:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Asset not found in this project.",
            details={"assetId": asset_id, "projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    return asset


async def get_library_folder_map(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return get_folder_map_for_codirector(ctx.db, ctx.project_id)


async def get_library_context_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = int(args.get("limit") or 8)
    return get_library_context(ctx.db, ctx.project_id, recent_limit=max(1, min(limit, 20)))


async def resolve_library_location_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return resolve_library_location(
        ctx.db,
        ctx.project_id,
        path=args.get("path") or None,
        system_key=args.get("systemKey") or args.get("system_key") or None,
        query=args.get("query") or None,
    )


async def search_library_assets_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or args.get("q") or "")
    if not query.strip():
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "A search query is required.",
            details={"parameter": "query"},
            recoverable=True,
            recommended_action="retry",
        )
    return search_library_assets(
        ctx.db,
        ctx.project_id,
        query=query,
        entity_type=args.get("entityType") or args.get("entity_type") or None,
        folder_id=args.get("folderId") or args.get("folder_id") or None,
        system_key=args.get("systemKey") or args.get("system_key") or None,
        limit=int(args.get("limit") or 12),
    )


async def plan_library_storage(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    task = str(args.get("task") or "store_asset")
    return storage_preflight(
        ctx.db,
        ctx.project_id,
        task=task,
        system_key=args.get("systemKey") or args.get("system_key") or None,
        path=args.get("path") or None,
        entity_type=args.get("entityType") or args.get("entity_type") or None,
        entity_name=args.get("entityName") or args.get("entity_name") or None,
        entity_id=args.get("entityId") or args.get("entity_id") or None,
        filename_hint=args.get("filenameHint") or args.get("expectedName") or None,
    )


async def link_bible_entity_folder_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    entity_type = str(args.get("entityType") or args.get("entity_type") or "")
    entity_name = str(args.get("entityName") or args.get("entity_name") or "")
    if not entity_type or not entity_name:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "entityType and entityName are required.",
            details={"entityType": entity_type, "entityName": entity_name},
            recoverable=True,
            recommended_action="retry",
        )
    return link_bible_entity_folder(
        ctx.db,
        ctx.project_id,
        entity_type=entity_type,
        entity_name=entity_name,
        entity_id=args.get("entityId") or args.get("entity_id") or None,
        subfolder_system_key=args.get("systemKey") or args.get("system_key") or None,
    )


def preview_propose_asset_library_assignment(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    asset = _require_asset(ctx, str(args.get("assetId") or args.get("asset_id") or ""))
    loc = resolve_library_location(
        ctx.db,
        ctx.project_id,
        path=args.get("path") or None,
        system_key=args.get("systemKey") or args.get("system_key") or None,
        query=args.get("query") or None,
    )
    if loc.get("ambiguous"):
        return ToolPreview(
            summary=f"Ambiguous folder for '{args.get('path') or args.get('query')}' — choose a candidate.",
            lines=[f"candidates: {loc.get('candidates') or []}"],
        )
    match = loc.get("match") or {}
    return ToolPreview(
        summary=f"Move '{asset.tag or asset.filename}' → {match.get('libraryPath') or match.get('displayPath') or 'target folder'}",
        lines=[
            f"assetId: {asset.id}",
            f"targetPath: {match.get('libraryPath') or match.get('displayPath')}",
            f"systemKey: {args.get('systemKey') or match.get('systemKey')}",
            f"override: {bool(args.get('override', True))}",
        ],
    )


def apply_propose_asset_library_assignment(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    asset = _require_asset(ctx, str(args.get("assetId") or args.get("asset_id") or ""))
    meta = assign_asset(
        ctx.db,
        asset,
        system_key=args.get("systemKey") or args.get("system_key") or None,
        folder_id=args.get("folderId") or args.get("folder_id") or None,
        entity_type=args.get("entityType") or args.get("entity_type") or None,
        entity_name=args.get("entityName") or args.get("entity_name") or None,
        entity_id=args.get("entityId") or args.get("entity_id") or None,
        classified_by="codirector",
        override=bool(args.get("override", True)),
    )
    return {"ok": True, "asset": enrich_library_item(asset), "meta": meta.to_dict()}
