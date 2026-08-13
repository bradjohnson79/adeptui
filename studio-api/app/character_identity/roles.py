"""Machine-readable Visual Identity Pack reference roles (M3.3)."""

from __future__ import annotations

REQUIRED_FULL_BODY = (
    "full_body_front",
    "full_body_side_left",
    "full_body_back",
)

OPTIONAL_FULL_BODY = (
    "full_body_side_right",
    "full_body_three_quarter_front",
    "full_body_three_quarter_back",
)

REQUIRED_CLOSEUP = (
    "closeup_front",
    "closeup_side_left",
    "closeup_back",
)

OPTIONAL_CLOSEUP = (
    "closeup_side_right",
    "closeup_three_quarter_front",
    "closeup_three_quarter_back",
)

ADDITIONAL_ROLES = (
    "hero_identity",
    "reference_image",
    "neutral_portrait",
    "expression_sheet",
    "pose_sheet",
    "turnaround_sheet",
    "hands_reference",
    "feet_reference",
    "scale_reference",
    "skin_closeup",
    "hair_front",
    "hair_side",
    "hair_back",
    "wardrobe_reference",
    "prop_reference",
    "accessory_reference",
)

ALL_REFERENCE_ROLES = (
    REQUIRED_FULL_BODY
    + OPTIONAL_FULL_BODY
    + REQUIRED_CLOSEUP
    + OPTIONAL_CLOSEUP
    + ADDITIONAL_ROLES
)

# Production-ready visual coverage: front/side/back for full-body and close-up.
REQUIRED_COVERAGE_ROLES = REQUIRED_FULL_BODY + REQUIRED_CLOSEUP

# Side can be satisfied by left or right.
SIDE_ALIASES = {
    "full_body_side": ("full_body_side_left", "full_body_side_right"),
    "closeup_side": ("closeup_side_left", "closeup_side_right"),
}

# Amendment 2b: hero_portrait → hero_identity rename.
# Legacy rows persisted with reference_role="hero_portrait" (before the rename)
# still resolve to hero_identity for reads, so existing approved characters
# continue to work during the migration window. The one-time data migration
# (migrations/hero_identity_rename.py) rewrites rows to hero_identity.
ROLE_ALIASES: dict[str, str] = {
    "hero_portrait": "hero_identity",
}


def canonical_role(role: str | None) -> str:
    """Resolve a reference role to its canonical name, applying legacy aliases."""
    if not role:
        return ""
    return ROLE_ALIASES.get(role, role)

ROLE_GUIDANCE = {
    "full_body_front": "Add a full-body front reference before generating full-body walking or establishing shots.",
    "full_body_side_left": "Side identity is not yet defined. Generate or upload a full-body side view before profile-angle generations.",
    "full_body_back": "Rear body identity is not yet defined. Generate or upload a full-body back view before rear-angle shots.",
    "closeup_front": "Add a close-up front reference before portrait or dialogue close-ups.",
    "closeup_side_left": "Side facial identity is not yet defined. Generate or upload a close-up side view before side-profile shots.",
    "closeup_back": "Rear hair identity is not yet defined. Generate or upload a close-up back view before creating rear-angle portrait shots.",
    "hair_back": "Rear hair identity is not yet defined. Generate or upload a close-up back / hair-back view before rear-angle portrait shots.",
}
