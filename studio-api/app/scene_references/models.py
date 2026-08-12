"""ORM models for Scene Reference Bindings."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SceneReferenceBinding(Base):
    __tablename__ = "scene_reference_bindings"
    __table_args__ = (
        Index("ix_srb_project_scope", "project_id", "scope_type", "scope_id"),
        Index("ix_srb_asset", "asset_id"),
        UniqueConstraint(
            "project_id",
            "scope_type",
            "scope_id",
            "asset_id",
            "reference_type",
            name="uq_srb_scope_asset_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)
    usage_modes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reference_roles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    identity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    identity_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    variant_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requested_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asset = relationship("Asset", lazy="joined")


class SceneReferenceAuditEvent(Base):
    __tablename__ = "scene_reference_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    binding_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
