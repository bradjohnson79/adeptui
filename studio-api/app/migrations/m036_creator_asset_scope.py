"""M036: Canonical isGlobal scope for Character / Prop / Environment."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0036"
CHECKSUM_SOURCE = "M036:creator-asset-scope-is-global:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS creator_asset_scope (
        entity_type VARCHAR(32) NOT NULL,
        entity_id VARCHAR(64) NOT NULL,
        owning_project_id VARCHAR(36) NOT NULL,
        is_global BOOLEAN NOT NULL DEFAULT 0,
        tag VARCHAR(200) NOT NULL DEFAULT '',
        name VARCHAR(200) NOT NULL DEFAULT '',
        identity_asset_id VARCHAR(36) NOT NULL DEFAULT '',
        created_at VARCHAR(64) NOT NULL DEFAULT '',
        updated_at VARCHAR(64) NOT NULL DEFAULT '',
        PRIMARY KEY (entity_type, entity_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_creator_asset_scope_owner ON creator_asset_scope (owning_project_id)",
    "CREATE INDEX IF NOT EXISTS ix_creator_asset_scope_global ON creator_asset_scope (entity_type, is_global)",
    "CREATE INDEX IF NOT EXISTS ix_creator_asset_scope_tag ON creator_asset_scope (entity_type, tag)",
    "CREATE INDEX IF NOT EXISTS ix_creator_asset_scope_identity ON creator_asset_scope (identity_asset_id)",
    "ALTER TABLE character_profiles ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT 0",
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        try:
            connection.exec_driver_sql(stmt)
        except Exception as e:
            msg = str(e).lower()
            if "duplicate column" in msg or "already exists" in msg:
                continue
            raise


MIGRATION = Migration(
    revision=REVISION,
    description="Global creator-asset scope (is_global + query index)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Leave creator_asset_scope and character_profiles.is_global; SQLite cannot drop easily.",
    reversible=False,
)
