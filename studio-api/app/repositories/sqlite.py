"""SQLite repository boundary marker; existing SQLAlchemy access remains active."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import RepositoryBundle


@dataclass(frozen=True)
class SQLiteRepositoryBoundary:
    """Configuration marker for a future SQLite repository implementation."""

    database_url: str
    dialect: str = "sqlite"


def make_sqlite_repository_boundary(database_url: str) -> SQLiteRepositoryBoundary:
    """Create boundary metadata without opening or modifying a database."""

    if not database_url.startswith("sqlite"):
        raise ValueError("SQLite repository URLs must use the sqlite dialect")
    return SQLiteRepositoryBoundary(database_url=database_url)


class SQLiteRepositoryBoundaryFactory:
    """Factory for inert SQLite boundary markers, not live repositories."""

    def create(self, database_url: str) -> SQLiteRepositoryBoundary:
        return make_sqlite_repository_boundary(database_url)


class SQLiteRepositoryFactory(Protocol):
    """Future factory contract for a complete SQLite repository bundle."""

    def create(
        self, boundary: SQLiteRepositoryBoundary
    ) -> RepositoryBundle: ...
