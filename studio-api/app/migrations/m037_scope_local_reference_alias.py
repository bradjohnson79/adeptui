"""M037: Scope-local unique alias for scene_reference_bindings."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0037"
CHECKSUM_SOURCE = "M037:scope-local-reference-alias:v1"

_DDL = [
    "DROP INDEX IF EXISTS uq_srb_project_alias",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_srb_scope_alias
    ON scene_reference_bindings (project_id, scope_type, scope_id, alias)
    """,
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        try:
            connection.exec_driver_sql(stmt)
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "already exists" in msg:
                continue
            raise


MIGRATION = Migration(
    revision=REVISION,
    description="Scope-local unique aliases so the same @/#/% tag can exist on two scenes",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Restore uq_srb_project_alias if a project-wide alias collision must be enforced again.",
    reversible=False,
)
