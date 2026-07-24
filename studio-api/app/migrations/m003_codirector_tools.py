"""Co-Director M2.2: bounded tool registry invocation ledger.

Additive-only: creates one new table mirroring the `CoDirectorToolInvocation` SQLAlchemy model
in `app/db.py`. No existing table is touched — `tool_call` proposals reuse the existing
`codirector_proposals` row shape (`proposal_type` is already a free-form `VARCHAR(48)` and
`payload_json` already holds arbitrary JSON), so the approval pipeline needs no schema change.

Kept as hand-written DDL for the same reason as `m002_production_bible.py`: it stays runnable
in isolation against a bare SQLite file, and `tests/test_codirector_tools.py` asserts that both
provisioning paths (`Base.metadata.create_all` and `MigrationRunner.apply_pending()`) produce
the same columns.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M003"
CHECKSUM_SOURCE = "M003:codirector-tool-invocations:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS codirector_tool_invocations (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        tool_id VARCHAR(64) NOT NULL,
        tool_schema_version INTEGER NOT NULL,
        kind VARCHAR(16) NOT NULL,
        status VARCHAR(16) NOT NULL,
        arguments_json TEXT,
        result_json TEXT,
        result_hash VARCHAR(64),
        result_truncated INTEGER,
        capability_snapshot_json TEXT,
        error_code VARCHAR(64),
        error_message TEXT,
        proposal_id VARCHAR(36),
        request_id VARCHAR(64),
        duration_ms INTEGER,
        created_by VARCHAR(64),
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_tool_invocations_project_id "
    "ON codirector_tool_invocations (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_tool_invocations_tool_id "
    "ON codirector_tool_invocations (tool_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_tool_invocations_status "
    "ON codirector_tool_invocations (status)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_tool_invocations_proposal_id "
    "ON codirector_tool_invocations (proposal_id)",
)


def apply(connection: Connection) -> None:
    for statement in _DDL:
        connection.exec_driver_sql(statement)


MIGRATION = Migration(
    revision=REVISION,
    description="Add the Co-Director tool invocation ledger",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Additive-only and unreferenced by M1/M2.1 code paths. To roll back manually: "
        "DROP TABLE codirector_tool_invocations, then DELETE FROM codirector_proposals "
        "WHERE proposal_type = 'tool_call' (plus their codirector_approvals / "
        "codirector_execution_receipts children)."
    ),
    reversible=False,
)
