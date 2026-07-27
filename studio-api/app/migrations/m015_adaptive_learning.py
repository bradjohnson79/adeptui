"""M015: Co-Director M2.12 Adaptive Learning tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M015"
CHECKSUM_SOURCE = "M015:adaptive-learning:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS m212_lessons (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        layer VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        title TEXT NOT NULL DEFAULT '',
        text TEXT NOT NULL,
        policy_json TEXT NOT NULL DEFAULT '{}',
        evidence_json TEXT NOT NULL DEFAULT '[]',
        confidence REAL NOT NULL DEFAULT 0.0,
        evidence_score REAL NOT NULL DEFAULT 0.0,
        mistake_class VARCHAR(64) NOT NULL DEFAULT '',
        source_signals_json TEXT NOT NULL DEFAULT '[]',
        regression_suite_id VARCHAR(64),
        regression_passed INTEGER NOT NULL DEFAULT 0,
        approval_json TEXT NOT NULL DEFAULT '{}',
        project_id VARCHAR(36),
        user_id VARCHAR(64),
        session_id VARCHAR(64),
        created_at DATETIME NOT NULL,
        promoted_at DATETIME,
        retired_at DATETIME,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m212_lessons_layer ON m212_lessons (layer)",
    "CREATE INDEX IF NOT EXISTS ix_m212_lessons_status ON m212_lessons (status)",
    "CREATE INDEX IF NOT EXISTS ix_m212_lessons_project_id ON m212_lessons (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_m212_lessons_mistake_class ON m212_lessons (mistake_class)",
    """
    CREATE TABLE IF NOT EXISTS m212_lesson_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        lesson_id VARCHAR(36) NOT NULL,
        version INTEGER NOT NULL,
        action VARCHAR(32) NOT NULL,
        actor VARCHAR(128) NOT NULL DEFAULT 'system',
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        note TEXT NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m212_lesson_versions_lesson_id ON m212_lesson_versions (lesson_id)",
    """
    CREATE TABLE IF NOT EXISTS m212_retrospectives (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        session_id VARCHAR(64),
        summary TEXT NOT NULL DEFAULT '',
        critique_json TEXT NOT NULL DEFAULT '{}',
        candidate_lesson_ids_json TEXT NOT NULL DEFAULT '[]',
        trace_id VARCHAR(36),
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m212_retrospectives_project_id ON m212_retrospectives (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m212_confidence_calibration (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36),
        predicted_confidence REAL NOT NULL,
        observed_outcome VARCHAR(32) NOT NULL,
        calibrated_confidence REAL,
        context_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m212_confidence_calibration_project_id ON m212_confidence_calibration (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m212_strategy_packs (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        name VARCHAR(128) NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        status VARCHAR(32) NOT NULL DEFAULT 'candidate',
        pack_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        activated_at DATETIME,
        retired_at DATETIME
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m212_strategy_packs_status ON m212_strategy_packs (status)",
)


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="Add M2.12 adaptive learning tables (lessons, versions, retrospectives, calibration, strategy)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Additive. Drop m212_* tables to reverse.",
    reversible=False,
)
