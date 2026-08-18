"""M034: Project-scoped production event stream (Co-Director production orchestrator).

Adds the `production_events` table: a lightweight, append-only record of
production changes (spatial map, ERS, scene creator candidates, library,
timeline, jobs) so Co-Director can answer "what happened" — including
changes the user made manually. See docs/release-gate/codirector-production-orchestrator.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0034"
CHECKSUM_SOURCE = "M034:production-events:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS production_events (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        event_type VARCHAR(80) NOT NULL,
        actor VARCHAR(16) NOT NULL DEFAULT 'system',
        actor_detail VARCHAR(64) NOT NULL DEFAULT '',
        subject_kind VARCHAR(32) NOT NULL DEFAULT '',
        subject_id VARCHAR(64) NOT NULL DEFAULT '',
        summary VARCHAR(400) NOT NULL DEFAULT '',
        payload_json TEXT,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_events_project ON production_events (project_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_production_events_project_scene ON production_events (project_id, scene_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_production_events_type ON production_events (event_type)",
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        try:
            connection.exec_driver_sql(stmt)
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate" in msg:
                continue
            raise


MIGRATION = Migration(
    revision=REVISION,
    description="Project-scoped production event stream",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Drop table production_events (project-scoped; no cross-project data).",
    reversible=False,
)
