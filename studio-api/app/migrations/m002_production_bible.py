"""Co-Director M2.1: Production Bible + durable proposals/approvals schema.

Additive-only: creates seven new tables, mirroring the SQLAlchemy models declared in
`app/db.py` (`ProductionBible`, `ProductionBibleVersion`, `ProductionBibleEntity`,
`ProductionBibleFact`, `CoDirectorProposal`, `CoDirectorApproval`,
`CoDirectorExecutionReceipt`). No existing table is touched.

Kept as hand-written DDL (rather than importing `app.db.Base.metadata`) so this migration
stays runnable in isolation against a bare SQLite file, exactly like `m001_initial.py`, and
so `tests/test_production_bible.py` can assert both provisioning paths (`create_all` and
`MigrationRunner.apply_pending()`) produce the same columns.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M002"
CHECKSUM_SOURCE = "M002:production-bible-and-proposals:v1"

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS production_bibles (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL UNIQUE,
        current_version_id VARCHAR(36),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_bibles_project_id ON production_bibles (project_id)",
    """
    CREATE TABLE IF NOT EXISTS production_bible_versions (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        bible_id VARCHAR(36) NOT NULL,
        version_number INTEGER NOT NULL,
        parent_version_id VARCHAR(36),
        summary TEXT,
        change_reason TEXT,
        created_by VARCHAR(64),
        created_at DATETIME NOT NULL,
        FOREIGN KEY(bible_id) REFERENCES production_bibles (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_bible_versions_bible_id ON production_bible_versions (bible_id)",
    """
    CREATE TABLE IF NOT EXISTS production_bible_entities (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        bible_version_id VARCHAR(36) NOT NULL,
        entity_type VARCHAR(32) NOT NULL,
        entity_key VARCHAR(160) NOT NULL,
        display_name VARCHAR(200),
        data_json TEXT,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(bible_version_id) REFERENCES production_bible_versions (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_bible_entities_bible_version_id "
    "ON production_bible_entities (bible_version_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_bible_entities_entity_type ON production_bible_entities (entity_type)",
    "CREATE INDEX IF NOT EXISTS ix_production_bible_entities_entity_key ON production_bible_entities (entity_key)",
    """
    CREATE TABLE IF NOT EXISTS production_bible_facts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        bible_version_id VARCHAR(36) NOT NULL,
        entity_key VARCHAR(160),
        fact_type VARCHAR(32),
        statement TEXT,
        data_json TEXT,
        created_at DATETIME NOT NULL,
        FOREIGN KEY(bible_version_id) REFERENCES production_bible_versions (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_production_bible_facts_bible_version_id "
    "ON production_bible_facts (bible_version_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_bible_facts_entity_key ON production_bible_facts (entity_key)",
    """
    CREATE TABLE IF NOT EXISTS codirector_proposals (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        bible_id VARCHAR(36),
        based_on_version_id VARCHAR(36),
        proposal_type VARCHAR(48),
        title VARCHAR(200),
        summary TEXT,
        payload_json TEXT,
        status VARCHAR(24) NOT NULL,
        request_id VARCHAR(64),
        created_by VARCHAR(64),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_proposals_project_id ON codirector_proposals (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_proposals_status ON codirector_proposals (status)",
    """
    CREATE TABLE IF NOT EXISTS codirector_approvals (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        proposal_id VARCHAR(36) NOT NULL,
        decision VARCHAR(24) NOT NULL,
        note TEXT,
        decided_by VARCHAR(64),
        decided_at DATETIME NOT NULL,
        FOREIGN KEY(proposal_id) REFERENCES codirector_proposals (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_approvals_proposal_id ON codirector_approvals (proposal_id)",
    """
    CREATE TABLE IF NOT EXISTS codirector_execution_receipts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        proposal_id VARCHAR(36) NOT NULL,
        input_hash VARCHAR(64) NOT NULL,
        status VARCHAR(24) NOT NULL,
        resulting_version_id VARCHAR(36),
        error_json TEXT,
        executed_at DATETIME NOT NULL,
        FOREIGN KEY(proposal_id) REFERENCES codirector_proposals (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_codirector_execution_receipts_proposal_id "
    "ON codirector_execution_receipts (proposal_id)",
    "CREATE INDEX IF NOT EXISTS ix_codirector_execution_receipts_input_hash "
    "ON codirector_execution_receipts (input_hash)",
)


def apply(connection: Connection) -> None:
    for statement in _DDL:
        connection.exec_driver_sql(statement)


MIGRATION = Migration(
    revision=REVISION,
    description="Add Production Bible + Co-Director proposal/approval/receipt tables",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Additive-only and unreferenced by M1 code paths. To roll back manually, drop in "
        "this order: codirector_execution_receipts, codirector_approvals, "
        "codirector_proposals, production_bible_facts, production_bible_entities, "
        "production_bible_versions, production_bibles."
    ),
    reversible=False,
)
