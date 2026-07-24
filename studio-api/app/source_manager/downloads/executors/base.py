"""DownloadExecutor protocol and shared helpers."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

ProgressHook = Callable[[int, int | None], None]


@dataclass
class DownloadCapabilities:
    can_pause: bool = False
    can_resume: bool = False
    can_cancel: bool = True
    supports_range_requests: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "canPause": self.can_pause,
            "canResume": self.can_resume,
            "canCancel": self.can_cancel,
            "supportsRangeRequests": self.supports_range_requests,
            "message": self.message,
        }


@dataclass
class DownloadExecutionContext:
    operation_id: str
    staging_dir: str
    cancel_event: threading.Event
    pause_event: threading.Event
    on_progress: ProgressHook | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DownloadExecutionResult:
    ok: bool
    phase: str
    message: str = ""
    files: list[dict[str, Any]] = field(default_factory=list)
    error_category: str | None = None
    error: dict[str, Any] | None = None
    bytes_downloaded: int = 0
    archive_path: str | None = None


@runtime_checkable
class DownloadExecutor(Protocol):
    provider_id: str

    def get_capabilities(self, plan: dict[str, Any]) -> DownloadCapabilities: ...

    def execute(
        self, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult: ...

    def cancel(self, operation: dict[str, Any]) -> None: ...
