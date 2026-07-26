"""Stable provider contract for M2.10b sandbox audio generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from .schemas import AudioGenerateRequest, AudioGenerateResult


@runtime_checkable
class AudioGenerationProvider(Protocol):
    """Structural protocol for sandbox audio providers."""

    id: str
    capabilities: list[str]

    def health_check(self) -> dict[str, Any]: ...

    def validate_request(self, request: AudioGenerateRequest) -> dict[str, Any]: ...

    def generate(self, request: AudioGenerateRequest) -> AudioGenerateResult: ...

    def cancel(self, job_id: str) -> None: ...

    def dispose(self) -> None: ...


class AudioGenerationProviderABC(ABC):
    """ABC form of ``AudioGenerationProvider`` for concrete adapters."""

    id: str
    capabilities: list[str]

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def validate_request(self, request: AudioGenerateRequest) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def generate(self, request: AudioGenerateRequest) -> AudioGenerateResult:
        raise NotImplementedError

    @abstractmethod
    def cancel(self, job_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def dispose(self) -> None:
        raise NotImplementedError
