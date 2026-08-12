"""SQLAlchemy models for project password protection."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ProjectSecurityRow(Base):
    __tablename__ = "project_security"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    password_protected: Mapped[int] = mapped_column(Integer, default=0)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_algorithm: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_params_json: Mapped[str] = mapped_column(Text, default="{}")
    password_version: Mapped[int] = mapped_column(Integer, default=1)
    password_hint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    protection_policy_json: Mapped[str] = mapped_column(Text, default="{}")
    protection_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectUnlockGrantRow(Base):
    __tablename__ = "project_unlock_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[str] = mapped_column(String(64), default="local")
    password_version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProjectSecurityAuditRow(Base):
    __tablename__ = "project_security_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    event: Mapped[str] = mapped_column(String(64))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectUnlockAttemptRow(Base):
    __tablename__ = "project_unlock_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    client_key: Mapped[str] = mapped_column(String(128), default="")
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
