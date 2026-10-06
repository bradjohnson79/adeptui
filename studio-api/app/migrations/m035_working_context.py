"""M035: Persist Co-Director Working Context on the project row.

Sanitation Phase 1 — compact working-context-v1 JSON. Canonical stores remain
authoritative; this column is the shared chat/pipeline reference document.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0035"
CHECKSUM_SOURCE = "M035:working-context-v1"

_DDL_NOTE = "ALTER TABLE projects ADD COLUMN working_context_json TEXT NOT NULL DEFAULT ''"


def apply(connection: Connection) -> None:
    table_rows = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
    ).fetchall()
    if not table_rows:
        return
    cols = connection.exec_driver_sql("PRAGMA table_info(projects)").fetchall()
    names = {row[1] for row in cols}
    if "working_context_json" not in names:
        connection.exec_driver_sql(_DDL_NOTE)


MIGRATION = Migration(
    revision=REVISION,
    description="Persist Co-Director Working Context (working-context-v1)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Column working_context_json remains (additive).",
    reversible=False,
)
