"""Bound-scene production Temporal Continuity Status check + InternVideo3 skip."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.codirector.status.registry import StatusContext, _probe_temporal_continuity
from app.codirector.status.weighting import summarize_results
from app.codirector.status.types import HealthCheckResult
from app.codirector.video_intelligence.contracts import (
    CoDirectorContinuityPolicy,
    TemporalContinuityPacket,
    VideoPerceptionObservation,
)
from app.codirector.video_intelligence.service import review_completed_batch
from app.director_timeline_w46.contracts import (
    ApprovedClip,
    BatchBlock,
    DurationState,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.readiness.v11_policy import ReadinessClass


def _master(*, packets=None, completed=2) -> SceneTimelineMaster:
    first = BatchBlock(
        id="bb_a",
        sceneId="s1",
        order=0,
        status="Approved",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0, generatedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="Walk.")],
        approvedClip=ApprovedClip(assetId="asset_a", executionSnapshotId="snap_a") if completed else None,
    )
    second = BatchBlock(
        id="bb_b",
        sceneId="s1",
        order=1,
        status="Approved" if completed >= 2 else "Queued",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0, generatedDuration=5.0 if completed >= 2 else None),
        promptSegments=[TimelinePromptSegment(text="Continue.")],
        approvedClip=ApprovedClip(assetId="asset_b", executionSnapshotId="snap_b") if completed >= 2 else None,
    )
    return SceneTimelineMaster(batchBlocks=[first, second], temporalPackets=list(packets or []))


def _ctx() -> StatusContext:
    return StatusContext(db=None, project_id="proj-1", scene_id="scene-1")  # type: ignore[arg-type]


def test_probe_not_applicable_without_completed_take(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.director_timeline_w46.service.load_timeline_bundle",
        lambda *_a, **_k: {"ok": True, "master": _master(completed=0)},
    )
    result = asyncio.run(_probe_temporal_continuity(_ctx()))
    assert result["status"] == "not_applicable"
    assert result["readinessClass"] == "advisory_review_degraded"


def test_probe_healthy_when_production_packet_ready(monkeypatch) -> None:
    packet = TemporalContinuityPacket(
        availability="ready",
        packetId="tcp_prod_ready",
        source={"batchId": "bb_a", "targetBatchId": "bb_b", "perceptionModelId": "videochat3-4b"},
    )
    cert = TemporalContinuityPacket(
        availability="ready",
        packetId="tcp_cert",
        source={"batchId": "bb_a", "targetBatchId": "vi95_cert_probe"},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.service.load_timeline_bundle",
        lambda *_a, **_k: {"ok": True, "master": _master(packets=[cert, packet])},
    )
    result = asyncio.run(_probe_temporal_continuity(_ctx()))
    assert result["status"] == "healthy"
    assert result["details"]["packetId"] == "tcp_prod_ready"
    assert result["details"]["certProbeExcluded"] is True
    assert result["readinessClass"] == "advisory_review_degraded"
    assert not result.get("warnings")


def test_probe_warns_when_production_packet_unavailable(monkeypatch) -> None:
    packet = TemporalContinuityPacket(
        availability="unavailable",
        reason="SOURCE_VIDEO_MISSING",
        packetId="tcp_stale",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.service.load_timeline_bundle",
        lambda *_a, **_k: {"ok": True, "master": _master(packets=[packet])},
    )
    result = asyncio.run(_probe_temporal_continuity(_ctx()))
    assert result["status"] == "warning"
    assert result["details"]["packetId"] == "tcp_stale"
    assert result["readinessClass"] == "advisory_review_degraded"


def test_advisory_warning_does_not_block_or_cap_84() -> None:
    results = [
        HealthCheckResult(
            checkId="api.health",
            title="api",
            category="core",
            criticality="critical",
            status="healthy",
            score=100,
            summary="ok",
            checkedAt="2026-09-14T00:00:00+00:00",
        ),
        HealthCheckResult(
            checkId="codirector.temporal_continuity",
            title="Temporal Continuity Handoff",
            category="integration",
            criticality="standard",
            status="warning",
            score=64,
            summary="handoff unavailable",
            checkedAt="2026-09-14T00:00:00+00:00",
            readinessClass=ReadinessClass.ADVISORY_REVIEW_DEGRADED.value,
        ),
    ]
    summary, _cats, _explain = summarize_results(results, "standard")
    assert summary.statusIndicator == "Operational"
    assert summary.score <= 94
    assert summary.score >= 85
    assert summary.blockedChecks == 0


def test_missing_internvideo3_skips_without_failing_packet(monkeypatch, tmp_path) -> None:
    video = tmp_path / "take.mp4"
    video.write_bytes(b"not-a-real-mp4")
    master = _master(completed=2)
    master.coDirectorContinuityPolicy = CoDirectorContinuityPolicy(deepReview="on", fastVisionModel="videochat3-4b")

    observation = VideoPerceptionObservation(
        modelId="videochat3-4b",
        rawText="Walking continues.",
        unfinishedActions=[],
        completedActions=["walking"],
        confidence=0.8,
        parseOk=True,
    )

    def _perception(_path, model_id="videochat3-4b", **_k):
        assert "internvideo" not in model_id
        return observation

    monkeypatch.setenv("ADEPT_TEMPORAL_PERCEPTION_MODE", "live")
    monkeypatch.setattr("app.codirector.video_intelligence.service._batch_video_path", lambda *_a, **_k: str(video))
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.best_effort_free_generator",
        lambda: {"comfyFreeRequested": True, "comfyFreeStatus": 200, "vramAfterFreeGb": 20.0},
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.preflight_for_review",
        lambda: {"ok": True, "freeVramGb": 20.0, "unknownVram": False},
    )
    monkeypatch.setattr("app.codirector.video_intelligence.service._internvideo3_available", lambda: False)
    monkeypatch.setattr("app.codirector.video_intelligence.service.run_perception", _perception)

    packet = review_completed_batch(None, "p1", "s1", master, master.batchBlocks[0], target_batch_id="bb_b")
    assert packet.availability == "ready"
    assert packet.source.deepReviewInvoked is False
    assert packet.extras.get("deepReviewSkipped", {}).get("reason") == "INTERNVIDEO3_NOT_INSTALLED"
    assert packet.reason != "MODEL_NOT_INSTALLED"


def test_source_video_missing_packet_is_retried_when_take_exists(monkeypatch, tmp_path) -> None:
    video = tmp_path / "take.mp4"
    video.write_bytes(b"not-a-real-mp4")
    master = _master(completed=2)
    stale = TemporalContinuityPacket(
        availability="unavailable",
        reason="SOURCE_VIDEO_MISSING",
        source={"batchId": "bb_a", "targetBatchId": "bb_b"},
    )
    master.temporalPackets = [stale]
    observation = VideoPerceptionObservation(
        modelId="videochat3-4b",
        rawText="Walking continues.",
        unfinishedActions=[],
        completedActions=["walking"],
        confidence=0.7,
        parseOk=True,
    )
    monkeypatch.setenv("ADEPT_TEMPORAL_PERCEPTION_MODE", "live")
    monkeypatch.setattr("app.codirector.video_intelligence.service._batch_video_path", lambda *_a, **_k: str(video))
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.best_effort_free_generator",
        lambda: {"comfyFreeRequested": True, "comfyFreeStatus": 200, "vramAfterFreeGb": 20.0},
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.preflight_for_review",
        lambda: {"ok": True, "freeVramGb": 20.0, "unknownVram": False},
    )
    monkeypatch.setattr("app.codirector.video_intelligence.service._internvideo3_available", lambda: False)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service.run_perception",
        lambda *_a, **_k: observation,
    )
    packet = review_completed_batch(None, "p1", "s1", master, master.batchBlocks[0], target_batch_id="bb_b")
    assert packet.packetId != stale.packetId
    assert packet.availability == "ready"
