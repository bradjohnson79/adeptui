"""SQLAlchemy models for Wave 5 continuity domain."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ContinuityPolicyRow(Base):
    __tablename__ = "continuity_policies"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    continuity_policy_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    preflight_mode: Mapped[str] = mapped_column(String(32), default="off")
    evaluation_mode: Mapped[str] = mapped_column(String(32), default="manual")
    production_master_requires_decision: Mapped[bool] = mapped_column(Boolean, default=False)
    critical_severity_behavior: Mapped[str] = mapped_column(String(32), default="warn")
    default_evaluator_key: Mapped[str] = mapped_column(String(120), default="continuity.rule_based_v1")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class VisualIdentityRow(Base):
    __tablename__ = "visual_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    visual_identity_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    identity_type: Mapped[str] = mapped_column(String(64), default="character")
    canonical_name: Mapped[str] = mapped_column(String(200), default="")
    display_name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    active_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    production_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    character_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    bible_entity_stable_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class IdentityVersionRow(Base):
    __tablename__ = "identity_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    identity_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    parent_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    label: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    identity_trait_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    traits_json: Mapped[str] = mapped_column(Text, default="{}")
    constraint_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    reference_set_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class IdentityVariantRow(Base):
    __tablename__ = "identity_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    identity_id: Mapped[str] = mapped_column(String(36), index=True)
    identity_version_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    variant_type: Mapped[str] = mapped_column(String(64), default="custom")
    name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    trait_overrides_json: Mapped[str] = mapped_column(Text, default="{}")
    locked_traits_json: Mapped[str] = mapped_column(Text, default="[]")
    reference_set_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class ApprovedReferenceRow(Base):
    __tablename__ = "approved_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    identity_id: Mapped[str] = mapped_column(String(36), index=True)
    identity_version_id: Mapped[str] = mapped_column(String(36), index=True)
    variant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    reference_role_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    roles_json: Mapped[str] = mapped_column(Text, default="[]")
    approval_status: Mapped[str] = mapped_column(String(32), default="candidate")
    quality_status: Mapped[str] = mapped_column(String(64), default="unknown")
    crop_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    view_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    notes: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    approved_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    revoke_reason: Mapped[str] = mapped_column(Text, default="")


class ContinuityConstraintRow(Base):
    __tablename__ = "continuity_constraints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    identity_id: Mapped[str] = mapped_column(String(36), index=True)
    identity_version_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    variant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    continuity_constraint_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    dimension: Mapped[str] = mapped_column(String(64), default="")
    policy: Mapped[str] = mapped_column(String(64), default="prefer")
    severity: Mapped[str] = mapped_column(String(32), default="minor")
    expected_value_json: Mapped[str] = mapped_column(Text, default="null")
    tolerance_json: Mapped[str] = mapped_column(Text, default="null")
    evaluator_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")


class ContinuityPacketRow(Base):
    __tablename__ = "continuity_packets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    request_id: Mapped[str] = mapped_column(String(120), index=True)
    continuity_packet_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    bindings_json: Mapped[str] = mapped_column(Text, default="[]")
    workflow_capability_statement_json: Mapped[str] = mapped_column(Text, default="{}")
    resolver_version: Mapped[str] = mapped_column(String(120), default="")
    compiler_version: Mapped[str] = mapped_column(String(120), default="")
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(64), default="")


class ContinuityEvaluationRow(Base):
    __tablename__ = "continuity_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    packet_id: Mapped[str] = mapped_column(String(36), index=True)
    continuity_evaluation_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    evaluator_key: Mapped[str] = mapped_column(String(120), default="")
    evaluator_version: Mapped[str] = mapped_column(String(64), default="")
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_status: Mapped[str] = mapped_column(String(32), default="not_assessable")
    dimensions_json: Mapped[str] = mapped_column(Text, default="[]")
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    mark_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class ContinuityReviewRow(Base):
    __tablename__ = "continuity_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    evaluation_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    review_decision_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    decision: Mapped[str] = mapped_column(String(64), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    previous_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer: Mapped[str] = mapped_column(String(120), default="")
    correction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")


class ContinuityIssueRow(Base):
    __tablename__ = "continuity_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    issue_type: Mapped[str] = mapped_column(String(64), default="")
    severity: Mapped[str] = mapped_column(String(32), default="major")
    status: Mapped[str] = mapped_column(String(32), default="open")
    title: Mapped[str] = mapped_column(String(300), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    identity_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    asset_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    packet_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    evaluation_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    resolved_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ContinuityCorrectionRow(Base):
    __tablename__ = "continuity_corrections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    source_asset_id: Mapped[str] = mapped_column(String(36), index=True)
    packet_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evaluation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    issue_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    certified: Mapped[bool] = mapped_column(Boolean, default=False)
    workflow_key: Mapped[str] = mapped_column(String(120), default="")
    image_edit_intent_json: Mapped[str] = mapped_column(Text, default="{}")
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    derived_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    enqueued_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ContinuityHistoryRow(Base):
    __tablename__ = "continuity_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="")
    entity_type: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[str] = mapped_column(String(36), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    actor: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
