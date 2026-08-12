"""M020: M3.1a Templates & Presets foundation + Project Types columns.

Additive tables for the unified creative-items layer, production units, and
custom project-type definitions. Also backfills ``projects.primary_project_type``
from legacy UI ``defaults_json.production_type`` / ``tags_json`` labels.

``defaults_json.production_type`` is intentionally left in place (deprecated soft
metadata) so older clients keep reading until M3.1i dual-read ends.
"""

from __future__ import annotations

import json

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0020"
CHECKSUM_SOURCE = "M020:templates-presets-foundation:v1"

# Legacy UI ProductionType labels → canonical project-type slugs.
LEGACY_PRODUCTION_TYPE_MAP: dict[str, str] = {
    "short film": "short_film",
    "feature film": "feature_film",
    "series episode": "television_episodic",
    "commercial": "commercial",
    "music video": "music_video",
    "social video": "social_media",
    "animation": "animation",
    "custom": "custom",
}

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS creative_items (
        id VARCHAR(64) NOT NULL PRIMARY KEY,
        kind VARCHAR(64) NOT NULL,
        category VARCHAR(64) NOT NULL DEFAULT '',
        subcategory VARCHAR(64) NOT NULL DEFAULT '',
        scope VARCHAR(32) NOT NULL,
        owner_user_id VARCHAR(64),
        project_id VARCHAR(36),
        scene_id VARCHAR(36),
        shot_ref VARCHAR(128),
        name VARCHAR(200) NOT NULL,
        slug VARCHAR(200) NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        intent_json TEXT NOT NULL DEFAULT '{}',
        provider_mappings_json TEXT NOT NULL DEFAULT '{}',
        compatibility_json TEXT NOT NULL DEFAULT '{}',
        lifecycle VARCHAR(32) NOT NULL DEFAULT 'draft',
        approval_state VARCHAR(32) NOT NULL DEFAULT 'draft',
        active_version_id VARCHAR(64),
        parent_item_id VARCHAR(64),
        origin VARCHAR(32) NOT NULL DEFAULT 'local',
        visibility VARCHAR(32) NOT NULL DEFAULT 'private',
        share_slug VARCHAR(200),
        library_system_key VARCHAR(128) NOT NULL DEFAULT '',
        tags_json TEXT NOT NULL DEFAULT '[]',
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_creative_items_project ON creative_items (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_creative_items_kind ON creative_items (kind)",
    "CREATE INDEX IF NOT EXISTS ix_creative_items_scope ON creative_items (scope)",
    "CREATE INDEX IF NOT EXISTS ix_creative_items_slug ON creative_items (slug)",
    """
    CREATE TABLE IF NOT EXISTS creative_item_versions (
        id VARCHAR(64) NOT NULL PRIMARY KEY,
        item_id VARCHAR(64) NOT NULL,
        version INTEGER NOT NULL,
        intent_json TEXT NOT NULL DEFAULT '{}',
        provider_mappings_json TEXT NOT NULL DEFAULT '{}',
        compatibility_json TEXT NOT NULL DEFAULT '{}',
        changelog TEXT NOT NULL DEFAULT '',
        created_at DATETIME,
        created_by VARCHAR(64)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_creative_item_versions_item ON creative_item_versions (item_id)",
    """
    CREATE TABLE IF NOT EXISTS creative_bindings (
        id VARCHAR(64) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scope_level VARCHAR(32) NOT NULL,
        scene_id VARCHAR(36),
        shot_ref VARCHAR(128),
        slot VARCHAR(64) NOT NULL,
        item_id VARCHAR(64) NOT NULL,
        version_pin INTEGER,
        mode VARCHAR(32) NOT NULL DEFAULT 'override',
        expected_version INTEGER,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_creative_bindings_project ON creative_bindings (project_id)",
    """
    CREATE TABLE IF NOT EXISTS project_type_definitions (
        id VARCHAR(64) NOT NULL PRIMARY KEY,
        slug VARCHAR(128) NOT NULL UNIQUE,
        display_name VARCHAR(200) NOT NULL,
        group_name VARCHAR(64) NOT NULL DEFAULT '',
        is_builtin INTEGER NOT NULL DEFAULT 0,
        parent_selector VARCHAR(128),
        profile_json TEXT NOT NULL DEFAULT '{}',
        version INTEGER NOT NULL DEFAULT 1,
        lifecycle VARCHAR(32) NOT NULL DEFAULT 'approved',
        origin VARCHAR(32) NOT NULL DEFAULT 'local',
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_project_type_definitions_slug ON project_type_definitions (slug)",
    """
    CREATE TABLE IF NOT EXISTS production_units (
        id VARCHAR(64) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        kind VARCHAR(32) NOT NULL,
        parent_id VARCHAR(64),
        name VARCHAR(200) NOT NULL,
        unit_index INTEGER NOT NULL DEFAULT 0,
        meta_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_units_project ON production_units (project_id)",
]


def _table_columns(connection: Connection, table: str) -> set[str]:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(connection: Connection, table: str, column: str, ddl: str) -> None:
    cols = _table_columns(connection, table)
    if not cols:
        return
    if column not in cols:
        connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _legacy_slug_from_project_row(defaults_raw: str | None, tags_raw: str | None) -> str:
    label = ""
    try:
        defaults = json.loads(defaults_raw or "") if defaults_raw else {}
    except Exception:
        defaults = {}
    if isinstance(defaults, dict):
        label = str(defaults.get("production_type") or "").strip()
    if not label:
        try:
            tags = json.loads(tags_raw or "[]")
        except Exception:
            tags = []
        if isinstance(tags, list) and tags:
            label = str(tags[0] or "").strip()
    if not label:
        return "custom"
    return LEGACY_PRODUCTION_TYPE_MAP.get(label.lower(), "custom")


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)

    _add_column_if_missing(
        connection, "projects", "primary_project_type",
        "primary_project_type VARCHAR(128) DEFAULT 'custom'",
    )
    _add_column_if_missing(
        connection, "projects", "project_traits_json",
        "project_traits_json TEXT DEFAULT '[]'",
    )
    _add_column_if_missing(
        connection, "projects", "resolved_profile_json",
        "resolved_profile_json TEXT DEFAULT '{}'",
    )
    _add_column_if_missing(
        connection, "projects", "project_type_version",
        "project_type_version INTEGER DEFAULT 1",
    )
    _add_column_if_missing(
        connection, "scenes", "production_unit_id",
        "production_unit_id VARCHAR(64)",
    )

    project_cols = _table_columns(connection, "projects")
    if not project_cols:
        return
    if "primary_project_type" not in project_cols:
        return

    rows = connection.exec_driver_sql(
        "SELECT id, defaults_json, tags_json FROM projects"
    ).fetchall()
    for row in rows:
        project_id, defaults_json, tags_json = row[0], row[1], row[2]
        slug = _legacy_slug_from_project_row(defaults_json, tags_json)
        connection.exec_driver_sql(
            "UPDATE projects SET primary_project_type = ?, "
            "project_traits_json = COALESCE(NULLIF(project_traits_json, ''), '[]'), "
            "resolved_profile_json = COALESCE(NULLIF(resolved_profile_json, ''), '{}'), "
            "project_type_version = COALESCE(project_type_version, 1) "
            "WHERE id = ?",
            (slug, project_id),
        )


MIGRATION = Migration(
    revision=REVISION,
    description="M3.1a templates/presets foundation tables and project type columns",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Drop creative_items, creative_item_versions, creative_bindings, "
        "project_type_definitions, production_units; remove added project/scene columns."
    ),
    reversible=True,
)
