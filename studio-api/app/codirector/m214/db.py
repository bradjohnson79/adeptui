"""Ensure M2.14 tables exist (migration + runtime safety)."""
from __future__ import annotations

from sqlalchemy.engine import Engine

from ...db import engine as default_engine
from ...migrations import DEFAULT_REGISTRY, MigrationRunner

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS m214_attachment_interpretations (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        attachment_id VARCHAR(64) NOT NULL,
        classified_kind VARCHAR(64) NOT NULL DEFAULT 'unknown',
        confidence REAL NOT NULL DEFAULT 0,
        summary TEXT NOT NULL DEFAULT '',
        status VARCHAR(32) NOT NULL DEFAULT 'proposed',
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m214_attach_project ON m214_attachment_interpretations (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m214_emotional_profiles (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        version INTEGER NOT NULL DEFAULT 1,
        profile_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_storyteller_handoffs (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        version INTEGER NOT NULL DEFAULT 1,
        handoff_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_sonic_concepts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        version INTEGER NOT NULL DEFAULT 1,
        concept_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_specialist_messages (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        from_specialist VARCHAR(64) NOT NULL,
        to_specialist VARCHAR(64) NOT NULL,
        kind VARCHAR(32) NOT NULL DEFAULT 'note',
        body TEXT NOT NULL DEFAULT '',
        requires_response INTEGER NOT NULL DEFAULT 0,
        responded INTEGER NOT NULL DEFAULT 0,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m214_msg_project ON m214_specialist_messages (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m214_unified_briefs (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        revision INTEGER NOT NULL DEFAULT 1,
        brief_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_production_meetings (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        topic TEXT NOT NULL DEFAULT '',
        meeting_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_decision_impacts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        decision_id VARCHAR(64),
        impact_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_production_motifs (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        name VARCHAR(128) NOT NULL DEFAULT '',
        kind VARCHAR(32) NOT NULL DEFAULT 'visual',
        motif_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_project_stages (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL UNIQUE,
        stage VARCHAR(32) NOT NULL DEFAULT 'idea',
        stage_json TEXT NOT NULL DEFAULT '{}',
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_media_cards (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        kind VARCHAR(32) NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        group_key VARCHAR(64),
        honesty VARCHAR(16) NOT NULL DEFAULT 'mocked',
        status VARCHAR(32) NOT NULL DEFAULT 'draft',
        media_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m214_media_project ON m214_media_cards (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m214_session_snapshots (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_capability_invokes (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36),
        capability_id VARCHAR(128) NOT NULL,
        action VARCHAR(64) NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
]


def ensure_m214_tables(engine: Engine | None = None) -> None:
    eng = engine or default_engine
    try:
        MigrationRunner(DEFAULT_REGISTRY, eng).apply_pending()
    except Exception:
        pass
    with eng.begin() as conn:
        for stmt in _DDL:
            conn.exec_driver_sql(stmt)
