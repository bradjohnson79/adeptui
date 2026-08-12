"""M032: Project-scoped trait store for Co-Director execution packs.

Introduces the ``project_traits`` table — a generic project-scoped JSON trait
store mirroring the character-scoped ``character_traits`` table. The Co-Director
execution pack store persists ``ExecutionPlan`` packs here under
``category = "execution_pack"`` and ``key = execution_id`` (see
``codirector/execution/pack_store.py``).

Reuses the same trait-store pattern as the visual_sheet pack
(``character_identity/visual_sheet.py:_save_pack``) so there is one storage
mechanism for pack-like state — just project-scoped instead of character-scoped.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0032"
CHECKSUM_SOURCE = "M032:project-traits-execution-pack-store:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS project_traits (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        category VARCHAR(64) NOT NULL DEFAULT '',
        key VARCHAR(160) NOT NULL DEFAULT '',
        value TEXT NOT NULL DEFAULT '',
        provenance VARCHAR(64) NOT NULL DEFAULT 'CODEX_EXECUTION_DISPATCHER',
        created_at VARCHAR(64) NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_project_traits_project ON project_traits (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_project_traits_category ON project_traits (category)",
    "CREATE INDEX IF NOT EXISTS ix_project_traits_key ON project_traits (key)",
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="Project-scoped trait store for Co-Director execution packs",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Drop project_traits.",
    reversible=False,
)
