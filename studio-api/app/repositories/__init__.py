"""Persistence contracts introduced without replacing current database access."""

from .contracts import (
    AssetRepository,
    GenerationRepository,
    JobRepository,
    MemoryRepository,
    ProfileRepository,
    ProjectRepository,
    Repository,
    RepositoryBundle,
    RepositoryFactory,
    SceneRepository,
    TimelineRepository,
)
from .sqlite import (
    SQLiteRepositoryBoundary,
    SQLiteRepositoryBoundaryFactory,
    SQLiteRepositoryFactory,
    make_sqlite_repository_boundary,
)

__all__ = [
    "AssetRepository",
    "GenerationRepository",
    "JobRepository",
    "MemoryRepository",
    "ProfileRepository",
    "ProjectRepository",
    "Repository",
    "RepositoryBundle",
    "RepositoryFactory",
    "SQLiteRepositoryBoundary",
    "SQLiteRepositoryBoundaryFactory",
    "SQLiteRepositoryFactory",
    "SceneRepository",
    "TimelineRepository",
    "make_sqlite_repository_boundary",
]
