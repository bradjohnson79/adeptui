"""SQLAlchemy persistence for Voice Performance plans, segments, assemblies."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class PerformancePlanRow(Base):
    __tablename__ = "voice_performance_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    scene_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    shot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    timeline_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    character_id: Mapped[str] = mapped_column(String(36), index=True)
    character_profile_version_id: Mapped[str] = mapped_column(String(64), default="")
    voice_version_id: Mapped[str] = mapped_column(String(36), default="")
    performance_bible_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    emotion_profile_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pronunciation_profile_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reaction_library_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    script_source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, default="")
    segments_json: Mapped[str] = mapped_column(Text, default="[]")
    provider_preferences_json: Mapped[str] = mapped_column(Text, default="[]")
    applied_defaults_json: Mapped[str] = mapped_column(Text, default="{}")
    issues_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|submitted|generating|assembled|approved
    immutable: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    compiler_version: Mapped[str] = mapped_column(String(32), default="w44.1")
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(64), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    provenance_json: Mapped[str] = mapped_column(Text, default="{}")


class PerformanceAssemblyRow(Base):
    __tablename__ = "voice_performance_assemblies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    composite_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    segment_asset_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    timeline_clip_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    timing_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
