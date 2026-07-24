"""Initial idempotent baseline migration.

This deliberately creates no application tables. Existing schema creation remains
owned by the current startup path until a later, explicit cutover.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "M001"
CHECKSUM_SOURCE = "M001:phase-0-baseline:no-application-schema-changes:v1"


def apply(connection: Connection) -> None:
    """Record a baseline without changing existing application data or schema."""

    connection.exec_driver_sql("SELECT 1")


MIGRATION = Migration(
    revision=REVISION,
    description="Establish the Phase 0 migration baseline",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Metadata-only baseline; no rollback action is required.",
    reversible=False,
)
