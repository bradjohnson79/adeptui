"""Project-scoped typed reference aliases (@ entity, # image, * video)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SceneReferenceBinding

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
    if token[:1] in "@#*":
        token = token[1:]
    return token.strip()


def sanitize_alias(raw: str | None) -> str:
    token = strip_prefix(raw or "")
    token = re.sub(r"\s+", "", token)
    token = _TOKEN_RE.sub("", token)
    return token


def prefix_for_media_kind(media_kind: str) -> str:
    if media_kind == "entity":
        return "@"
    if media_kind == "video":
        return "*"
    return "#"


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


def display_token(alias: str, media_kind: str) -> str:
    token = sanitize_alias(alias)
    if not token:
        return ""
    return f"{prefix_for_media_kind(media_kind)}{token}"


def list_project_aliases(
    db: Session, project_id: str, *, exclude_id: str | None = None
) -> set[str]:
    q = select(SceneReferenceBinding.alias).where(
        SceneReferenceBinding.project_id == project_id,
        SceneReferenceBinding.alias.is_not(None),
    )
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
) -> tuple[str, bool]:
    """Return a project-unique alias. Second value is True when the token was adjusted."""
    base = sanitize_alias(desired) or sanitize_alias(fallback) or "Reference"
    taken = list_project_aliases(db, project_id, exclude_id=exclude_id)
    if base.lower() not in taken:
        return base, False
    n = 2
    while True:
        candidate = f"{base}{n}"
        if candidate.lower() not in taken:
            return candidate, True
        n += 1
