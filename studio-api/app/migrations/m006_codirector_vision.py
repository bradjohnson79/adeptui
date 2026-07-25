"""Co-Director M2.5: vision & continuity validation persistence tables + Asset columns."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M006"
CHECKSUM_SOURCE = "M006:codirector-vision:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS codirector_validation_sessions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        asset_id VARCHAR(36),
        plan_id VARCHAR(36),
        scene_id VARCHAR(36),
        reference_asset_id VARCHAR(36),
        provider VARCHAR(32) NOT NULL,
        status VARCHAR(24) NOT NULL,
        validator_set_json TEXT,
        report_id VARCHAR(36),
        comparison_id VARCHAR(36),
        error_message TEXT,
        requirements_json TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_sessions_project_id "
    "ON codirector_validation_sessions (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_sessions_asset_id "
    "ON codirector_validation_sessions (asset_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_sessions_plan_id "
    "ON codirector_validation_sessions (plan_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_sessions_status "
    "ON codirector_validation_sessions (status)",
    """
    CREATE TABLE IF NOT EXISTS codirector_validation_reports (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        session_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        overall_score REAL,
        passed INTEGER,
        band VARCHAR(32),
        strengths_json TEXT,
        warnings_json TEXT,
        failures_json TEXT,
        recommendations_json TEXT,
        confidence REAL,
        weights_json TEXT,
        blocking_failures_json TEXT,
        provider VARCHAR(32),
        report_json TEXT,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_reports_session_id "
    "ON codirector_validation_reports (session_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_reports_project_id "
    "ON codirector_validation_reports (project_id)",
    """
    CREATE TABLE IF NOT EXISTS codirector_validation_findings (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        session_id VARCHAR(36) NOT NULL,
        report_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        validator_id VARCHAR(64) NOT NULL,
        status VARCHAR(24) NOT NULL,
        score REAL,
        confidence REAL,
        severity VARCHAR(24),
        correctable INTEGER,
        blocking INTEGER,
        issues_json TEXT,
        finding_json TEXT,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_findings_session_id "
    "ON codirector_validation_findings (session_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_findings_report_id "
    "ON codirector_validation_findings (report_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_findings_validator_id "
    "ON codirector_validation_findings (validator_id)",
    """
    CREATE TABLE IF NOT EXISTS codirector_validation_approvals (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        session_id VARCHAR(36) NOT NULL,
        report_id VARCHAR(36),
        project_id VARCHAR(36) NOT NULL,
        decision VARCHAR(32) NOT NULL,
        reviewer VARCHAR(64),
        notes TEXT,
        override_flag INTEGER,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_approvals_session_id "
    "ON codirector_validation_approvals (session_id)",
    """
    CREATE TABLE IF NOT EXISTS codirector_validation_correction_proposals (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        session_id VARCHAR(36) NOT NULL,
        report_id VARCHAR(36),
        project_id VARCHAR(36) NOT NULL,
        proposal_id VARCHAR(36) NOT NULL,
        kind VARCHAR(64),
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_correction_proposals_session_id "
    "ON codirector_validation_correction_proposals (session_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_correction_proposals_proposal_id "
    "ON codirector_validation_correction_proposals (proposal_id)",
    """
    CREATE TABLE IF NOT EXISTS codirector_validation_comparisons (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        session_id VARCHAR(36) NOT NULL,
        project_id VARCHAR(36) NOT NULL,
        reference_asset_id VARCHAR(36),
        generated_asset_id VARCHAR(36),
        reference_meta_json TEXT,
        generated_meta_json TEXT,
        differences_json TEXT,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_validation_comparisons_session_id "
    "ON codirector_validation_comparisons (session_id)",
)


def apply(connection: Connection) -> None:
    for statement in _DDL:
        connection.exec_driver_sql(statement)

    asset_cols = {
        row[1] for row in connection.exec_driver_sql("PRAGMA table_info(assets)").fetchall()
    }
    if asset_cols:
        if "validation_lifecycle" not in asset_cols:
            connection.exec_driver_sql(
                "ALTER TABLE assets ADD COLUMN validation_lifecycle TEXT DEFAULT 'not_requested'"
            )
        if "validation_result" not in asset_cols:
            connection.exec_driver_sql(
                "ALTER TABLE assets ADD COLUMN validation_result TEXT DEFAULT 'unreviewed'"
            )
        if "production_approval" not in asset_cols:
            connection.exec_driver_sql(
                "ALTER TABLE assets ADD COLUMN production_approval TEXT DEFAULT 'none'"
            )


MIGRATION = Migration(
    revision=REVISION,
    description="Add Co-Director M2.5 vision validation tables and Asset validation columns",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Additive-only. To roll back manually: DROP TABLE codirector_validation_comparisons; "
        "DROP TABLE codirector_validation_correction_proposals; "
        "DROP TABLE codirector_validation_approvals; "
        "DROP TABLE codirector_validation_findings; "
        "DROP TABLE codirector_validation_reports; "
        "DROP TABLE codirector_validation_sessions; "
        "Asset validation columns may remain (SQLite drop-column limitations)."
    ),
    reversible=False,
)
