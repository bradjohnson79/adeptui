"""M027: PoseCraft custom poses — project-scoped creator-defined pose CRUD.

Master Program Phase 15–20: persistence. Custom poses are stored per
project so creators can save, reuse, and delete their own poses
alongside the canonical catalog. The thumbnail is generated from the
pose's canonical joint data (see poseThumbnail.ts) and stored as SVG.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0027"
CHECKSUM_SOURCE = "M027:posecraft-custom-poses:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS posecraft_custom_poses (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        pose_id VARCHAR(120) NOT NULL,
        label VARCHAR(200) NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        category VARCHAR(48) NOT NULL DEFAULT 'custom',
        archetypes_json TEXT NOT NULL DEFAULT '[]',
        joints_json TEXT NOT NULL DEFAULT '{}',
        thumbnail TEXT NOT NULL DEFAULT '',
        creator_modified BOOLEAN NOT NULL DEFAULT 1,
        saved_by VARCHAR(64) NOT NULL DEFAULT 'creator',
        created_at DATETIME,
        updated_at DATETIME,
        UNIQUE (project_id, pose_id),
        FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_posecraft_custom_poses_project ON posecraft_custom_poses (project_id)",
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="PoseCraft custom poses (project-scoped creator pose CRUD)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Drop posecraft_custom_poses (additive; no shared data lost).",
    reversible=False,
)
