"""Project-scoped typed reference aliases (@ CRS, # ERS, % PRS, * video)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SceneReferenceBinding
from .sheet_tags import (
    ALL_PREFIXES,
    display_sheet_token,
    pascal_alias,
    prefix_for_reference,
)

MEDIA_KINDS = frozenset({"entity", "image", "video"})
ENTITY_TYPES = frozenset(
    {
        "character",
        "prop",
        "wardrobe",
        "vehicle",
        "creature",
        "environment",
        "location",
        "style",
        "lighting",
        "composition",
        "pose",
        "other",
    }
)

_TOKEN_RE = re.compile(r"[^A-Za-z0-9_]")


def strip_prefix(raw: str) -> str:
    token = (raw or "").strip()
    if token[:1] in ALL_PREFIXES:
        token = token[1:]
    return token.strip()


def sanitize_alias(raw: str | None) -> str:
    token = pascal_alias(raw or "", "")
    if token:
        return token
    stripped = strip_prefix(raw or "")
    stripped = re.sub(r"\s+", "", stripped)
    return _TOKEN_RE.sub("", stripped)


def prefix_for_media_kind(media_kind: str, reference_type: str | None = None) -> str:
    return prefix_for_reference(reference_type, media_kind)


def media_kind_for(reference_type: str, *, asset_kind: str | None = None) -> str:
    if reference_type == "image":
        return "image"
    if reference_type in ("video", "motion"):
        return "video"
    if reference_type in ENTITY_TYPES:
        return "entity"
    kind = (asset_kind or "").lower()
    if kind == "video":
        return "video"
    if kind == "image":
        return "image"
    return "entity"


def display_token(alias: str, media_kind: str, reference_type: str | None = None) -> str:
    token = sanitize_alias(alias)
    if not token:
        return ""
    return display_sheet_token(token, reference_type, media_kind)


def list_project_aliases(
    db: Session,
    project_id: str,
    *,
    exclude_id: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> set[str]:
    q = select(SceneReferenceBinding.alias).where(
        SceneReferenceBinding.project_id == project_id,
        SceneReferenceBinding.alias.is_not(None),
        SceneReferenceBinding.deleted_at.is_(None),
    )
    if scope_type:
        q = q.where(SceneReferenceBinding.scope_type == scope_type)
    if scope_id:
        q = q.where(SceneReferenceBinding.scope_id == scope_id)
    if exclude_id:
        q = q.where(SceneReferenceBinding.id != exclude_id)
    out: set[str] = set()
    for alias in db.scalars(q).all():
        token = sanitize_alias(str(alias or ""))
        if token:
            out.add(token.lower())
    return out


def unique_alias(
    db: Session,
    project_id: str,
    desired: str | None,
    *,
    exclude_id: str | None = None,
    fallback: str = "Reference",
    scope_type: str | None = None,
    scope_id: str | None = None,
    allow_collision_suffix: bool = True,
) -> tuple[str, bool]:
    """Return a scope-unique alias. Project-wide when scope is omitted (legacy).

    Identity tags (character / prop / environment) must pass
    ``allow_collision_suffix=False``. Collision suffixes are internal only and
    must never become generator-facing identity.
    """
    base = sanitize_alias(desired) or sanitize_alias(fallback) or "Reference"
    taken = list_project_aliases(
        db,
        project_id,
        exclude_id=exclude_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    if base.lower() not in taken:
        return base, False
    if not allow_collision_suffix:
        return base, False
    n = 2
    while True:
        candidate = f"{base}{n}"
        if candidate.lower() not in taken:
            return candidate, True
        n += 1
