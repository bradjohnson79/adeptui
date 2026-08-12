"""M024: M42 Wave 6P Scene Reference Binding tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0024"
CHECKSUM_SOURCE = "M024:m42-w6p-scene-references:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS scene_reference_bindings (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        schema_version INTEGER NOT NULL DEFAULT 1,
        project_id VARCHAR(36) NOT NULL,
        asset_id VARCHAR(36) NOT NULL,
        scope_type VARCHAR(32) NOT NULL,
        scope_id VARCHAR(64) NOT NULL,
        reference_type VARCHAR(32) NOT NULL,
        usage_modes_json TEXT NOT NULL DEFAULT '[]',
        reference_roles_json TEXT NOT NULL DEFAULT '[]',
        identity_id VARCHAR(36),
        identity_version_id VARCHAR(36),
        variant_ids_json TEXT,
        enabled BOOLEAN NOT NULL DEFAULT 1,
        order_index INTEGER NOT NULL DEFAULT 0,
        requested_weight FLOAT,
        notes TEXT,
        created_by VARCHAR(64) NOT NULL DEFAULT 'system',
        updated_by VARCHAR(64) NOT NULL DEFAULT 'system',
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME,
        FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
        FOREIGN KEY(asset_id) REFERENCES assets (id) ON DELETE CASCADE,
        CONSTRAINT uq_srb_scope_asset_type UNIQUE (project_id, scope_type, scope_id, asset_id, reference_type)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_srb_project_scope ON scene_reference_bindings (project_id, scope_type, scope_id)",
    "CREATE INDEX IF NOT EXISTS ix_srb_asset ON scene_reference_bindings (asset_id)",
    "CREATE INDEX IF NOT EXISTS ix_srb_project ON scene_reference_bindings (project_id)",
    """
    CREATE TABLE IF NOT EXISTS scene_reference_audit_events (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        binding_id VARCHAR(36),
        event_type VARCHAR(64) NOT NULL,
        actor VARCHAR(64) NOT NULL DEFAULT 'system',
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_srb_audit_project ON scene_reference_audit_events (project_id)",
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="M42 Wave 6P Scene Reference Binding tables",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Drop scene_reference_bindings and scene_reference_audit_events.",
    reversible=False,
)
