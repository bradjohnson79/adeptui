"""SQLAlchemy persistence for Multi-Shot Image Planning.

Three tables, all project-scoped (every row carries `project_id`, so the generic
project-deletion sweep in `app.project_cleanup` covers them automatically):

- ``multi_shot_plans``      — one plan per (project, scene) decomposition effort.
- ``multi_shots``           — ordered shots inside a plan (``order_index``).
- ``multi_shot_candidates`` — append-only candidate history per shot; rejection
  never deletes a row, matching the honest-history rule for image candidates.

List payloads (references, subject ids, loras, settings) are stored as JSON text,
following the repo convention used by voice_performance / production_jobs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base


class MultiShotPlanRow(Base):
    __tablename__ = "multi_shot_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    scene_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(200), default="Multi-Shot Plan")
    # Provider-agnostic routing hints — plain strings, never validated against a
    # specific provider registry so any current/future provider can back a plan.
    provider_id: Mapped[str] = mapped_column(String(64), default="")
    model_id: Mapped[str] = mapped_column(String(128), default="")
    shared_visual_context: Mapped[str] = mapped_column(Text, default="")
    # Single polymorphic list of references; each entry carries a `role`
    # (style | character | environment | moodboard | ...). Grouped views are
    # derived at serialization time.
    shared_references_json: Mapped[str] = mapped_column(Text, default="[]")
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="")
    resolution_label: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="draft")  # draft|active|archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MultiShotRow(Base):
    __tablename__ = "multi_shots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(36), index=True)
    # Denormalized so project isolation checks and the deletion sweep never need
    # a join through the plan table.
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    scene_id: Mapped[str] = mapped_column(String(36), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    video_prompt: Mapped[str] = mapped_column(Text, default="")
    duration_hint: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    framing: Mapped[str] = mapped_column(String(64), default="")
    camera_angle: Mapped[str] = mapped_column(String(64), default="")
    subject_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    reference_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    seed_strategy: Mapped[str] = mapped_column(String(32), default="sequence")  # fixed|sequence|random|...
    status: Mapped[str] = mapped_column(String(24), default="pending")
    # pending|generating|candidate_review|approved|rejected
    approved_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # W46 Timeline batch block this shot was sent to (Multi-Shot → Timeline lineage).
    timeline_batch_block_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MultiShotCandidateRow(Base):
    __tablename__ = "multi_shot_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    shot_id: Mapped[str] = mapped_column(String(36), index=True)
    plan_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    generation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, default="")
    references_json: Mapped[str] = mapped_column(Text, default="[]")
    loras_json: Mapped[str] = mapped_column(Text, default="[]")
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    # Points at the shared Asset system once the candidate produced a real image.
    asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending")  # pending|approved|rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
