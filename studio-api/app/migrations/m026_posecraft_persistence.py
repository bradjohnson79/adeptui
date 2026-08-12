"""M026: PoseCraft production persistence — project-scoped scene document + revision history."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0026"
CHECKSUM_SOURCE = "M026:posecraft-persistence:v1"

_DDL = [
    # Revision history for PoseCraft scenes (one row per saved milestone).
    """
    CREATE TABLE IF NOT EXISTS posecraft_revisions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        revision INTEGER NOT NULL,
        label VARCHAR(200) NOT NULL DEFAULT '',
        scene_json TEXT NOT NULL DEFAULT '{}',
        creator_modified BOOLEAN NOT NULL DEFAULT 0,
        saved_by VARCHAR(64) NOT NULL DEFAULT 'creator',
        created_at DATETIME,
        FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_posecraft_revisions_project ON posecraft_revisions (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_posecraft_revisions_project_rev ON posecraft_revisions (project_id, revision)",
]


def apply(connection: Connection) -> None:
    # Add the live-document column to projects (SQLite-safe additive ALTER).
    # The ``projects`` table is provisioned by ``Base.metadata.create_all`` (the
    # SQLAlchemy model path), not by a migration. On a fresh engine that runs the
    # migration runner WITHOUT ``create_all`` first (the migration-only test path,
    # and any deployment that provisions schema purely via migrations), ``projects``
    # does not exist yet, so the ALTER must be skipped rather than crash the whole
    # run. ``create_all`` later creates ``projects`` with this column already
    # present (the model declares it), so skipping is non-destructive and additive.
    table_rows = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
    ).fetchall()
    if not table_rows:
        for stmt in _DDL:
            connection.exec_driver_sql(stmt)
        return
    cols = connection.exec_driver_sql("PRAGMA table_info(projects)").fetchall()
    names = {row[1] for row in cols}
    if "posecraft_document_json" not in names:
        connection.exec_driver_sql(
            "ALTER TABLE projects ADD COLUMN posecraft_document_json TEXT NOT NULL DEFAULT ''"
        )
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="PoseCraft production persistence (project-scoped document + revisions)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Drop posecraft_revisions; column posecraft_document_json remains (additive).",
    reversible=False,
)
