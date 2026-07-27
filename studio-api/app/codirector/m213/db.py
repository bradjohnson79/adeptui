"""Ensure M2.13 tables exist (migration + runtime safety)."""
from __future__ import annotations

from sqlalchemy.engine import Engine

from ...db import engine as default_engine
from ...migrations import DEFAULT_REGISTRY, MigrationRunner

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS m213_virtual_environments (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        route VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'draft',
        title TEXT NOT NULL DEFAULT '',
        asset_id VARCHAR(36),
        summary_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        approved_at DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m213_ve_project ON m213_virtual_environments (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m213_theme_profiles (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        environment_id VARCHAR(36),
        name VARCHAR(128) NOT NULL,
        profile_json TEXT NOT NULL DEFAULT '{}',
        recommended INTEGER NOT NULL DEFAULT 0,
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m213_blocking_states (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        environment_id VARCHAR(36) NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        state_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        approved_at DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m213_scene_states (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        environment_id VARCHAR(36) NOT NULL,
        kind VARCHAR(32) NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        state_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m213_scene_plans (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        environment_id VARCHAR(36),
        mode VARCHAR(32) NOT NULL DEFAULT 'guided',
        stage VARCHAR(8) NOT NULL DEFAULT 'A',
        readiness VARCHAR(16) NOT NULL DEFAULT 'NO-GO',
        plan_json TEXT NOT NULL DEFAULT '{}',
        blockers_json TEXT NOT NULL DEFAULT '[]',
        dependencies_json TEXT NOT NULL DEFAULT '[]',
        approvals_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m213_shot_packages (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        plan_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        package_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m213_concepts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        environment_id VARCHAR(36) NOT NULL,
        tier VARCHAR(32) NOT NULL,
        generation_mode VARCHAR(32) NOT NULL,
        asset_id VARCHAR(36),
        payload_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m213_approvals (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        gate VARCHAR(64) NOT NULL,
        subject_id VARCHAR(36) NOT NULL,
        approved INTEGER NOT NULL DEFAULT 0,
        actor VARCHAR(128) NOT NULL DEFAULT 'user',
        note TEXT NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m213_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        subject_kind VARCHAR(64) NOT NULL,
        subject_id VARCHAR(36) NOT NULL,
        version INTEGER NOT NULL,
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m213_capability_log (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36),
        capability_id VARCHAR(128) NOT NULL,
        action VARCHAR(64) NOT NULL,
        reversible INTEGER NOT NULL DEFAULT 1,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
]


def ensure_m213_tables(eng: Engine | None = None) -> None:
    eng = eng or default_engine
    try:
        MigrationRunner(eng, DEFAULT_REGISTRY).apply_pending()
    except Exception:
        with eng.begin() as conn:
            for stmt in _DDL:
                conn.exec_driver_sql(stmt)
