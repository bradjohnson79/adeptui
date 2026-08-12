"""M023: M42 Wave 5 Identity and Visual Continuity tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0023"
CHECKSUM_SOURCE = "M023:m42-w5-continuity-identity:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS continuity_policies (
        project_id VARCHAR(36) NOT NULL PRIMARY KEY,
        continuity_policy_schema_version INTEGER NOT NULL DEFAULT 1,
        enabled BOOLEAN NOT NULL DEFAULT 0,
        preflight_mode VARCHAR(32) NOT NULL DEFAULT 'off',
        evaluation_mode VARCHAR(32) NOT NULL DEFAULT 'manual',
        production_master_requires_decision BOOLEAN NOT NULL DEFAULT 0,
        critical_severity_behavior VARCHAR(32) NOT NULL DEFAULT 'warn',
        default_evaluator_key VARCHAR(120) NOT NULL DEFAULT 'continuity.rule_based_v1',
        updated_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS visual_identities (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        visual_identity_schema_version INTEGER NOT NULL DEFAULT 1,
        identity_type VARCHAR(64) NOT NULL DEFAULT 'character',
        canonical_name VARCHAR(200) NOT NULL DEFAULT '',
        display_name VARCHAR(200) NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        status VARCHAR(32) NOT NULL DEFAULT 'draft',
        active_version_id VARCHAR(36),
        production_version_id VARCHAR(36),
        character_profile_id VARCHAR(36),
        bible_entity_stable_id VARCHAR(120),
        archived BOOLEAN NOT NULL DEFAULT 0,
        created_by VARCHAR(120) NOT NULL DEFAULT '',
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        updated_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_visual_identities_project ON visual_identities (project_id)",
    """
    CREATE TABLE IF NOT EXISTS identity_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        identity_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        version_number INTEGER NOT NULL DEFAULT 1,
        parent_version_id VARCHAR(36),
        label VARCHAR(200) NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        identity_trait_schema_version INTEGER NOT NULL DEFAULT 1,
        traits_json TEXT NOT NULL DEFAULT '{}',
        constraint_ids_json TEXT NOT NULL DEFAULT '[]',
        reference_set_id VARCHAR(36),
        status VARCHAR(32) NOT NULL DEFAULT 'draft',
        archived BOOLEAN NOT NULL DEFAULT 0,
        created_by VARCHAR(120) NOT NULL DEFAULT '',
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        approved_by VARCHAR(120),
        approved_at VARCHAR(64)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_identity_versions_identity ON identity_versions (identity_id)",
    """
    CREATE TABLE IF NOT EXISTS identity_variants (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        identity_id VARCHAR(36) NOT NULL,
        identity_version_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        variant_type VARCHAR(64) NOT NULL DEFAULT 'custom',
        name VARCHAR(200) NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        trait_overrides_json TEXT NOT NULL DEFAULT '{}',
        locked_traits_json TEXT NOT NULL DEFAULT '[]',
        reference_set_id VARCHAR(36),
        status VARCHAR(32) NOT NULL DEFAULT 'draft',
        archived BOOLEAN NOT NULL DEFAULT 0,
        created_by VARCHAR(120) NOT NULL DEFAULT '',
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS approved_references (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        identity_id VARCHAR(36) NOT NULL,
        identity_version_id VARCHAR(36) NOT NULL,
        variant_id VARCHAR(36),
        asset_id VARCHAR(36) NOT NULL,
        reference_role_schema_version INTEGER NOT NULL DEFAULT 1,
        roles_json TEXT NOT NULL DEFAULT '[]',
        approval_status VARCHAR(32) NOT NULL DEFAULT 'candidate',
        quality_status VARCHAR(64) NOT NULL DEFAULT 'unknown',
        crop_metadata_json TEXT NOT NULL DEFAULT '{}',
        view_metadata_json TEXT NOT NULL DEFAULT '{}',
        notes TEXT NOT NULL DEFAULT '',
        archived BOOLEAN NOT NULL DEFAULT 0,
        created_by VARCHAR(120) NOT NULL DEFAULT '',
        approved_by VARCHAR(120),
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        approved_at VARCHAR(64),
        revoked_at VARCHAR(64),
        revoked_by VARCHAR(120),
        revoke_reason TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_approved_refs_project ON approved_references (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_approved_refs_asset ON approved_references (asset_id)",
    """
    CREATE TABLE IF NOT EXISTS continuity_constraints (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        identity_id VARCHAR(36) NOT NULL,
        identity_version_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        variant_id VARCHAR(36),
        continuity_constraint_schema_version INTEGER NOT NULL DEFAULT 1,
        dimension VARCHAR(64) NOT NULL DEFAULT '',
        policy VARCHAR(64) NOT NULL DEFAULT 'prefer',
        severity VARCHAR(32) NOT NULL DEFAULT 'minor',
        expected_value_json TEXT NOT NULL DEFAULT 'null',
        tolerance_json TEXT NOT NULL DEFAULT 'null',
        evaluator_key VARCHAR(120),
        user_description TEXT NOT NULL DEFAULT '',
        enabled BOOLEAN NOT NULL DEFAULT 1,
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS continuity_packets (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        request_id VARCHAR(120) NOT NULL,
        continuity_packet_schema_version INTEGER NOT NULL DEFAULT 1,
        bindings_json TEXT NOT NULL DEFAULT '[]',
        workflow_capability_statement_json TEXT NOT NULL DEFAULT '{}',
        resolver_version VARCHAR(120) NOT NULL DEFAULT '',
        compiler_version VARCHAR(120) NOT NULL DEFAULT '',
        frozen BOOLEAN NOT NULL DEFAULT 1,
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS continuity_evaluations (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        asset_id VARCHAR(36) NOT NULL,
        packet_id VARCHAR(36) NOT NULL,
        continuity_evaluation_schema_version INTEGER NOT NULL DEFAULT 1,
        evaluator_key VARCHAR(120) NOT NULL DEFAULT '',
        evaluator_version VARCHAR(64) NOT NULL DEFAULT '',
        overall_score FLOAT,
        overall_status VARCHAR(32) NOT NULL DEFAULT 'not_assessable',
        dimensions_json TEXT NOT NULL DEFAULT '[]',
        requires_human_review BOOLEAN NOT NULL DEFAULT 1,
        marked_for_review BOOLEAN NOT NULL DEFAULT 0,
        mark_reason TEXT NOT NULL DEFAULT '',
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS continuity_reviews (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        evaluation_id VARCHAR(36) NOT NULL,
        asset_id VARCHAR(36) NOT NULL,
        review_decision_schema_version INTEGER NOT NULL DEFAULT 1,
        decision VARCHAR(64) NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        previous_decision VARCHAR(64),
        reviewer VARCHAR(120) NOT NULL DEFAULT '',
        correction_id VARCHAR(36),
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS continuity_issues (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        issue_type VARCHAR(64) NOT NULL DEFAULT '',
        severity VARCHAR(32) NOT NULL DEFAULT 'major',
        status VARCHAR(32) NOT NULL DEFAULT 'open',
        title VARCHAR(300) NOT NULL DEFAULT '',
        detail_json TEXT NOT NULL DEFAULT '{}',
        identity_ids_json TEXT NOT NULL DEFAULT '[]',
        asset_ids_json TEXT NOT NULL DEFAULT '[]',
        packet_ids_json TEXT NOT NULL DEFAULT '[]',
        evaluation_ids_json TEXT NOT NULL DEFAULT '[]',
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        resolved_at VARCHAR(64)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS continuity_corrections (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        source_asset_id VARCHAR(36) NOT NULL,
        packet_id VARCHAR(36),
        evaluation_id VARCHAR(36),
        issue_ids_json TEXT NOT NULL DEFAULT '[]',
        status VARCHAR(32) NOT NULL DEFAULT 'proposed',
        certified BOOLEAN NOT NULL DEFAULT 0,
        workflow_key VARCHAR(120) NOT NULL DEFAULT '',
        image_edit_intent_json TEXT NOT NULL DEFAULT '{}',
        job_id VARCHAR(36),
        derived_asset_id VARCHAR(36),
        created_by VARCHAR(120) NOT NULL DEFAULT '',
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        enqueued_at VARCHAR(64)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS continuity_history (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        event_type VARCHAR(64) NOT NULL DEFAULT '',
        entity_type VARCHAR(64) NOT NULL DEFAULT '',
        entity_id VARCHAR(36) NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL DEFAULT '{}',
        actor VARCHAR(120) NOT NULL DEFAULT '',
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="M42 Wave 5 Identity Registry and Continuity domain tables",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Drop continuity_* and visual_identities / identity_* / approved_references tables.",
    reversible=False,
)
