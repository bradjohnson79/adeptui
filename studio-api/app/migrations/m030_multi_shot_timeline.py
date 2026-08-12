"""M030: Multi-Shot → Timeline handoff lineage.

Adds a nullable ``timeline_batch_block_id`` column to ``multi_shots`` so each
approved shot can remember the W46 Timeline BatchBlock it was sent to. The column
is project-scoped through the existing ``project_id`` on the row, so the generic
project-deletion sweep continues to cover it.
Forward-only and non-destructive: only adds the column if it does not already
exist.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0030"
CHECKSUM_SOURCE = "M030:multi-shot-timeline-handoff:v1"


def apply(conn: Connection) -> None:
    rows = conn.exec_driver_sql("PRAGMA table_info(multi_shots)").fetchall()
    if not any(row[1] == "timeline_batch_block_id" for row in rows):
        conn.exec_driver_sql(
            "ALTER TABLE multi_shots ADD COLUMN timeline_batch_block_id VARCHAR(36)"
        )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_multi_shots_timeline_batch ON multi_shots (timeline_batch_block_id)"
    )


MIGRATION = Migration(
    revision=REVISION,
    description="Multi-Shot to Timeline handoff lineage column",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Column is nullable and only stores lineage. Rollback would require "
        "removing the column from multi_shots."
    ),
    reversible=False,
)
