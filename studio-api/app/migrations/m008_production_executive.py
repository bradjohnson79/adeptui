"""M008: Co-Director M2.7 Production Executive durable job orchestration tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M008"
CHECKSUM_SOURCE = "M008:production-executive:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS production_jobs (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        type VARCHAR(64) NOT NULL,
        owner VARCHAR(64) NOT NULL DEFAULT 'system',
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36),
        timeline_item_id VARCHAR(64),
        priority INTEGER NOT NULL DEFAULT 100,
        status VARCHAR(24) NOT NULL,
        capability_requirements_json TEXT NOT NULL DEFAULT '[]',
        payload_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT,
        error_message TEXT,
        idempotency_key VARCHAR(128),
        attempts_count INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        provider VARCHAR(64),
        blocked_reason TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        started_at DATETIME,
        completed_at DATETIME,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_jobs_project_id ON production_jobs (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_jobs_status ON production_jobs (status)",
    "CREATE INDEX IF NOT EXISTS ix_production_jobs_scene_id ON production_jobs (scene_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_jobs_priority_created "
    "ON production_jobs (status, priority, created_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_production_jobs_idempotency "
    "ON production_jobs (project_id, idempotency_key) "
    "WHERE idempotency_key IS NOT NULL",
    """
    CREATE TABLE IF NOT EXISTS production_job_attempts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL,
        attempt_n INTEGER NOT NULL,
        provider VARCHAR(64),
        started_at DATETIME NOT NULL,
        finished_at DATETIME,
        duration_ms INTEGER,
        errors_json TEXT NOT NULL DEFAULT '[]',
        capability_snapshot_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT,
        outcome VARCHAR(32) NOT NULL DEFAULT 'started',
        FOREIGN KEY(job_id) REFERENCES production_jobs (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_job_attempts_job_id "
    "ON production_job_attempts (job_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_production_job_attempts_n "
    "ON production_job_attempts (job_id, attempt_n)",
    """
    CREATE TABLE IF NOT EXISTS production_job_dependencies (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL,
        depends_on_job_id VARCHAR(36) NOT NULL,
        FOREIGN KEY(job_id) REFERENCES production_jobs (id),
        FOREIGN KEY(depends_on_job_id) REFERENCES production_jobs (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_job_dependencies_job_id "
    "ON production_job_dependencies (job_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_job_dependencies_depends "
    "ON production_job_dependencies (depends_on_job_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_production_job_dependencies "
    "ON production_job_dependencies (job_id, depends_on_job_id)",
    """
    CREATE TABLE IF NOT EXISTS production_job_events (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        job_id VARCHAR(36),
        project_id VARCHAR(36) NOT NULL,
        event_type VARCHAR(64) NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(job_id) REFERENCES production_jobs (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_job_events_job_id "
    "ON production_job_events (job_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_job_events_project_id "
    "ON production_job_events (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_job_events_type "
    "ON production_job_events (event_type)",
    """
    CREATE TABLE IF NOT EXISTS production_notifications (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        job_id VARCHAR(36),
        event_id VARCHAR(36),
        level VARCHAR(24) NOT NULL DEFAULT 'info',
        title VARCHAR(200) NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        read_flag INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(job_id) REFERENCES production_jobs (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_notifications_project_id "
    "ON production_notifications (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_notifications_read "
    "ON production_notifications (project_id, read_flag)",
    """
    CREATE TABLE IF NOT EXISTS production_job_audit (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        job_id VARCHAR(36) NOT NULL,
        from_status VARCHAR(24),
        to_status VARCHAR(24) NOT NULL,
        actor VARCHAR(64) NOT NULL DEFAULT 'system',
        reason TEXT NOT NULL DEFAULT '',
        detail_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(job_id) REFERENCES production_jobs (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_job_audit_job_id "
    "ON production_job_audit (job_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_job_audit_created "
    "ON production_job_audit (created_at)",
)


def apply(connection: Connection) -> None:
    for statement in _DDL:
        connection.exec_driver_sql(statement)


MIGRATION = Migration(
    revision=REVISION,
    description="Add Production Executive durable job orchestration tables",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Additive-only. To roll back manually: DROP TABLE production_job_audit; "
        "DROP TABLE production_notifications; DROP TABLE production_job_events; "
        "DROP TABLE production_job_dependencies; DROP TABLE production_job_attempts; "
        "DROP TABLE production_jobs;"
    ),
    reversible=False,
)
