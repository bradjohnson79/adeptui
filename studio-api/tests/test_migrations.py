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

    expected = tuple(m.revision for m in DEFAULT_REGISTRY.all())
    assert first.applied == expected
    assert second.applied == ()
    assert second.already_applied == expected


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


def test_registry_orders_migrations_by_numeric_revision_not_raw_string() -> None:
    """The registry mixes ``M###`` and ``0###`` revision formats. A raw string sort
    would place ``0###`` before ``M###`` and run later-wave ALTER TABLE statements
    before the initial CREATE TABLE migration on a fresh engine. The sort must be
    driven by the numeric portion so chronological order is preserved."""

    revisions = [m.revision for m in DEFAULT_REGISTRY.all()]
    # M001 (creates projects) must precede M026 (ALTER TABLE projects ...).
    assert revisions.index("M001") < revisions.index("0026")
    # Every adjacent pair must be in ascending numeric order.
    nums = []
    for rev in revisions:
        import re

        match = re.search(r"\d+", rev)
        assert match, f"revision {rev!r} has no numeric portion"
        nums.append(int(match.group()))
    assert nums == sorted(nums)
    # The full set is exactly the registered revisions, no drops.
    assert len(revisions) == len(set(revisions))


def test_fresh_engine_migrates_cleanly_in_numeric_order(tmp_path) -> None:
    """Regression: a fresh engine (no Base.metadata.create_all first) must migrate
    cleanly. Previously the raw-string sort ran M026's ALTER TABLE projects before
    M001 ran, and M026 assumed the projects table (provisioned by create_all, not by
    any migration) already existed, crashing the whole migration run."""

    engine = create_engine(f"sqlite:///{tmp_path / 'fresh-engine.db'}")
    result = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    expected = tuple(m.revision for m in DEFAULT_REGISTRY.all())
    assert result.applied == expected
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "schema_migrations" in tables
    # M026 creates posecraft_revisions; it must survive a migration-only run even
    # though the projects table (provisioned separately by create_all) is absent.
    assert "posecraft_revisions" in tables
    # Every registered migration is recorded as applied exactly once.
    rows = engine.connect().exec_driver_sql(
        "SELECT revision FROM schema_migrations"
    ).fetchall()
    assert {str(r[0]) for r in rows} == set(expected)
