"""M014: Co-Director M2.11 Production Intelligence tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M014"
CHECKSUM_SOURCE = "M014:production-intelligence:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS m211_memory_items (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36),
        category VARCHAR(64) NOT NULL,
        content TEXT NOT NULL,
        tags_json TEXT NOT NULL DEFAULT '[]',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        version INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m211_memory_items_project_id ON m211_memory_items (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_m211_memory_items_scene_id ON m211_memory_items (scene_id)",
    "CREATE INDEX IF NOT EXISTS ix_m211_memory_items_category ON m211_memory_items (category)",
    """
    CREATE TABLE IF NOT EXISTS m211_decision_records (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36),
        category VARCHAR(64) NOT NULL,
        rationale TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.0,
        evidence_json TEXT NOT NULL DEFAULT '[]',
        bible_refs_json TEXT NOT NULL DEFAULT '[]',
        specialist_id VARCHAR(64) NOT NULL,
        approval_required INTEGER NOT NULL DEFAULT 0,
        approval_status VARCHAR(32) NOT NULL DEFAULT 'pending',
        recommendation TEXT NOT NULL DEFAULT '',
        explainability_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m211_decision_records_project_id ON m211_decision_records (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_m211_decision_records_scene_id ON m211_decision_records (scene_id)",
    "CREATE INDEX IF NOT EXISTS ix_m211_decision_records_specialist_id ON m211_decision_records (specialist_id)",
    "CREATE INDEX IF NOT EXISTS ix_m211_decision_records_approval_status ON m211_decision_records (approval_status)",
    """
    CREATE TABLE IF NOT EXISTS m211_execution_traces (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36),
        model_used VARCHAR(128) NOT NULL,
        specialist_graph_json TEXT NOT NULL DEFAULT '[]',
        brief TEXT NOT NULL DEFAULT '',
        status VARCHAR(32) NOT NULL,
        durations_json TEXT NOT NULL DEFAULT '{}',
        failures_json TEXT NOT NULL DEFAULT '[]',
        retries_json TEXT NOT NULL DEFAULT '[]',
        approvals_json TEXT NOT NULL DEFAULT '[]',
        stages_json TEXT NOT NULL DEFAULT '[]',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m211_execution_traces_project_id ON m211_execution_traces (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_m211_execution_traces_scene_id ON m211_execution_traces (scene_id)",
    "CREATE INDEX IF NOT EXISTS ix_m211_execution_traces_status ON m211_execution_traces (status)",
)



def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="Add M2.11 production intelligence tables (memory, decisions, traces)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Additive. Drop m211_* tables to reverse.",
    reversible=False,
)
