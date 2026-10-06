"""Canonical GeneratorRuntimeEvent contract — no live runtimes."""

from __future__ import annotations

from app.director_timeline_w46.generation.contracts import VideoGeneratorCapabilities
from app.preview_bus import preview_bus
from app.video_runtime.runtime_events import (
    GeneratorEventType,
    honest_progress_percent,
    normalize_from_job_status,
    normalize_from_preview,
)


def test_honest_progress_rejects_coarse_buckets():
    assert honest_progress_percent(0.25) is None
    assert honest_progress_percent(0.55) is None
    assert honest_progress_percent(0.9) is None
    assert honest_progress_percent(0.42) == 42
    assert honest_progress_percent(100) == 100


def test_preview_normalization_requires_job_id():
    try:
        normalize_from_preview(
            {"mediaType": "image", "sequenceNumber": 1},
            provider="local-comfy",
            model_id="minimax-h3",
            created_at="2026-09-07T00:00:00Z",
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "jobId" in str(exc)


def test_h3_preview_frame_maps_to_preview_event():
    event = normalize_from_preview(
        {
            "jobId": "job-1",
            "stage": "live_preview",
            "sequenceNumber": 3,
            "mediaType": "image",
            "localPath": "preview_cache/job-1/preview_abc.jpg",
            "createdAt": "2026-09-07T00:00:00Z",
            "progress": 0.47,
        },
        provider="local-comfy",
        model_id="minimax-h3",
        created_at="2026-09-07T00:00:00Z",
    )
    assert event.eventType == GeneratorEventType.PREVIEW_FRAME
    assert event.preview and event.preview.sequence == 3
    assert event.preview.draft is True
    assert event.progressPercent == 47


def test_hosted_status_maps_cancel_rejected_and_hides_coarse_progress():
    event = normalize_from_job_status(
        job_id="job-hosted",
        status="cancel_rejected",
        stage="running",
        provider="fal",
        model_id="seedance-2.5",
        created_at="2026-09-07T00:00:00Z",
        progress=0.25,
        cancel_reason="PROVIDER_CANCEL_UNSUPPORTED",
    )
    assert event.eventType == GeneratorEventType.CANCEL_REJECTED
    assert event.progressPercent is None
    assert event.cancelReason == "PROVIDER_CANCEL_UNSUPPORTED"


def test_local_live_pathway_implies_preview_flags():
    caps = VideoGeneratorCapabilities(
        id="ltx-local",
        label="LTX",
        draftPathway="local_live",
        supportsQueuedCancel=True,
        supportsRunningCancel=True,
    )
    assert caps.supportsLivePreview is True
    assert caps.supportsHonestProgress is True
    assert caps.supportsIntermediateFrames is True


def test_seedance_does_not_imply_preview_or_cancel():
    caps = VideoGeneratorCapabilities(
        id="seedance-2.5",
        label="Seedance 2.5",
        executionType="api",
        draftPathway="cheap_preview",
        supportsQueuedCancel=False,
        supportsRunningCancel=False,
    )
    assert caps.supportsLivePreview is False
    assert caps.supportsHonestProgress is False
    assert caps.remoteCancelCostNote is None


def test_fal_engine_caps_do_not_claim_thumbnail_or_progress():
    caps = preview_bus.capabilities_for("fal_seedance")
    assert caps["supportsLivePreview"] is False
    assert caps["previewMode"] is None
    assert caps["supportsPreviewProgress"] is False
    assert caps["supportsPreviewStreaming"] is False
