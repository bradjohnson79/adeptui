"""M033: Project-scoped typed reference aliases on scene_reference_bindings.

Adds:
- alias: unique per project (UI token without @/#/* prefix)
- media_kind: entity | image | video
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0033"
CHECKSUM_SOURCE = "M033:scene-reference-aliases-media-kind:v1"

_DDL = [
    "ALTER TABLE scene_reference_bindings ADD COLUMN alias VARCHAR(80)",
    "ALTER TABLE scene_reference_bindings ADD COLUMN media_kind VARCHAR(16)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_srb_project_alias ON scene_reference_bindings (project_id, alias)",
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
    description="Typed project-scoped reference aliases (alias + media_kind)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Leave alias/media_kind columns; SQLite cannot drop them easily.",
    reversible=False,
)
