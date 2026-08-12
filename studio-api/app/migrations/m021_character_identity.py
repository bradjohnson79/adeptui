"""M021: M3.3 Character Identity foundation tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0021"
CHECKSUM_SOURCE = "M021:character-identity-foundation:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS character_profiles (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        name VARCHAR(200) NOT NULL DEFAULT '',
        slug VARCHAR(200) NOT NULL DEFAULT '',
        role VARCHAR(120) NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        apparent_age VARCHAR(64) NOT NULL DEFAULT '',
        species_or_type VARCHAR(64) NOT NULL DEFAULT 'human',
        gender_presentation VARCHAR(64) NOT NULL DEFAULT '',
        cultural_background VARCHAR(120) NOT NULL DEFAULT '',
        height_description VARCHAR(120) NOT NULL DEFAULT '',
        body_type VARCHAR(120) NOT NULL DEFAULT '',
        status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
        approval_status VARCHAR(32) NOT NULL DEFAULT 'draft',
        active_version_id VARCHAR(36),
        active_voice_profile_id VARCHAR(36),
        active_wardrobe_id VARCHAR(36),
        skin_json TEXT NOT NULL DEFAULT '{}',
        hair_json TEXT NOT NULL DEFAULT '{}',
        personality_json TEXT NOT NULL DEFAULT '{}',
        performance_json TEXT NOT NULL DEFAULT '{}',
        continuity_json TEXT NOT NULL DEFAULT '{}',
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        updated_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_character_profiles_project ON character_profiles (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_character_profiles_slug ON character_profiles (slug)",
    """
    CREATE TABLE IF NOT EXISTS character_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        character_profile_id VARCHAR(36) NOT NULL,
        version_number INTEGER NOT NULL DEFAULT 1,
        version_label VARCHAR(120) NOT NULL DEFAULT '',
        change_summary TEXT NOT NULL DEFAULT '',
        status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
        parent_version_id VARCHAR(36),
        approved_at VARCHAR(64) NOT NULL DEFAULT '',
        approved_by VARCHAR(120) NOT NULL DEFAULT '',
        locked_at VARCHAR(64) NOT NULL DEFAULT '',
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_character_versions_profile ON character_versions (character_profile_id)",
    """
    CREATE TABLE IF NOT EXISTS character_reference_assets (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        character_profile_id VARCHAR(36) NOT NULL,
        character_version_id VARCHAR(36),
        asset_id VARCHAR(36) NOT NULL,
        reference_role VARCHAR(64) NOT NULL,
        view_angle VARCHAR(64) NOT NULL DEFAULT '',
        framing VARCHAR(64) NOT NULL DEFAULT '',
        approval_status VARCHAR(32) NOT NULL DEFAULT 'draft',
        canonical BOOLEAN NOT NULL DEFAULT 0,
        source_type VARCHAR(64) NOT NULL DEFAULT 'upload',
        generation_lineage_json TEXT NOT NULL DEFAULT '{}',
        notes TEXT NOT NULL DEFAULT '',
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_character_refs_profile ON character_reference_assets (character_profile_id)",
    "CREATE INDEX IF NOT EXISTS ix_character_refs_role ON character_reference_assets (reference_role)",
    """
    CREATE TABLE IF NOT EXISTS character_traits (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        character_profile_id VARCHAR(36) NOT NULL,
        character_version_id VARCHAR(36),
        category VARCHAR(64) NOT NULL DEFAULT '',
        key VARCHAR(120) NOT NULL DEFAULT '',
        value TEXT NOT NULL DEFAULT '',
        importance VARCHAR(32) NOT NULL DEFAULT 'canonical',
        canonical BOOLEAN NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS character_wardrobes (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        character_profile_id VARCHAR(36) NOT NULL,
        character_version_id VARCHAR(36),
        name VARCHAR(200) NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        approval_status VARCHAR(32) NOT NULL DEFAULT 'draft',
        materials TEXT NOT NULL DEFAULT '',
        colors TEXT NOT NULL DEFAULT '',
        footwear VARCHAR(200) NOT NULL DEFAULT '',
        jewelry TEXT NOT NULL DEFAULT '',
        accessories TEXT NOT NULL DEFAULT '',
        makeup_state VARCHAR(200) NOT NULL DEFAULT '',
        hair_state VARCHAR(200) NOT NULL DEFAULT '',
        continuity_rules TEXT NOT NULL DEFAULT '',
        reference_asset_ids_json TEXT NOT NULL DEFAULT '[]',
        scene_assignments_json TEXT NOT NULL DEFAULT '[]',
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        updated_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS character_props (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        character_profile_id VARCHAR(36) NOT NULL,
        character_version_id VARCHAR(36),
        name VARCHAR(200) NOT NULL DEFAULT '',
        prop_type VARCHAR(64) NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        materials TEXT NOT NULL DEFAULT '',
        colors TEXT NOT NULL DEFAULT '',
        placement VARCHAR(200) NOT NULL DEFAULT '',
        how_worn TEXT NOT NULL DEFAULT '',
        hand_assignment VARCHAR(64) NOT NULL DEFAULT '',
        usage_behavior TEXT NOT NULL DEFAULT '',
        continuity_rules TEXT NOT NULL DEFAULT '',
        library_asset_id VARCHAR(36),
        approval_status VARCHAR(32) NOT NULL DEFAULT 'draft',
        reference_asset_ids_json TEXT NOT NULL DEFAULT '[]',
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS voice_profiles (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        character_profile_id VARCHAR(36) NOT NULL,
        character_version_id VARCHAR(36),
        version_number INTEGER NOT NULL DEFAULT 1,
        name VARCHAR(200) NOT NULL DEFAULT '',
        source_mode VARCHAR(32) NOT NULL DEFAULT 'UNASSIGNED',
        provider VARCHAR(64) NOT NULL DEFAULT '',
        model_id VARCHAR(200) NOT NULL DEFAULT '',
        status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
        approval_status VARCHAR(32) NOT NULL DEFAULT 'draft',
        language VARCHAR(32) NOT NULL DEFAULT 'en',
        accent VARCHAR(64) NOT NULL DEFAULT '',
        perceived_age VARCHAR(64) NOT NULL DEFAULT '',
        pitch_description VARCHAR(120) NOT NULL DEFAULT '',
        pace_description VARCHAR(120) NOT NULL DEFAULT '',
        tone_description VARCHAR(120) NOT NULL DEFAULT '',
        resonance_description VARCHAR(120) NOT NULL DEFAULT '',
        warmth VARCHAR(64) NOT NULL DEFAULT '',
        breathiness VARCHAR(64) NOT NULL DEFAULT '',
        energy VARCHAR(64) NOT NULL DEFAULT '',
        emotional_range VARCHAR(120) NOT NULL DEFAULT '',
        pronunciation_notes TEXT NOT NULL DEFAULT '',
        voice_design_prompt TEXT NOT NULL DEFAULT '',
        reference_asset_id VARCHAR(36),
        reference_transcript TEXT NOT NULL DEFAULT '',
        approved_preview_asset_id VARCHAR(36),
        consent_record_id VARCHAR(36),
        candidate_asset_ids_json TEXT NOT NULL DEFAULT '[]',
        lineage_json TEXT NOT NULL DEFAULT '{}',
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        updated_at VARCHAR(64) NOT NULL DEFAULT '',
        approved_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_voice_profiles_character ON voice_profiles (character_profile_id)",
    """
    CREATE TABLE IF NOT EXISTS voice_consent_records (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        voice_profile_id VARCHAR(36) NOT NULL,
        source_owner_name VARCHAR(200) NOT NULL DEFAULT '',
        performer_name VARCHAR(200) NOT NULL DEFAULT '',
        authority_type VARCHAR(64) NOT NULL DEFAULT 'self',
        consent_confirmed BOOLEAN NOT NULL DEFAULT 0,
        commercial_use_allowed BOOLEAN NOT NULL DEFAULT 0,
        synthetic_generation_allowed BOOLEAN NOT NULL DEFAULT 0,
        project_scope VARCHAR(64) NOT NULL DEFAULT 'project',
        restriction_notes TEXT NOT NULL DEFAULT '',
        confirmation_timestamp VARCHAR(64) NOT NULL DEFAULT '',
        confirmed_by VARCHAR(120) NOT NULL DEFAULT ''
    )
    """,
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="M3.3 Character Identity foundation (profiles, versions, references, voice)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Drop character_profiles, character_versions, character_reference_assets, character_traits, character_wardrobes, character_props, voice_profiles, voice_consent_records.",
    reversible=False,
)
