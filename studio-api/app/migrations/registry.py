"""Migration definitions and an ordered, immutable registry."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.engine import Connection

MigrationStep = Callable[[Connection], None]


@dataclass(frozen=True)
class Migration:
    """One forward-only migration plus informational rollback metadata."""

    revision: str
    description: str
    apply: MigrationStep
    checksum_source: str
    rollback_notes: str
    reversible: bool = False

    @property
    def checksum(self) -> str:
        """Return a stable checksum for drift detection."""

        return sha256(self.checksum_source.encode("utf-8")).hexdigest()


class MigrationRegistry:
    """Validated collection of migrations ordered by revision."""

    def __init__(self, migrations: Iterable[Migration] = ()) -> None:
        registered = tuple(sorted(migrations, key=lambda item: item.revision))
        revisions = [item.revision for item in registered]
        if len(revisions) != len(set(revisions)):
            raise ValueError("Migration revisions must be unique")
        self._migrations = registered

    def all(self) -> tuple[Migration, ...]:
        return self._migrations

    def get(self, revision: str) -> Migration:
        for migration in self._migrations:
            if migration.revision == revision:
                return migration
        raise KeyError(revision)
