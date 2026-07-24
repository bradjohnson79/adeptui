"""Unified Source Manager (Phase 1)."""

from .api import router
from .migration import ensure_migrated
from .registry import detect_all, select_provider
from .service import get_overview, remove_component_source, save_verified_source_for_component

__all__ = [
    "router",
    "ensure_migrated",
    "detect_all",
    "select_provider",
    "get_overview",
    "save_verified_source_for_component",
    "remove_component_source",
]
