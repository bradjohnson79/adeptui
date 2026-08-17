from __future__ import annotations

"""Asset graph + version lineage helpers."""

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, String, Text, or_
from sqlalchemy.orm import Mapped, mapped_column, Session

from .db import Base, Asset, engine

EDGE_RELATIONS = (
    "character_of",
    "used_in_scene",
    "derived_from",
    "motion_for",
    "from_segment",
    "storyboard_of",
    "spatial_of",
    "camera_of",
    "used_in_director",
    "related",
)


class AssetVersion(Base):
    __tablename__ = "asset_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    op: Mapped[str] = mapped_column(String(64), default="generate")
    seed: Mapped[int] = mapped_column(Integer, default=-1)
    prompt_json: Mapped[str] = mapped_column(Text, default="{}")
    model: Mapped[str] = mapped_column(String(200), default="")
    path: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssetEdge(Base):
    __tablename__ = "asset_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    from_id: Mapped[str] = mapped_column(String(36), index=True)
    to_id: Mapped[str] = mapped_column(String(36), index=True)
    relation: Mapped[str] = mapped_column(String(64), default="related")
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def ensure_graph_tables() -> None:
    Base.metadata.create_all(bind=engine, tables=[AssetVersion.__table__, AssetEdge.__table__])


def add_version(
    db: Session,
    *,
    asset_id: str,
    op: str,
    path: str,
    seed: int = -1,
    prompt: dict | None = None,
    model: str = "",
) -> AssetVersion:
    prev = (
        db.query(AssetVersion)
        .filter(AssetVersion.asset_id == asset_id)
        .order_by(AssetVersion.version.desc())
        .first()
    )
    ver = (prev.version + 1) if prev else 1
    row = AssetVersion(
        id=str(uuid.uuid4()),
        asset_id=asset_id,
        version=ver,
        op=op,
        seed=seed,
        prompt_json=json.dumps(prompt or {}),
        model=model,
        path=path,
    )
    db.add(row)
    return row


def add_edge(db: Session, from_id: str, to_id: str, relation: str, meta: dict | None = None) -> AssetEdge:
    row = AssetEdge(
        id=str(uuid.uuid4()),
        from_id=from_id,
        to_id=to_id,
        relation=relation,
        meta_json=json.dumps(meta or {}),
    )
    db.add(row)
    return row


def neighbors(db: Session, node_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in db.query(AssetEdge).filter((AssetEdge.from_id == node_id) | (AssetEdge.to_id == node_id)).all():
        other = e.to_id if e.from_id == node_id else e.from_id
        out.append({"edge_id": e.id, "other_id": other, "relation": e.relation, "from_id": e.from_id, "to_id": e.to_id})
    return out


def _asset_query(
    db: Session,
    project_id: str | None,
    q: str,
    *,
    global_only: bool = False,
):
    """Shared SQL filter for asset search - project-scoped plus promoted global rows."""
    query = db.query(Asset)
    if global_only:
        query = query.filter(Asset.scope == "global")
    elif project_id:
        query = query.filter((Asset.project_id == project_id) | (Asset.scope == "global"))
    term = (q or "").strip().lower()
    if term:
        like = _like_pattern(term)
        query = query.filter(
            or_(
                Asset.tag.ilike(like, escape="\\"),
                Asset.filename.ilike(like, escape="\\"),
                Asset.kind.ilike(like, escape="\\"),
                Asset.labels_json.ilike(like, escape="\\"),
                Asset.prompt_meta_json.ilike(like, escape="\\"),
            )
        )
    return query


def _like_pattern(term: str) -> str:
    """Escape LIKE wildcards so user queries match literally, not as patterns."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_assets(
    db: Session,
    project_id: str | None,
    q: str,
    *,
    global_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Asset]:
    """Search assets with SQL-level filters and bounded paging (no scan-window cap).

    CDX-067: the previous implementation loaded only the 500 most-recent rows and
    returned at most 100, so older assets were unsearchable. Any asset is now
    reachable by tag/filename/kind/labels via LIMIT/OFFSET paging, newest-first.
    `global_only` restricts to assets promoted via promote_asset_global.
    """
    page_size = max(1, min(limit, 500))
    page_offset = max(0, offset)
    query = _asset_query(db, project_id, q, global_only=global_only)
    return query.order_by(Asset.created_at.desc()).offset(page_offset).limit(page_size).all()


def count_assets(
    db: Session,
    project_id: str | None,
    q: str,
    *,
    global_only: bool = False,
    project_only: bool = False,
) -> int:
    """Count assets matching the same filters as search_assets (pagination metadata).

    `project_only` counts rows strictly local to the project (excludes promoted
    global rows) so project-scope pagination metadata stays truthful.
    """
    query = _asset_query(db, project_id, q, global_only=global_only)
    if project_only:
        query = query.filter(Asset.project_id == project_id)
    return int(query.count())
