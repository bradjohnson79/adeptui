"""Input validation for continuity domain."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .constants import (
    IDENTITY_TYPES,
    REFERENCE_ROLES,
    REFERENCE_STATUSES,
    VARIANT_TYPES,
    VISIBILITY,
)


def require_identity_type(identity_type: str) -> str:
    t = (identity_type or "").strip().lower()
    if t not in IDENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_IDENTITY_TYPE",
                "message": f"Identity type '{identity_type}' is not registered.",
                "allowed": sorted(IDENTITY_TYPES),
            },
        )
    return t


def require_roles(roles: list[str]) -> list[str]:
    out: list[str] = []
    for r in roles or []:
        key = str(r).strip().lower()
        if key not in REFERENCE_ROLES:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_REFERENCE_ROLE",
                    "message": f"Reference role '{r}' is not registered.",
                    "allowed": sorted(REFERENCE_ROLES),
                },
            )
        if key not in out:
            out.append(key)
    return out


def require_variant_type(variant_type: str) -> str:
    t = (variant_type or "custom").strip().lower()
    if t not in VARIANT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_VARIANT_TYPE", "message": f"Unknown variant type '{variant_type}'."},
        )
    return t


def require_visibility(visibility: str) -> str:
    v = (visibility or "fully_visible").strip().lower()
    if v not in VISIBILITY:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_VISIBILITY", "message": f"Unknown visibility '{visibility}'."},
        )
    return v


def reject_external_url(asset_id: str) -> None:
    s = (asset_id or "").strip().lower()
    if s.startswith("http://") or s.startswith("https://") or "://" in s:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EXTERNAL_URL_REJECTED",
                "message": "Canonical references must be registered project assets, not external URLs.",
            },
        )


def sanitize_user_text(text: str | None, *, max_len: int = 4000) -> str:
    """Treat descriptive text as untrusted — strip control chars, bound length."""
    if not text:
        return ""
    cleaned = "".join(ch for ch in str(text) if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return cleaned[:max_len]


def traits_are_dicts(traits: Any) -> dict[str, Any]:
    if traits is None:
        return {}
    if not isinstance(traits, dict):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_TRAITS", "message": "Traits must be an object."},
        )
    return dict(traits)


def assert_reference_status_transition(current: str, target: str) -> None:
    if target not in REFERENCE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REFERENCE_STATUS", "message": f"Invalid status '{target}'."},
        )
    if current == "revoked" and target == "approved":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REVOCATION_IRREVERSIBLE",
                "message": "Revoked references cannot be re-approved; create a new reference.",
            },
        )
