"""M029: Multi-Shot Image Planning — plans, ordered shots, candidate history.

Creates the three project-scoped tables backing the provider-agnostic
Multi-Shot architecture (Krea 2 milestone, Phase D):

- ``multi_shot_plans``      — one row per scene decomposition plan.
- ``multi_shots``           — ordered shots per plan (``order_index``).
- ``multi_shot_candidates`` — append-only per-shot candidate history.

Every table carries a plain ``project_id`` column, so the generic
project-deletion sweep in ``app.project_cleanup`` removes these rows with the
owning project; plan-level deletes cascade explicitly in the service layer.
Forward-only and non-destructive: CREATE IF NOT EXISTS plus indexes, no ALTER
or DROP of existing tables.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0029"
CHECKSUM_SOURCE = "M029:multi-shot-planning:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS multi_shot_plans (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36) NOT NULL,
        name VARCHAR(200) NOT NULL DEFAULT 'Multi-Shot Plan',
        provider_id VARCHAR(64) NOT NULL DEFAULT '',
        model_id VARCHAR(128) NOT NULL DEFAULT '',
        shared_visual_context TEXT NOT NULL DEFAULT '',
        shared_references_json TEXT NOT NULL DEFAULT '[]',
        aspect_ratio VARCHAR(16) NOT NULL DEFAULT '',
        resolution_label VARCHAR(64) NOT NULL DEFAULT '',
        status VARCHAR(24) NOT NULL DEFAULT 'draft',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_multi_shot_plans_project ON multi_shot_plans (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_multi_shot_plans_scene ON multi_shot_plans (scene_id)",
    """
    CREATE TABLE IF NOT EXISTS multi_shots (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        plan_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(36) NOT NULL,
        order_index INTEGER NOT NULL DEFAULT 0,
        title VARCHAR(200) NOT NULL DEFAULT '',
        prompt TEXT NOT NULL DEFAULT '',
        image_prompt TEXT NOT NULL DEFAULT '',
        video_prompt TEXT NOT NULL DEFAULT '',
        duration_hint FLOAT,
        framing VARCHAR(64) NOT NULL DEFAULT '',
        camera_angle VARCHAR(64) NOT NULL DEFAULT '',
        subject_ids_json TEXT NOT NULL DEFAULT '[]',
        reference_ids_json TEXT NOT NULL DEFAULT '[]',
        seed_strategy VARCHAR(32) NOT NULL DEFAULT 'sequence',
        status VARCHAR(24) NOT NULL DEFAULT 'pending',
        approved_asset_id VARCHAR(36),
        approved_candidate_id VARCHAR(36),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_multi_shots_plan ON multi_shots (plan_id)",
    "CREATE INDEX IF NOT EXISTS ix_multi_shots_project ON multi_shots (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_multi_shots_scene ON multi_shots (scene_id)",
    """
    CREATE TABLE IF NOT EXISTS multi_shot_candidates (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        shot_id VARCHAR(36) NOT NULL,
        plan_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        generation_id VARCHAR(64),
        provider VARCHAR(64) NOT NULL DEFAULT '',
        model VARCHAR(128) NOT NULL DEFAULT '',
        seed INTEGER,
        prompt TEXT NOT NULL DEFAULT '',
        references_json TEXT NOT NULL DEFAULT '[]',
        loras_json TEXT NOT NULL DEFAULT '[]',
        settings_json TEXT NOT NULL DEFAULT '{}',
        asset_id VARCHAR(36),
        status VARCHAR(24) NOT NULL DEFAULT 'pending',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_multi_shot_candidates_shot ON multi_shot_candidates (shot_id)",
    "CREATE INDEX IF NOT EXISTS ix_multi_shot_candidates_plan ON multi_shot_candidates (plan_id)",
    "CREATE INDEX IF NOT EXISTS ix_multi_shot_candidates_project ON multi_shot_candidates (project_id)",
]


def apply(conn: Connection) -> None:
    for stmt in _DDL:
        conn.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="Multi-Shot Image Planning: plans + ordered shots + candidate history tables",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Drop multi_shot_candidates, multi_shots, and multi_shot_plans. No existing "
        "tables are altered, so rollback never touches pre-M029 data."
    ),
    reversible=False,
)
