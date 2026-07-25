"""M007: Director 2.0 timeline reference bindings (COW versions + presets)."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M007"
CHECKSUM_SOURCE = "M007:timeline-reference-bindings:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS timeline_reference_sets (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36) NOT NULL,
        timeline_item_id VARCHAR(64) NOT NULL,
        active_version INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_timeline_reference_sets_project_id "
    "ON timeline_reference_sets (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_timeline_reference_sets_scene_id "
    "ON timeline_reference_sets (scene_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_timeline_reference_sets_item "
    "ON timeline_reference_sets (project_id, scene_id, timeline_item_id)",
    """
    CREATE TABLE IF NOT EXISTS timeline_reference_set_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        set_id VARCHAR(36) NOT NULL,
        version INTEGER NOT NULL,
        status VARCHAR(24) NOT NULL,
        created_at DATETIME NOT NULL,
        created_by VARCHAR(64),
        FOREIGN KEY(set_id) REFERENCES timeline_reference_sets (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_timeline_reference_set_versions_set_id "
    "ON timeline_reference_set_versions (set_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_timeline_reference_set_versions "
    "ON timeline_reference_set_versions (set_id, version)",
    """
    CREATE TABLE IF NOT EXISTS timeline_reference_bindings (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        version_id VARCHAR(36) NOT NULL,
        reference_asset_id VARCHAR(36) NOT NULL,
        role VARCHAR(64) NOT NULL,
        influence VARCHAR(32) NOT NULL,
        source VARCHAR(64) NOT NULL,
        bible_entity_stable_id VARCHAR(64),
        bible_version_id VARCHAR(64),
        source_timeline_item_id VARCHAR(64),
        label VARCHAR(200),
        notes TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(version_id) REFERENCES timeline_reference_set_versions (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_timeline_reference_bindings_version_id "
    "ON timeline_reference_bindings (version_id)",
    "CREATE INDEX IF NOT EXISTS ix_timeline_reference_bindings_asset "
    "ON timeline_reference_bindings (reference_asset_id)",
    """
    CREATE TABLE IF NOT EXISTS reference_presets (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        created_at DATETIME NOT NULL,
        created_by VARCHAR(64),
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_reference_presets_project_id "
    "ON reference_presets (project_id)",
    """
    CREATE TABLE IF NOT EXISTS reference_preset_bindings (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        preset_id VARCHAR(36) NOT NULL,
        reference_asset_id VARCHAR(36) NOT NULL,
        role VARCHAR(64) NOT NULL,
        influence VARCHAR(32) NOT NULL,
        source VARCHAR(64) NOT NULL,
        bible_entity_stable_id VARCHAR(64),
        bible_version_id VARCHAR(64),
        label VARCHAR(200),
        notes TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(preset_id) REFERENCES reference_presets (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_reference_preset_bindings_preset_id "
    "ON reference_preset_bindings (preset_id)",
)


def apply(connection: Connection) -> None:
    for statement in _DDL:
        connection.exec_driver_sql(statement)


MIGRATION = Migration(
    revision=REVISION,
    description="Add versioned timeline reference bindings and presets",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Additive-only. To roll back manually: DROP TABLE reference_preset_bindings; "
        "DROP TABLE reference_presets; DROP TABLE timeline_reference_bindings; "
        "DROP TABLE timeline_reference_set_versions; DROP TABLE timeline_reference_sets;"
    ),
    reversible=False,
)
