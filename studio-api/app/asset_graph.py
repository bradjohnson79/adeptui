from __future__ import annotations

"""Asset graph + version lineage helpers."""

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, String, Text
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


def search_assets(db: Session, project_id: str | None, q: str, *, global_only: bool = False) -> list[Asset]:
    query = db.query(Asset)
    if global_only:
        query = query.filter(Asset.scope == "global")
    elif project_id:
        query = query.filter((Asset.project_id == project_id) | (Asset.scope == "global"))
    term = (q or "").strip().lower()
    if not term:
        return query.order_by(Asset.created_at.desc()).limit(100).all()
    rows = query.order_by(Asset.created_at.desc()).limit(500).all()
    hits = []
    for a in rows:
        blob = " ".join(
            [
                a.tag or "",
                a.filename or "",
                a.kind or "",
                getattr(a, "labels_json", "") or "",
                getattr(a, "prompt_meta_json", "") or "",
            ]
        ).lower()
        if term in blob:
            hits.append(a)
    return hits[:100]
