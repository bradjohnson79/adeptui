"""GeneratorRuntimeEvent bridge: subscribe-only dual-emit on PreviewBus.

Governing doc: docs/release-gate/universal-preview-cancel/UNIVERSAL_GENERATOR_PREVIEW_CANCEL.md

The bridge is intentionally additive and subscribe-only. It does not alter the
certified MiniMax H3 Route A preview tap, PreviewBus internals, or any job-status
pipeline. It listens to ``preview_updated`` events on the existing PreviewBus and
publishes a canonical ``runtime_event`` envelope on the same bus so existing SSE
clients receive it without a new socket.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from app.preview_bus import preview_bus
from app.video_runtime.runtime_events import (
    GeneratorRuntimeEvent,
    RuntimeEventEnvelope,
    normalize_from_job_status,
    normalize_from_preview,
)

logger = logging.getLogger(__name__)

__all__ = [
    "RuntimeEventBridge",
    "build_runtime_event_from_preview",
    "normalize_from_job_status",
    "runtime_event_bridge",
]


def _engine_to_provider(engine_id: str) -> tuple[str, str]:
    """Map a preview engineId to a provider/model pair for the canonical event.

    The mapping is intentionally conservative: anything explicitly prefixed as a
    hosted fal engine is reported as provider ``fal``; everything else is treated as
    the local Comfy-backed runtime (including MiniMax H3 Route A, which is served
    from the Adept :8192 local runtime).
    """
    token = str(engine_id or "").strip().lower()
    if token.startswith("fal_"):
        return "fal", token[4:]
    if token in {"auto", ""}:
        return "local-comfy", "auto"
    return "local-comfy", token


def build_runtime_event_from_preview(
    item: dict[str, Any],
) -> Optional[GeneratorRuntimeEvent]:
    """Build a canonical GeneratorRuntimeEvent from a PreviewBus preview item.

    Returns None when the item lacks a jobId or cannot be normalized.
    """
    preview = item.get("preview") or {}
    if not preview.get("jobId"):
        return None
    provider, model_id = _engine_to_provider(preview.get("engineId"))
    created_at = str(preview.get("createdAt") or item.get("ts") or "")
    try:
        return normalize_from_preview(
            preview,
            provider=provider,
            model_id=model_id,
            execution_id=str(preview.get("previewId") or ""),
            created_at=created_at,
            capabilities=preview_bus.capabilities_for(preview.get("engineId")),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Dropping unnormalizable runtime_event: %s", exc)
        return None


class RuntimeEventBridge:
    """Subscribe to PreviewBus and dual-emit canonical runtime_event envelopes."""

    def __init__(self) -> None:
        self._queue: Optional[asyncio.Queue] = None
        self._task: Optional[asyncio.Task[None]] = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._queue = preview_bus.subscribe()
        self._task = asyncio.create_task(self._loop())
        logger.debug("RuntimeEventBridge started")

    async def _loop(self) -> None:
        while True:
            try:
                item = await self._queue.get()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("RuntimeEventBridge queue get failed")
                break
            try:
                await self._handle(item)
            except Exception:
                logger.exception("RuntimeEventBridge handle failed")

    async def _handle(self, item: dict[str, Any]) -> None:
        if item.get("event") != "preview_updated":
            return
        runtime_event = build_runtime_event_from_preview(item)
        if runtime_event is None:
            return
        envelope = RuntimeEventEnvelope(
            event="runtime_event",
            runtimeEvent=runtime_event,
            ts=time.time(),
        )
        await preview_bus.publish(
            "runtime_event",
            preview=None,
            extra=envelope.model_dump(),
        )

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        if self._queue is not None:
            try:
                preview_bus.unsubscribe(self._queue)
            except Exception:  # noqa: BLE001
                pass
            self._queue = None
        logger.debug("RuntimeEventBridge stopped")


runtime_event_bridge = RuntimeEventBridge()
