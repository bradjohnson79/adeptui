from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from app.migrations import (
    DEFAULT_REGISTRY,
    ChecksumMismatchError,
    Migration,
    MigrationRegistry,
    MigrationRunner,
)


def test_default_registry_migrations_are_idempotent(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'migrations.db'}")
    runner = MigrationRunner(engine, DEFAULT_REGISTRY)

    first = runner.apply_pending()
    second = runner.apply_pending()

    assert first.applied == ("M001", "M002", "M003", "M004", "M005", "M006", "M007", "M008", "M010", "M011", "M012")
    assert second.applied == ()
    assert second.already_applied == ("M001", "M002", "M003", "M004", "M005", "M006", "M007", "M008", "M010", "M011", "M012")


def test_sqlite_foreign_keys_are_enabled_before_apply(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'foreign-keys.db'}")
    observed: list[int] = []

    migration = Migration(
        revision="T001",
        description="observe pragma",
        apply=lambda connection: observed.append(
            connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
        ),
        checksum_source="observe-foreign-keys",
        rollback_notes="none",
    )
    MigrationRunner(engine, MigrationRegistry((migration,))).apply_pending()

    assert observed == [1]


def test_applied_migration_checksum_mismatch_is_rejected(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'checksum.db'}")

    original = Migration(
        revision="T001",
        description="test",
        apply=lambda connection: connection.exec_driver_sql("SELECT 1"),
        checksum_source="original",
        rollback_notes="none",
    )
    MigrationRunner(engine, MigrationRegistry((original,))).apply_pending()

    changed = Migration(
        revision="T001",
        description="test",
        apply=lambda connection: connection.exec_driver_sql("SELECT 1"),
        checksum_source="changed",
        rollback_notes="none",
    )
    with pytest.raises(ChecksumMismatchError, match="T001"):
        MigrationRunner(engine, MigrationRegistry((changed,))).pending()
