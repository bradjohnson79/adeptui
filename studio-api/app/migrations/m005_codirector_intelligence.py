"""Co-Director M2.4: production intelligence persistence tables."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M005"
CHECKSUM_SOURCE = "M005:codirector-intelligence:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS codirector_specialist_findings (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        request_id VARCHAR(64) NOT NULL,
        specialist_id VARCHAR(64) NOT NULL,
        prompt_version VARCHAR(32),
        model_id VARCHAR(128),
        context_hash VARCHAR(64),
        output_json TEXT,
        validation_status VARCHAR(24) NOT NULL,
        confidence REAL,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_specialist_findings_project_id "
    "ON codirector_specialist_findings (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_specialist_findings_request_id "
    "ON codirector_specialist_findings (request_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_specialist_findings_specialist_id "
    "ON codirector_specialist_findings (specialist_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_specialist_findings_validation_status "
    "ON codirector_specialist_findings (validation_status)",
    """
    CREATE TABLE IF NOT EXISTS codirector_synthesis_records (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        request_id VARCHAR(64) NOT NULL,
        specialist_ids_json TEXT,
        synthesis_json TEXT,
        prompt_versions_json TEXT,
        plan_id VARCHAR(36),
        model_id VARCHAR(128),
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_synthesis_records_project_id "
    "ON codirector_synthesis_records (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_synthesis_records_request_id "
    "ON codirector_synthesis_records (request_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_synthesis_records_plan_id "
    "ON codirector_synthesis_records (plan_id)",
    """
    CREATE TABLE IF NOT EXISTS codirector_production_plans (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        request_id VARCHAR(64) NOT NULL,
        playbook_id VARCHAR(64),
        title VARCHAR(200),
        status VARCHAR(24) NOT NULL,
        plan_json TEXT,
        visual_validation_pending INTEGER,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_production_plans_project_id "
    "ON codirector_production_plans (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_production_plans_request_id "
    "ON codirector_production_plans (request_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_production_plans_status "
    "ON codirector_production_plans (status)",
)


def apply(connection: Connection) -> None:
    for statement in _DDL:
        connection.exec_driver_sql(statement)


MIGRATION = Migration(
    revision=REVISION,
    description="Add Co-Director M2.4 intelligence persistence tables",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Additive-only. To roll back manually: DROP TABLE codirector_production_plans; "
        "DROP TABLE codirector_synthesis_records; DROP TABLE codirector_specialist_findings;"
    ),
    reversible=False,
)
