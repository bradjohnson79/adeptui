"""Reference-role contracts for character consistency work."""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class ReferenceRole(str, Enum):
    IDENTITY = "identity"
    FACE = "face"
    HAIR = "hair"
    WARDROBE = "wardrobe"
    BODY_PROPORTIONS = "body_proportions"
    EARS = "ears"
    MARKINGS = "markings"
    ACCESSORY = "accessory"
    ART_STYLE = "art_style"
    LIGHTING = "lighting"
    CAMERA = "camera"
    ENVIRONMENT = "environment"


REFERENCE_ROLES: tuple[str, ...] = tuple(role.value for role in ReferenceRole)

REFERENCE_ROLE_DESCRIPTIONS: dict[str, str] = {
    ReferenceRole.IDENTITY.value: "Primary character identity anchor for overall likeness.",
    ReferenceRole.FACE.value: "Face structure, eyes, and expression-preserving anchor.",
    ReferenceRole.HAIR.value: "Hair color, silhouette, texture, and arrangement anchor.",
    ReferenceRole.WARDROBE.value: "Clothing silhouette, palette, and material anchor.",
    ReferenceRole.BODY_PROPORTIONS.value: "Body scale and proportion anchor for full-body continuity.",
    ReferenceRole.EARS.value: "Ear shape or stylized ear detail anchor when visible.",
    ReferenceRole.MARKINGS.value: "Scars, tattoos, freckles, or unique markings anchor.",
    ReferenceRole.ACCESSORY.value: "Recurring accessories or hero prop anchor.",
    ReferenceRole.ART_STYLE.value: "Render-language anchor separate from identity.",
    ReferenceRole.LIGHTING.value: "Lighting look anchor separate from identity lock.",
    ReferenceRole.CAMERA.value: "Camera language and lens framing anchor.",
    ReferenceRole.ENVIRONMENT.value: "Background or set context anchor.",
}

IDENTITY_LOCK_ROLES: tuple[str, ...] = (
    ReferenceRole.IDENTITY.value,
    ReferenceRole.FACE.value,
    ReferenceRole.HAIR.value,
    ReferenceRole.WARDROBE.value,
    ReferenceRole.BODY_PROPORTIONS.value,
    ReferenceRole.EARS.value,
    ReferenceRole.MARKINGS.value,
    ReferenceRole.ACCESSORY.value,
)

STYLE_CONTEXT_ROLES: tuple[str, ...] = (
    ReferenceRole.ART_STYLE.value,
    ReferenceRole.LIGHTING.value,
    ReferenceRole.CAMERA.value,
    ReferenceRole.ENVIRONMENT.value,
)


def is_valid_role(role: str) -> bool:
    return role in REFERENCE_ROLES


def normalize_roles(roles: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for role in roles:
        if role not in normalized and is_valid_role(role):
            normalized.append(role)
    return normalized


def identity_roles() -> tuple[str, ...]:
    return IDENTITY_LOCK_ROLES


def style_roles() -> tuple[str, ...]:
    return STYLE_CONTEXT_ROLES
