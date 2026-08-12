"""System catalogs for Templates & Presets and Project Types."""

from .project_types import (
    BUILTIN_PROJECT_TYPES,
    get_builtin_project_type,
    list_builtin_project_types,
    resolve_type_slug,
)
from .seed_placeholders import list_system_items, system_items_by_slug

__all__ = [
    "BUILTIN_PROJECT_TYPES",
    "get_builtin_project_type",
    "list_builtin_project_types",
    "list_system_items",
    "resolve_type_slug",
    "system_items_by_slug",
]
