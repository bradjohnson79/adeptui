"""Closed registries for scene reference bindings."""

from __future__ import annotations

SCOPE_TYPES = frozenset(
    {
        "project",
        "sequence",
        "scene",
        "shot",
        "clip",
        "start_frame",
        "middle_frame",
        "end_frame",
    }
)

# Inheritance precedence (highest first)
SCOPE_PRECEDENCE = (
    "clip",
    "shot",
    "end_frame",
    "middle_frame",
    "start_frame",
    "scene",
    "sequence",
    "project",
)

REFERENCE_TYPES = frozenset(
    {
        "character",
        "environment",
        "location",
        "prop",
        "wardrobe",
        "vehicle",
        "creature",
        "style",
        "lighting",
        "composition",
        "pose",
        "motion",
        "negative",
        "other",
        "image",
        "video",
    }
)

USAGE_MODES = frozenset(
    {
        "identity",
        "appearance",
        "wardrobe",
        "environment",
        "prop",
        "style",
        "composition",
        "lighting",
        "pose",
        "motion",
        "negative",
        "informational",
    }
)

WORKFLOW_SUPPORT = frozenset(
    {
        "reference_conditioned",
        "prompt_guided",
        "unsupported",
        "excluded_by_limit",
        "blocked",
    }
)
