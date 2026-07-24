"""Production Systems Readiness: add `scenes.summary`.

A scene could carry a name, a prompt, and a camera note, but nothing that reads as a short
human- or agent-facing description of what happens in it. Co-Director needs that summary to
reason about a timeline without ingesting every full prompt, so it becomes a first-class
column rather than another JSON blob.

Additive and idempotent: the column is only added when absent, so the migration is safe on a
database already provisioned by `app.db.init_db()`.

It is also a no-op on a database that has no `scenes` table at all. Core table creation is
still owned by `init_db()` (see `m001_initial.py`), so the runner can legitimately execute
against a bare file — in that case `init_db()` creates `scenes` with `summary` already on it
and there is nothing for this migration to alter.

Revision numbering: `M010` deliberately skips ahead of `M002` to stay out of the way of
Co-Director M2.2, which is claiming the `M003+` range on another branch.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M010"
CHECKSUM_SOURCE = "M010:scene-summary:v1"


def apply(connection: Connection) -> None:
    columns = {
        row[1] for row in connection.exec_driver_sql("PRAGMA table_info(scenes)").fetchall()
    }
    if not columns:
        return
    if "summary" not in columns:
        connection.exec_driver_sql("ALTER TABLE scenes ADD COLUMN summary TEXT DEFAULT ''")


MIGRATION = Migration(
    revision=REVISION,
    description="Add scenes.summary for short scene descriptions",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Additive and nullable. SQLite cannot drop a column before 3.35; to roll back, "
        "recreate `scenes` without `summary` and copy rows across. No code requires the "
        "column to be non-empty."
    ),
    reversible=False,
)
