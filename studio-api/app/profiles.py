from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, engine


def _nid() -> str:
    return uuid.uuid4().hex


ProfileKind = Literal[
    "character",
    "prop",
    "scene",
    "motion",
    "camera_preset",
    "motion_preset",
    "voice",
]


class ProfileItem(Base):
    """Cross-project Production DNA library entry."""

    __tablename__ = "profile_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    tag: Mapped[str] = mapped_column(String(64), default="")  # e.g. #walkMilitary
    category: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    media_path: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProfileOut(BaseModel):
    id: str
    kind: str
    name: str = ""
    tag: str = ""
    category: str = ""
    description: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    media_path: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True

    @classmethod
    def from_row(cls, row: ProfileItem) -> "ProfileOut":
        try:
            data = json.loads(row.data_json or "{}")
        except Exception:
            data = {}
        return cls(
            id=row.id,
            kind=row.kind,
            name=row.name,
            tag=row.tag,
            category=row.category,
            description=row.description,
            data=data if isinstance(data, dict) else {},
            media_path=row.media_path or "",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class ProfileIn(BaseModel):
    name: str = ""
    tag: str = ""
    category: str = ""
    description: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    media_path: str = ""


def ensure_profile_tables() -> None:
    Base.metadata.create_all(bind=engine, tables=[ProfileItem.__table__])


def normalize_motion_tag(tag: str, name: str = "") -> str:
    raw = (tag or name or "motion").strip()
    if not raw.startswith("#"):
        raw = "#" + raw
    cleaned = "#" + "".join(ch for ch in raw[1:] if ch.isalnum() or ch in ("_", "-"))
    if cleaned == "#":
        cleaned = "#motion"
    # camelCase-ish: walk military -> walkMilitary if spaces
    return cleaned
