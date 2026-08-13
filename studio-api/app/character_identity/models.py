"""SQLAlchemy models for Character Identity (M3.3)."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class CharacterProfileRow(Base):
    __tablename__ = "character_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    slug: Mapped[str] = mapped_column(String(200), default="", index=True)
    role: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    apparent_age: Mapped[str] = mapped_column(String(64), default="")
    species_or_type: Mapped[str] = mapped_column(String(64), default="human")
    gender_presentation: Mapped[str] = mapped_column(String(64), default="")
    cultural_background: Mapped[str] = mapped_column(String(120), default="")
    height_description: Mapped[str] = mapped_column(String(120), default="")
    body_type: Mapped[str] = mapped_column(String(120), default="")
    visual_description: Mapped[str] = mapped_column(Text, default="")
    visual_style: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    approval_status: Mapped[str] = mapped_column(String(32), default="draft")
    active_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active_voice_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active_wardrobe_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    skin_json: Mapped[str] = mapped_column(Text, default="{}")
    hair_json: Mapped[str] = mapped_column(Text, default="{}")
    personality_json: Mapped[str] = mapped_column(Text, default="{}")
    performance_json: Mapped[str] = mapped_column(Text, default="{}")
    continuity_json: Mapped[str] = mapped_column(Text, default="{}")
    motion_json: Mapped[str] = mapped_column(Text, default="{}")
    emotion_json: Mapped[str] = mapped_column(Text, default="{}")
    relationships_json: Mapped[str] = mapped_column(Text, default="[]")
    prompt_package_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class CharacterVersionRow(Base):
    __tablename__ = "character_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    character_profile_id: Mapped[str] = mapped_column(String(36), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    version_label: Mapped[str] = mapped_column(String(120), default="")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    parent_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[str] = mapped_column(String(64), default="")
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    locked_at: Mapped[str] = mapped_column(String(64), default="")
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class CharacterReferenceAssetRow(Base):
    __tablename__ = "character_reference_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    character_profile_id: Mapped[str] = mapped_column(String(36), index=True)
    character_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), index=True)
    reference_role: Mapped[str] = mapped_column(String(64), index=True)
    view_angle: Mapped[str] = mapped_column(String(64), default="")
    framing: Mapped[str] = mapped_column(String(64), default="")
    approval_status: Mapped[str] = mapped_column(String(32), default="draft")
    canonical: Mapped[bool] = mapped_column(Boolean, default=False)
    source_type: Mapped[str] = mapped_column(String(64), default="upload")
    generation_lineage_json: Mapped[str] = mapped_column(Text, default="{}")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class CharacterTraitRow(Base):
    __tablename__ = "character_traits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    character_profile_id: Mapped[str] = mapped_column(String(36), index=True)
    character_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="")
    key: Mapped[str] = mapped_column(String(120), default="")
    value: Mapped[str] = mapped_column(Text, default="")
    importance: Mapped[str] = mapped_column(String(32), default="canonical")
    canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    provenance: Mapped[str] = mapped_column(String(64), default="PROPOSED_BY_CHARACTER_CREATOR")


class CharacterWardrobeRow(Base):
    __tablename__ = "character_wardrobes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    character_profile_id: Mapped[str] = mapped_column(String(36), index=True)
    character_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(String(32), default="draft")
    materials: Mapped[str] = mapped_column(Text, default="")
    colors: Mapped[str] = mapped_column(Text, default="")
    footwear: Mapped[str] = mapped_column(String(200), default="")
    jewelry: Mapped[str] = mapped_column(Text, default="")
    accessories: Mapped[str] = mapped_column(Text, default="")
    makeup_state: Mapped[str] = mapped_column(String(200), default="")
    hair_state: Mapped[str] = mapped_column(String(200), default="")
    continuity_rules: Mapped[str] = mapped_column(Text, default="")
    reference_asset_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    scene_assignments_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class CharacterPropRow(Base):
    __tablename__ = "character_props"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    character_profile_id: Mapped[str] = mapped_column(String(36), index=True)
    character_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    prop_type: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    materials: Mapped[str] = mapped_column(Text, default="")
    colors: Mapped[str] = mapped_column(Text, default="")
    placement: Mapped[str] = mapped_column(String(200), default="")
    how_worn: Mapped[str] = mapped_column(Text, default="")
    hand_assignment: Mapped[str] = mapped_column(String(64), default="")
    usage_behavior: Mapped[str] = mapped_column(Text, default="")
    continuity_rules: Mapped[str] = mapped_column(Text, default="")
    library_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="draft")
    reference_asset_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    # Phase 6 Props workspace: pending image-generation job id for an
    # in-flight prop image. Cleared once the job completes and the output
    # asset is linked via library_asset_id. Stored on the prop row so the
    # frontend can poll a single prop-status endpoint without a parallel
    # job-tracking table.
    generation_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")


class VoiceProfileRow(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    character_profile_id: Mapped[str] = mapped_column(String(36), index=True)
    character_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(200), default="")
    source_mode: Mapped[str] = mapped_column(String(32), default="UNASSIGNED")
    provider: Mapped[str] = mapped_column(String(64), default="")
    model_id: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    approval_status: Mapped[str] = mapped_column(String(32), default="draft")
    language: Mapped[str] = mapped_column(String(32), default="en")
    accent: Mapped[str] = mapped_column(String(64), default="")
    perceived_age: Mapped[str] = mapped_column(String(64), default="")
    pitch_description: Mapped[str] = mapped_column(String(120), default="")
    pace_description: Mapped[str] = mapped_column(String(120), default="")
    tone_description: Mapped[str] = mapped_column(String(120), default="")
    resonance_description: Mapped[str] = mapped_column(String(120), default="")
    warmth: Mapped[str] = mapped_column(String(64), default="")
    breathiness: Mapped[str] = mapped_column(String(64), default="")
    energy: Mapped[str] = mapped_column(String(64), default="")
    emotional_range: Mapped[str] = mapped_column(String(120), default="")
    pronunciation_notes: Mapped[str] = mapped_column(Text, default="")
    voice_design_prompt: Mapped[str] = mapped_column(Text, default="")
    reference_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reference_transcript: Mapped[str] = mapped_column(Text, default="")
    approved_preview_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    consent_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    candidate_asset_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    lineage_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
    approved_at: Mapped[str] = mapped_column(String(64), default="")


class VoiceConsentRecordRow(Base):
    __tablename__ = "voice_consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    voice_profile_id: Mapped[str] = mapped_column(String(36), index=True)
    source_owner_name: Mapped[str] = mapped_column(String(200), default="")
    performer_name: Mapped[str] = mapped_column(String(200), default="")
    authority_type: Mapped[str] = mapped_column(String(64), default="self")
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    commercial_use_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    synthetic_generation_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    project_scope: Mapped[str] = mapped_column(String(64), default="project")
    restriction_notes: Mapped[str] = mapped_column(Text, default="")
    confirmation_timestamp: Mapped[str] = mapped_column(String(64), default="")
    confirmed_by: Mapped[str] = mapped_column(String(120), default="")


CHARACTER_IDENTITY_TABLES = [
    CharacterProfileRow.__table__,
    CharacterVersionRow.__table__,
    CharacterReferenceAssetRow.__table__,
    CharacterTraitRow.__table__,
    CharacterWardrobeRow.__table__,
    CharacterPropRow.__table__,
    VoiceProfileRow.__table__,
    VoiceConsentRecordRow.__table__,
]
