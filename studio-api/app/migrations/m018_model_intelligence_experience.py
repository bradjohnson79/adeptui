"""M018: M3.0e Model Intelligence generation experience table."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0018"
CHECKSUM_SOURCE = "M018:model-intelligence-experience:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS m30e_generation_experience (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        model_id VARCHAR(64) NOT NULL,
        model_version VARCHAR(64) NOT NULL DEFAULT '',
        provider_id VARCHAR(64) NOT NULL DEFAULT '',
        knowledge_pack_version VARCHAR(64) NOT NULL DEFAULT '',
        project_id VARCHAR(36),
        scene_id VARCHAR(64),
        shot_id VARCHAR(64),
        request_type VARCHAR(64) NOT NULL DEFAULT '',
        compiled_rule_ids_json TEXT NOT NULL DEFAULT '[]',
        parameter_summary_json TEXT NOT NULL DEFAULT '{}',
        generation_status VARCHAR(64) NOT NULL DEFAULT '',
        user_accepted INTEGER,
        user_rejected INTEGER,
        revision_requested INTEGER,
        vision_score REAL,
        continuity_score REAL,
        failure_codes_json TEXT NOT NULL DEFAULT '[]',
        generation_time_ms INTEGER,
        estimated_cost VARCHAR(128),
        actual_cost VARCHAR(128),
        user_feedback TEXT NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m30e_exp_model ON m30e_generation_experience (model_id)",
    "CREATE INDEX IF NOT EXISTS ix_m30e_exp_project ON m30e_generation_experience (project_id)",
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="M3.0e model intelligence generation experience",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="DROP TABLE m30e_generation_experience",
    reversible=True,
)
