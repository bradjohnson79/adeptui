"""M011: Immutable Production Context + job linkage (M2.7.1).

Revision numbering: `M011` follows M010 (M009 unused). Numeric `0110` sorts before M* and must not be used. M009 remains unused.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M011"
CHECKSUM_SOURCE = "M011:production-context:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS production_contexts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36) NOT NULL,
        context_json TEXT NOT NULL DEFAULT '{}',
        initiated_by VARCHAR(64),
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_contexts_project_id "
    "ON production_contexts (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_contexts_scene_id "
    "ON production_contexts (scene_id)",
    """
    CREATE TABLE IF NOT EXISTS production_context_extensions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        context_id VARCHAR(36) NOT NULL,
        extension_type VARCHAR(64) NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        actor VARCHAR(64) NOT NULL DEFAULT 'system',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(context_id) REFERENCES production_contexts (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_context_extensions_context_id "
    "ON production_context_extensions (context_id)",
)


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)

    columns = {
        row[1]
        for row in connection.exec_driver_sql("PRAGMA table_info(production_jobs)").fetchall()
    }
    if not columns:
        return
    if "production_context_id" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE production_jobs ADD COLUMN production_context_id VARCHAR(36)"
        )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_production_jobs_production_context_id "
        "ON production_jobs (production_context_id)"
    )


MIGRATION = Migration(
    revision=REVISION,
    description="Add production_contexts, extensions, and production_jobs.production_context_id",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Additive. Drop production_context_extensions and production_contexts; "
        "SQLite cannot drop production_context_id before 3.35 without table rebuild."
    ),
    reversible=False,
)