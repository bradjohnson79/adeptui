"""Co-Director M2.3: Production Bible domain lifecycle + audit events.

Additive-only: adds lifecycle columns to `production_bible_entities` and creates the
append-only `bible_audit_events` table. Mirrors SQLAlchemy models in `app/db.py`.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M004"
CHECKSUM_SOURCE = "M004:bible-domain-lifecycle-and-audit:v1"

_DDL = (
    "ALTER TABLE production_bible_entities ADD COLUMN stable_id VARCHAR(36)",
    "ALTER TABLE production_bible_entities ADD COLUMN slug VARCHAR(160)",
    "ALTER TABLE production_bible_entities ADD COLUMN lifecycle_status VARCHAR(24) DEFAULT 'draft'",
    "ALTER TABLE production_bible_entities ADD COLUMN updated_at DATETIME",
    "ALTER TABLE production_bible_entities ADD COLUMN content_revision INTEGER DEFAULT 1",
    "CREATE INDEX IF NOT EXISTS ix_production_bible_entities_stable_id ON production_bible_entities (stable_id)",
    "CREATE INDEX IF NOT EXISTS ix_production_bible_entities_lifecycle_status "
    "ON production_bible_entities (lifecycle_status)",
    """
    CREATE TABLE IF NOT EXISTS bible_audit_events (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        event_type VARCHAR(48) NOT NULL,
        entity_stable_id VARCHAR(36),
        entity_key VARCHAR(160),
        entity_type VARCHAR(32),
        bible_version_id VARCHAR(36),
        bible_version_number INTEGER,
        proposal_id VARCHAR(36),
        receipt_id VARCHAR(36),
        actor VARCHAR(64) DEFAULT 'user',
        summary TEXT,
        details_json TEXT DEFAULT '{}',
        created_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_bible_audit_events_project_id ON bible_audit_events (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_bible_audit_events_entity_stable_id ON bible_audit_events (entity_stable_id)",
    "CREATE INDEX IF NOT EXISTS ix_bible_audit_events_event_type ON bible_audit_events (event_type)",
)


def apply(connection: Connection) -> None:
    entity_cols = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(production_bible_entities)").fetchall()}
    for statement in _DDL:
        if statement.startswith("ALTER TABLE production_bible_entities"):
            col = statement.split("ADD COLUMN ")[1].split()[0]
            if col in entity_cols:
                continue
        connection.exec_driver_sql(statement)


MIGRATION = Migration(
    revision=REVISION,
    description="Add Bible entity lifecycle columns and bible_audit_events table",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Drop bible_audit_events; SQLite cannot drop columns from production_bible_entities "
        "without table rebuild — lifecycle columns remain harmless if left in place."
    ),
    reversible=False,
)
