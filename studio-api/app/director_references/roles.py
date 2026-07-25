"""Reference binding role vocabulary for timeline Reference Sets."""

from __future__ import annotations

from typing import Literal

ReferenceRole = Literal[
    "character_identity",
    "costume",
    "prop",
    "environment",
    "architecture",
    "style",
    "lighting",
    "color",
    "composition",
    "camera",
    "motion",
    "start_frame",
    "end_frame",
    "continuity",
    "negative",
    "other",
]

REFERENCE_ROLES: tuple[str, ...] = (
    "character_identity",
    "costume",
    "prop",
    "environment",
    "architecture",
    "style",
    "lighting",
    "color",
    "composition",
    "camera",
    "motion",
    "start_frame",
    "end_frame",
    "continuity",
    "negative",
    "other",
)

# Roles that map to M2.5 vision validators when a referenceSet is supplied.
ROLE_TO_VALIDATOR: dict[str, str] = {
    "character_identity": "identity",
    "costume": "identity",
    "continuity": "continuity",
    "composition": "composition",
    "camera": "camera",
    "lighting": "lighting",
    "color": "color",
    "motion": "motion",
    "style": "composition",
    "start_frame": "continuity",
    "end_frame": "continuity",
}


def is_valid_role(role: str) -> bool:
    return role in REFERENCE_ROLES
