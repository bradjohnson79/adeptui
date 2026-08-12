from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .codirector.bible.cleanup import delete_bible_for_project

_PROJECT_COLUMN_NAMES = ("project_id", "projectId")
_INDIRECT_PROJECT_DELETES: tuple[tuple[str, str], ...] = (
    (
        "production_context_extensions",
        "context_id IN (SELECT id FROM production_contexts WHERE project_id = :project_id)",
    ),
    (
        "production_job_attempts",
        "job_id IN (SELECT id FROM production_jobs WHERE project_id = :project_id)",
    ),
    (
        "production_job_dependencies",
        "job_id IN (SELECT id FROM production_jobs WHERE project_id = :project_id) "
        "OR depends_on_job_id IN (SELECT id FROM production_jobs WHERE project_id = :project_id)",
    ),
    (
        "production_job_audit",
        "job_id IN (SELECT id FROM production_jobs WHERE project_id = :project_id)",
    ),
    (
        "production_job_events",
        "job_id IN (SELECT id FROM production_jobs WHERE project_id = :project_id) OR project_id = :project_id",
    ),
    (
        "production_notifications",
        "job_id IN (SELECT id FROM production_jobs WHERE project_id = :project_id) OR project_id = :project_id",
    ),
    (
        "timeline_reference_bindings",
        "version_id IN ("
        "SELECT v.id FROM timeline_reference_set_versions v "
        "JOIN timeline_reference_sets s ON s.id = v.set_id "
        "WHERE s.project_id = :project_id"
        ")",
    ),
    (
        "timeline_reference_set_versions",
        "set_id IN (SELECT id FROM timeline_reference_sets WHERE project_id = :project_id)",
    ),
    (
        "reference_preset_bindings",
        "preset_id IN (SELECT id FROM reference_presets WHERE project_id = :project_id)",
    ),
    (
        "script_transactions",
        "document_id IN (SELECT id FROM script_documents_v2 WHERE project_id = :project_id)",
    ),
    (
        "script_revision_snapshots",
        "document_id IN (SELECT id FROM script_documents_v2 WHERE project_id = :project_id)",
    ),
    (
        "script_notes",
        "document_id IN (SELECT id FROM script_documents_v2 WHERE project_id = :project_id)",
    ),
    (
        "character_versions",
        "character_profile_id IN (SELECT id FROM character_profiles WHERE project_id = :project_id)",
    ),
    (
        "character_reference_assets",
        "character_profile_id IN (SELECT id FROM character_profiles WHERE project_id = :project_id)",
    ),
    (
        "character_traits",
        "character_profile_id IN (SELECT id FROM character_profiles WHERE project_id = :project_id)",
    ),
    (
        "character_wardrobes",
        "character_profile_id IN (SELECT id FROM character_profiles WHERE project_id = :project_id)",
    ),
    (
        "character_props",
        "character_profile_id IN (SELECT id FROM character_profiles WHERE project_id = :project_id)",
    ),
    (
        "voice_consent_records",
        "voice_profile_id IN (SELECT id FROM voice_profiles WHERE project_id = :project_id)",
    ),
    (
        "voice_performance_takes",
        '"recordId" IN (SELECT id FROM voice_performance_records WHERE "projectId" = :project_id)',
    ),
    (
        "asset_versions",
        "asset_id IN (SELECT id FROM assets WHERE project_id = :project_id)",
    ),
    (
        "asset_edges",
        "from_id IN (SELECT id FROM assets WHERE project_id = :project_id) "
        "OR to_id IN (SELECT id FROM assets WHERE project_id = :project_id)",
    ),
    (
        "codirector_approvals",
        "proposal_id IN (SELECT id FROM codirector_proposals WHERE project_id = :project_id)",
    ),
    (
        "codirector_execution_receipts",
        "proposal_id IN (SELECT id FROM codirector_proposals WHERE project_id = :project_id)",
    ),
    (
        "creative_item_versions",
        "item_id IN (SELECT id FROM creative_items WHERE project_id = :project_id)",
    ),
    (
        "m212_lesson_versions",
        "lesson_id IN (SELECT id FROM m212_lessons WHERE project_id = :project_id)",
    ),
    (
        "m28_recipe_stages",
        "recipe_id IN (SELECT id FROM m28_recipes WHERE project_id = :project_id)",
    ),
    (
        "m28_shot_profile_versions",
        "profile_id IN (SELECT id FROM m28_shot_profiles WHERE project_id = :project_id)",
    ),
)


def _delete_where(db: Session, table_name: str, where_sql: str, project_id: str) -> None:
    db.execute(text(f'DELETE FROM "{table_name}" WHERE {where_sql}'), {"project_id": project_id})


def delete_project_residue(db: Session, project_id: str) -> None:
    inspector = inspect(db.bind)
    table_names = set(inspector.get_table_names())

    delete_bible_for_project(db, project_id)

    for table_name, where_sql in _INDIRECT_PROJECT_DELETES:
        if table_name in table_names:
            _delete_where(db, table_name, where_sql, project_id)

    for table_name in table_names:
        if table_name == "projects":
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in _PROJECT_COLUMN_NAMES:
            if column_name in columns:
                quoted = f'"{column_name}"' if column_name != "project_id" else column_name
                _delete_where(db, table_name, f"{quoted} = :project_id", project_id)
                break
