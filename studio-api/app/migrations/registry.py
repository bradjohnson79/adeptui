"""Migration definitions and an ordered, immutable registry."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.engine import Connection

MigrationStep = Callable[[Connection], None]

_REVISION_DIGITS = re.compile(r"\d+")


def _revision_sort_key(revision: str):
    """Sort migrations by their numeric portion so revision formats that share the
    same zero-padded number (``M001`` vs ``0017``) order identically.

    Two revision formats coexist in the registry (``M###`` for the early waves and
    ``0###`` for later waves). A raw string sort places ``0###`` before ``M###``
    because ``'0' < 'M'`` in ASCII, which would run later-wave ALTER TABLE statements
    before the initial ``CREATE TABLE projects`` migration on a fresh engine. The
    numeric sort restores the intended chronological order without rewriting any
    revision string or checksum (no destructive change to already-applied rows).
    """

    digits = _REVISION_DIGITS.findall(revision or "")
    if digits:
        return (0, int(digits[0]))
    return (1, revision or "")


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
        registered = tuple(sorted(migrations, key=lambda item: _revision_sort_key(item.revision)))
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
