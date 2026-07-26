"""M013: Co-Director M2.9 Complete Native Production Suite tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M013"
CHECKSUM_SOURCE = "M013:production-suite:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS m29_asset_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        asset_id VARCHAR(64) NOT NULL,
        department VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL,
        parent_version_id VARCHAR(36),
        job_id VARCHAR(36),
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m29_asset_versions_project_id ON m29_asset_versions (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_m29_asset_versions_asset_id ON m29_asset_versions (asset_id)",
    """
    CREATE TABLE IF NOT EXISTS m29_frame_records (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        shot_id VARCHAR(64),
        frame_type VARCHAR(64) NOT NULL,
        order_index INTEGER NOT NULL DEFAULT 0,
        asset_id VARCHAR(64),
        version_id VARCHAR(36),
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m29_frame_records_project_id ON m29_frame_records (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_m29_frame_records_shot_id ON m29_frame_records (shot_id)",
    """
    CREATE TABLE IF NOT EXISTS m29_render_manifests (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36),
        kind VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL,
        job_id VARCHAR(36),
        asset_id VARCHAR(64),
        manifest_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m29_render_manifests_project_id ON m29_render_manifests (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m29_audio_cues (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36),
        cue_kind VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL,
        asset_id VARCHAR(64),
        start_sec REAL NOT NULL DEFAULT 0,
        duration_sec REAL NOT NULL DEFAULT 0,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m29_audio_cues_project_id ON m29_audio_cues (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m29_timeline_proposals (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36),
        status VARCHAR(32) NOT NULL,
        proposal_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m29_timeline_proposals_project_id ON m29_timeline_proposals (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m29_control_plans (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        status VARCHAR(32) NOT NULL,
        request_text TEXT NOT NULL DEFAULT '',
        plan_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m29_control_plans_project_id ON m29_control_plans (project_id)",
)


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="Add M2.9 production suite tables (assets, frames, renders, audio cues)",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Additive. Drop m29_* tables to reverse.",
    reversible=False,
)
