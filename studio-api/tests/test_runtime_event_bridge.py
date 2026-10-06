"""GeneratorRuntimeEvent bridge — dual-emit on the existing PreviewBus."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.preview_bus import GenerationPreview, preview_bus
from app.video_runtime.runtime_event_bridge import (
    RuntimeEventBridge,
    build_runtime_event_from_preview,
)


def _preview(
    job_id: str,
    engine_id: str = "minimax-h3",
    progress: float | None = 0.47,
    media_type: str = "image",
    local_path: str = "preview_cache/job/preview.jpg",
    sequence: int = 1,
) -> GenerationPreview:
    return GenerationPreview(
        jobId=job_id,
        sceneId="scene-1",
        engineId=engine_id,
        previewId=f"pv-{uuid.uuid4().hex[:8]}",
        sequenceNumber=sequence,
        createdAt="2026-09-07T00:00:00Z",
        stage="live_preview",
        progress=progress,
        mediaType=media_type,
        localPath=local_path,
    )


def test_build_runtime_event_from_preview_requires_job_id():
    event = build_runtime_event_from_preview(
        {"preview": {"engineId": "minimax-h3", "sequenceNumber": 1}}
    )
    assert event is None


def test_h3_like_preview_emits_preview_frame():
    async def _run() -> dict:
        bridge = RuntimeEventBridge()
        bridge.start()
        try:
            subscriber = preview_bus.subscribe()
            job_id = f"job-h3-{uuid.uuid4().hex[:8]}"
            preview = _preview(job_id=job_id, engine_id="minimax-h3", progress=0.47, sequence=1)
            await preview_bus.publish("preview_updated", preview)

            first = await asyncio.wait_for(subscriber.get(), timeout=1.0)
            assert first["event"] == "preview_updated"

            second = await asyncio.wait_for(subscriber.get(), timeout=1.0)
            assert second["event"] == "runtime_event"
            return second["extra"]["runtimeEvent"]
        finally:
            bridge.stop()

    runtime_event = asyncio.run(_run())
    assert runtime_event["eventType"] == "PREVIEW_FRAME"
    assert runtime_event["jobId"].startswith("job-h3-")
    assert runtime_event["provider"] == "local-comfy"
    assert runtime_event["modelId"] == "minimax-h3"
    assert runtime_event["progressPercent"] == 47
    assert runtime_event["preview"]["draft"] is True


def test_fal_coarse_progress_yields_null_percent():
    async def _run() -> dict:
        bridge = RuntimeEventBridge()
        bridge.start()
        try:
            subscriber = preview_bus.subscribe()
            job_id = f"job-fal-{uuid.uuid4().hex[:8]}"
            preview = _preview(
                job_id=job_id,
                engine_id="fal_seedance",
                progress=0.25,
                sequence=1,
            )
            await preview_bus.publish("preview_updated", preview)

            await asyncio.wait_for(subscriber.get(), timeout=1.0)  # preview_updated
            second = await asyncio.wait_for(subscriber.get(), timeout=1.0)
            assert second["event"] == "runtime_event"
            return second["extra"]["runtimeEvent"]
        finally:
            bridge.stop()

    runtime_event = asyncio.run(_run())
    assert runtime_event["eventType"] == "PREVIEW_FRAME"
    assert runtime_event["provider"] == "fal"
    assert runtime_event["modelId"] == "seedance"
    assert runtime_event["progressPercent"] is None


def test_bridge_drops_event_without_job_id():
    async def _run() -> None:
        bridge = RuntimeEventBridge()
        bridge.start()
        try:
            subscriber = preview_bus.subscribe()
            preview = _preview(job_id="", engine_id="minimax-h3", progress=0.47, sequence=1)
            await preview_bus.publish("preview_updated", preview)

            await asyncio.wait_for(subscriber.get(), timeout=1.0)  # preview_updated
            try:
                await asyncio.wait_for(subscriber.get(), timeout=0.5)
            except asyncio.TimeoutError:
                return  # expected: no runtime_event emitted
            pytest.fail("expected no runtime_event for missing jobId")
        finally:
            bridge.stop()

    asyncio.run(_run())


def test_bridge_re_exported_job_status_helper():
    """normalize_from_job_status is reachable for downstream job-status bridges."""
    from app.video_runtime.runtime_event_bridge import normalize_from_job_status

    event = normalize_from_job_status(
        job_id="job-1",
        status="completed",
        provider="local-comfy",
        model_id="minimax-h3",
        created_at="2026-09-07T00:00:00Z",
    )
    assert event.eventType.value == "COMPLETED"
    assert event.jobId == "job-1"
