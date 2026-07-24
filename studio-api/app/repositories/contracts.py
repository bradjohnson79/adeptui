"""Repository boundaries for persistence-independent backend domain access."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

RecordT = TypeVar("RecordT")
Record = Mapping[str, Any]


class Repository(Protocol[RecordT]):
    """Minimal persistence contract shared by domain repositories."""

    def get(self, entity_id: str) -> RecordT | None: ...

    def list(self, *, limit: int | None = None, offset: int = 0) -> Sequence[RecordT]: ...

    def save(self, record: RecordT) -> RecordT: ...

    def delete(self, entity_id: str) -> bool: ...


class ProjectRepository(Repository[Record], Protocol):
    def list_active(self) -> Sequence[Record]: ...


class SceneRepository(Repository[Record], Protocol):
    def list_for_project(self, project_id: str) -> Sequence[Record]: ...


class ProfileRepository(Repository[Record], Protocol):
    def list_for_project(self, project_id: str) -> Sequence[Record]: ...


class GenerationRepository(Repository[Record], Protocol):
    def list_for_scene(self, scene_id: str) -> Sequence[Record]: ...


class TimelineRepository(Repository[Record], Protocol):
    def get_for_project(self, project_id: str) -> Record | None: ...


class AssetRepository(Repository[Record], Protocol):
    def list_for_project(self, project_id: str) -> Sequence[Record]: ...


class JobRepository(Repository[Record], Protocol):
    def list_for_project(self, project_id: str) -> Sequence[Record]: ...


class MemoryRepository(Repository[Record], Protocol):
    def list_for_scope(self, scope: str, scope_id: str) -> Sequence[Record]: ...


@dataclass(frozen=True)
class RepositoryBundle:
    """Complete repository set supplied by one persistence implementation."""

    projects: ProjectRepository
    scenes: SceneRepository
    profiles: ProfileRepository
    generations: GenerationRepository
    timelines: TimelineRepository
    assets: AssetRepository
    jobs: JobRepository
    memories: MemoryRepository


class RepositoryFactory(Protocol):
    """Factory boundary used by a future persistence cutover."""

    def create(self) -> RepositoryBundle: ...
