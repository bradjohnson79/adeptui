"""M022: Wave 4 durable production plan versions, events, idempotency."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0022"
CHECKSUM_SOURCE = "M022:durable-production-plans:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS codirector_production_plan_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        plan_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        state VARCHAR(24) NOT NULL DEFAULT 'draft',
        snapshot_json TEXT,
        revision_reason TEXT,
        parent_version_id VARCHAR(64),
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_plan_versions_plan_id ON codirector_production_plan_versions (plan_id)",
    "CREATE INDEX IF NOT EXISTS ix_plan_versions_project_id ON codirector_production_plan_versions (project_id)",
    """
    CREATE TABLE IF NOT EXISTS codirector_production_plan_events (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        plan_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        plan_version INTEGER NOT NULL DEFAULT 1,
        event_type VARCHAR(64) NOT NULL,
        actor_type VARCHAR(24) NOT NULL DEFAULT 'system',
        actor_id VARCHAR(64),
        request_id VARCHAR(64) NOT NULL DEFAULT '',
        summary TEXT,
        changes_json TEXT,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_plan_events_plan_id ON codirector_production_plan_events (plan_id)",
    "CREATE INDEX IF NOT EXISTS ix_plan_events_project_id ON codirector_production_plan_events (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_plan_events_request_id ON codirector_production_plan_events (request_id)",
    "CREATE INDEX IF NOT EXISTS ix_plan_events_type ON codirector_production_plan_events (event_type)",
    """
    CREATE TABLE IF NOT EXISTS codirector_plan_command_idempotency (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        request_id VARCHAR(64) NOT NULL,
        command VARCHAR(64) NOT NULL DEFAULT '',
        plan_id VARCHAR(36),
        result_json TEXT,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_plan_idem_project ON codirector_plan_command_idempotency (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_plan_idem_request ON codirector_plan_command_idempotency (request_id)",
]


def _column_names(conn: Connection, table: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _add_col(conn: Connection, table: str, name: str, ddl: str) -> None:
    cols = _column_names(conn, table)
    if not cols:
        return
    if name not in cols:
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def apply(conn: Connection) -> None:
    for stmt in _DDL:
        conn.exec_driver_sql(stmt)
    # Extend plan head
    _add_col(conn, "codirector_production_plans", "version", "version INTEGER DEFAULT 1")
    _add_col(conn, "codirector_production_plans", "conversation_id", "conversation_id VARCHAR(64)")
    _add_col(conn, "codirector_production_plans", "active_step_id", "active_step_id VARCHAR(64)")
    _add_col(conn, "codirector_production_plans", "parent_version_id", "parent_version_id VARCHAR(64)")
    _add_col(conn, "codirector_production_plans", "revision_reason", "revision_reason TEXT")
    _add_col(conn, "codirector_production_plans", "paused_at", "paused_at DATETIME")
    _add_col(conn, "codirector_production_plans", "resumed_at", "resumed_at DATETIME")
    _add_col(conn, "codirector_production_plans", "cancelled_at", "cancelled_at DATETIME")
    _add_col(conn, "codirector_production_plans", "archived_at", "archived_at DATETIME")
    _add_col(conn, "codirector_production_plans", "completed_at", "completed_at DATETIME")


MIGRATION = Migration(
    revision=REVISION,
    description="Wave 4 durable production plan versions, events, and idempotency",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Drop Wave 4 plan auxiliary tables and ignore new plan head columns.",
    reversible=False,
)
