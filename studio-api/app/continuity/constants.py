"""Wave 5 continuity constants — registered types, roles, statuses."""

from __future__ import annotations

IDENTITY_TYPES = frozenset(
    {
        "character",
        "environment",
        "location",
        "prop",
        "vehicle",
        "creature",
        "wardrobe",
        "object",
        "graphic_element",
    }
)

IDENTITY_STATUSES = frozenset(
    {"draft", "in_review", "approved", "deprecated", "archived", "blocked"}
)

VERSION_STATUSES = frozenset({"draft", "in_review", "approved", "deprecated", "archived"})

REFERENCE_STATUSES = frozenset(
    {"candidate", "in_review", "approved", "rejected", "deprecated", "revoked"}
)

VARIANT_TYPES = frozenset(
    {
        "wardrobe",
        "age",
        "era",
        "hairstyle",
        "expression",
        "injury",
        "damage",
        "transformation",
        "lighting",
        "weather",
        "location_state",
        "prop_state",
        "custom",
    }
)

REFERENCE_ROLES = frozenset(
    {
        "canonical_front",
        "canonical_three_quarter",
        "canonical_profile",
        "canonical_back",
        "face_closeup",
        "full_body",
        "body_proportion",
        "hair",
        "eyes",
        "skin",
        "markings",
        "wardrobe_front",
        "wardrobe_side",
        "wardrobe_back",
        "wardrobe_detail",
        "prop",
        "environment_wide",
        "environment_layout",
        "environment_material",
        "lighting_reference",
        "palette_reference",
        "expression",
        "pose",
        "style_reference",
        "negative_reference",
        "historical_reference",
    }
)

VISIBILITY = frozenset(
    {
        "fully_visible",
        "partially_visible",
        "occluded",
        "offscreen",
        "background",
        "not_expected",
    }
)

CONSTRAINT_POLICIES = frozenset(
    {"lock", "prefer", "allow_range", "allow_variant_only", "warn", "informational"}
)

SEVERITIES = frozenset({"critical", "major", "minor", "informational"})

PREFLIGHT_STATUSES = frozenset(
    {"ready", "ready_with_warnings", "needs_review", "blocked", "not_applicable"}
)

EVAL_DIM_STATUSES = frozenset(
    {"pass", "review", "drift", "not_assessable", "not_applicable", "error"}
)

REVIEW_DECISIONS = frozenset(
    {
        "approve",
        "reject",
        "approve_with_notes",
        "override_warning",
        "request_correction",
        "mark_not_applicable",
        "mark_evaluator_error",
    }
)

CHARACTER_DIMENSIONS = (
    "face_structure",
    "eyes",
    "hair",
    "skin",
    "ears",
    "body_proportion",
    "silhouette",
    "wardrobe",
    "markings",
    "jewelry",
    "species_traits",
    "expression",
    "pose",
    "overall_identity",
)

ENVIRONMENT_DIMENSIONS = (
    "layout",
    "architecture",
    "materials",
    "palette",
    "lighting",
    "landmarks",
    "scale",
    "signage",
    "prop_placement",
    "overall_environment",
)

# Dimensions that require face/front visibility
FACE_DEPENDENT_DIMENSIONS = frozenset({"face_structure", "eyes", "skin", "ears", "expression"})
BACK_DEPENDENT_DIMENSIONS = frozenset({"wardrobe"})  # wardrobe_back detail checked via roles

COMPILER_VERSION = "continuity-packet-compiler/1.0.0"
RESOLVER_VERSION = "continuity-reference-resolver/1.0.0"
EVALUATOR_KEY = "continuity.rule_based_v1"
EVALUATOR_VERSION = "1.0.0"
