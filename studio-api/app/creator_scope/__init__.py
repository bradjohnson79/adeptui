"""Canonical creator-asset scope: one isGlobal field for Character / Prop / Environment.

Global means cross-project visibility inside this Adept workspace.
It does not copy entities, drop owning projectId, or change tags.
"""

from .contract import (
    CREATOR_SCOPE_HELP,
    ENTITY_ENVIRONMENT,
    ENTITY_CHARACTER,
    ENTITY_PROP,
    CreatorScopeError,
    asset_is_global,
    canonical_tag,
    group_scope_items,
    is_visible_to_project,
    normalize_is_global,
)
from .service import (
    CreatorAssetScopeRow,
    delete_scope,
    ensure_creator_scope_tables,
    is_entity_deleted,
    mark_entity_deleted,
    find_tag_collision,
    list_cross_project_usage,
    list_visible_scope,
    load_entity_for_reference,
    require_delete_safety,
    resolve_readable_asset,
    sync_scope,
    visible_to_project,
)

__all__ = [
    "CREATOR_SCOPE_HELP",
    "ENTITY_CHARACTER",
    "ENTITY_ENVIRONMENT",
    "ENTITY_PROP",
    "CreatorAssetScopeRow",
    "CreatorScopeError",
    "asset_is_global",
    "canonical_tag",
    "delete_scope",
    "ensure_creator_scope_tables",
    "find_tag_collision",
    "group_scope_items",
    "is_entity_deleted",
    "is_visible_to_project",
    "mark_entity_deleted",
    "list_cross_project_usage",
    "list_visible_scope",
    "load_entity_for_reference",
    "normalize_is_global",
    "require_delete_safety",
    "resolve_readable_asset",
    "sync_scope",
    "visible_to_project",
]
