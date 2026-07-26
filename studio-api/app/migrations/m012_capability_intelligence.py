"""M012: Co-Director M2.8 Capability Intelligence tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M012"
CHECKSUM_SOURCE = "M012:capability-intelligence:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS m28_model_entries (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        source VARCHAR(32) NOT NULL,
        source_key VARCHAR(256) NOT NULL,
        display_name VARCHAR(256) NOT NULL,
        classification VARCHAR(64) NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_m28_model_entries_source_key "
    "ON m28_model_entries (source, source_key)",
    """
    CREATE TABLE IF NOT EXISTS m28_watchlist (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        entry_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36),
        created_at DATETIME NOT NULL,
        FOREIGN KEY(entry_id) REFERENCES m28_model_entries (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m28_watchlist_entry_id ON m28_watchlist (entry_id)",
    """
    CREATE TABLE IF NOT EXISTS m28_compat_evals (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        entry_id VARCHAR(36) NOT NULL,
        verdict VARCHAR(64) NOT NULL,
        reasons_json TEXT NOT NULL DEFAULT '[]',
        env_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(entry_id) REFERENCES m28_model_entries (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m28_compat_evals_entry_id ON m28_compat_evals (entry_id)",
    """
    CREATE TABLE IF NOT EXISTS m28_sandbox_instances (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        status VARCHAR(64) NOT NULL,
        config_json TEXT NOT NULL DEFAULT '{}',
        port INTEGER,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m28_sandbox_plans (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        sandbox_id VARCHAR(36) NOT NULL,
        plan_json TEXT NOT NULL DEFAULT '{}',
        status VARCHAR(32) NOT NULL DEFAULT 'pending',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(sandbox_id) REFERENCES m28_sandbox_instances (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m28_sandbox_plans_sandbox_id ON m28_sandbox_plans (sandbox_id)",
    """
    CREATE TABLE IF NOT EXISTS m28_sandbox_validations (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        sandbox_id VARCHAR(36) NOT NULL,
        result_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(sandbox_id) REFERENCES m28_sandbox_instances (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m28_promotion_manifests (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        sandbox_id VARCHAR(36) NOT NULL,
        manifest_json TEXT NOT NULL DEFAULT '{}',
        status VARCHAR(32) NOT NULL DEFAULT 'pending',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(sandbox_id) REFERENCES m28_sandbox_instances (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m28_shot_profiles (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        name VARCHAR(200) NOT NULL,
        active_version_id VARCHAR(36),
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m28_shot_profiles_project_id ON m28_shot_profiles (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m28_shot_profile_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        profile_id VARCHAR(36) NOT NULL,
        version INTEGER NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(profile_id) REFERENCES m28_shot_profiles (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m28_shot_profile_versions_profile_id "
    "ON m28_shot_profile_versions (profile_id)",
    """
    CREATE TABLE IF NOT EXISTS m28_recipes (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        name VARCHAR(200) NOT NULL,
        status VARCHAR(64) NOT NULL,
        manifest_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m28_recipes_project_id ON m28_recipes (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m28_recipe_stages (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        recipe_id VARCHAR(36) NOT NULL,
        stage_index INTEGER NOT NULL,
        job_id VARCHAR(36),
        status VARCHAR(64) NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY(recipe_id) REFERENCES m28_recipes (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m28_recipe_stages_recipe_id ON m28_recipe_stages (recipe_id)",
    """
    CREATE TABLE IF NOT EXISTS m28_virtual_stages (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36),
        name VARCHAR(200) NOT NULL DEFAULT 'Stage',
        camera_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m28_virtual_stages_project_id ON m28_virtual_stages (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m28_location_spins (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        plan_json TEXT NOT NULL DEFAULT '{}',
        coverage_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
)


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="Add M2.8 capability intelligence tables (radar, sandbox, recipes, shot profiles)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Additive. Drop m28_* tables to reverse.",
    reversible=False,
)
