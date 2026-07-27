"""M019: M3.0F dialogue localization table."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0019"
CHECKSUM_SOURCE = "M019:language-intelligence-dialogue:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS project_dialogue_lines (
        id VARCHAR(64) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64) NOT NULL,
        speaker_id VARCHAR(64),
        original_language VARCHAR(32) NOT NULL DEFAULT 'en',
        original_text TEXT NOT NULL,
        localized_json TEXT NOT NULL DEFAULT '{}',
        timing_json TEXT NOT NULL DEFAULT '{}',
        constructed_language INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_dialogue_project ON project_dialogue_lines (project_id)",
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="M3.0F project dialogue localization table",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="DROP TABLE project_dialogue_lines",
    reversible=True,
)
