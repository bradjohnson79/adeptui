"""Explicit migration runner; application startup does not invoke this module."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.engine import Connection, Engine

from .registry import Migration, MigrationRegistry

SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    revision TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    reversible INTEGER NOT NULL DEFAULT 0,
    rollback_notes TEXT NOT NULL DEFAULT ''
)
"""


@dataclass(frozen=True)
class MigrationRun:
    """Summary of an explicit migration run."""

    applied: tuple[str, ...]
    already_applied: tuple[str, ...]


class ChecksumMismatchError(RuntimeError):
    """Raised when an applied migration no longer matches its registration."""


class MigrationRunner:
    """Apply pending migrations one at a time in database transactions."""

    def __init__(self, engine: Engine, registry: MigrationRegistry) -> None:
        self._engine = engine
        self._registry = registry

    def pending(self) -> tuple[Migration, ...]:
        """Return unapplied migrations after validating stored checksums."""

        with self._transaction() as connection:
            connection.exec_driver_sql(SCHEMA_MIGRATIONS_DDL)
            rows = connection.exec_driver_sql(
                "SELECT revision, checksum FROM schema_migrations"
            ).fetchall()
        applied = {str(row[0]): str(row[1]) for row in rows}
        self._validate_checksums(applied)
        return tuple(
            migration
            for migration in self._registry.all()
            if migration.revision not in applied
        )

    def apply_pending(self) -> MigrationRun:
        """Apply all pending migrations transactionally and record metadata."""

        pending = self.pending()
        applied_now: list[str] = []
        for migration in pending:
            with self._transaction() as connection:
                migration.apply(connection)
                connection.exec_driver_sql(
                    """
                    INSERT INTO schema_migrations (
                        revision, description, checksum, applied_at,
                        reversible, rollback_notes
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        migration.revision,
                        migration.description,
                        migration.checksum,
                        datetime.now(timezone.utc).isoformat(),
                        int(migration.reversible),
                        migration.rollback_notes,
                    ),
                )
            applied_now.append(migration.revision)

        pending_revisions = {migration.revision for migration in pending}
        already_applied = tuple(
            migration.revision
            for migration in self._registry.all()
            if migration.revision not in pending_revisions
        )
        return MigrationRun(tuple(applied_now), already_applied)

    @contextmanager
    def _transaction(self) -> Iterator[Connection]:
        """Open a transaction with SQLite foreign-key enforcement enabled first."""

        with self._engine.connect() as connection:
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                # SQLAlchemy autobegins around PRAGMA execution. End that
                # bookkeeping transaction before the migration transaction.
                connection.commit()
            with connection.begin():
                yield connection

    def _validate_checksums(self, applied: dict[str, str]) -> None:
        for migration in self._registry.all():
            stored = applied.get(migration.revision)
            if stored is not None and stored != migration.checksum:
                raise ChecksumMismatchError(
                    f"Checksum mismatch for applied migration {migration.revision}"
                )
