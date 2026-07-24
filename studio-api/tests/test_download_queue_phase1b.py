"""Phase 1B download queue unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def isolated_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "studio-data"
    data.mkdir()
    monkeypatch.setenv("STUDIO_DATA_DIR", str(data))
    monkeypatch.setenv("ADEPT_PACK_PROVIDER", "fixture_http")
    monkeypatch.setenv("ADEPT_PACK_FIXTURE_BASE_URL", "http://127.0.0.1:8765")
    from app.config import settings

    settings.data_dir = data
    # Reset singleton queue manager between tests
    import app.source_manager.downloads.queue as queue_mod

    queue_mod._MANAGER = None
    yield data
    queue_mod._MANAGER = None


def test_phase_transitions_valid_and_invalid():
    from app.source_manager.downloads.phases import InvalidPhaseTransition, can_transition, transition

    assert can_transition("queued", "preflighting")
    assert transition("queued", "preflighting") == "preflighting"
    with pytest.raises(InvalidPhaseTransition):
        transition("queued", "installed")


def test_progress_speed_and_eta_smoothing():
    from app.source_manager.downloads.progress import ProgressTracker

    tracker = ProgressTracker(window_seconds=10, min_samples=3)
    tracker.set_total(1000)
    t = 100.0
    tracker.update(0, now=t)
    tracker.update(100, now=t + 1)
    snap = tracker.update(300, now=t + 2)
    assert snap["bytesDownloaded"] == 300
    assert snap["percent"] == 30.0
    # Enough samples for speed
    snap = tracker.update(500, now=t + 4)
    assert snap["speedBytesPerSecond"] is not None
    assert snap["etaSeconds"] is not None
    assert snap["etaSeconds"] >= 0


def test_progress_unknown_total_no_eta():
    from app.source_manager.downloads.progress import ProgressTracker

    tracker = ProgressTracker(min_samples=2)
    tracker.update(10, now=1)
    snap = tracker.update(100, now=2)
    assert snap["bytesTotal"] is None
    assert snap["etaSeconds"] is None


def test_disk_preflight_insufficient(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.source_manager.downloads import disk

    monkeypatch.setattr(disk, "free_bytes", lambda path: 100)
    result = disk.preflight_disk(
        tmp_path,
        download_bytes=1000,
        extracted_bytes=1000,
    )
    assert result["block"] is True
    assert result["state"] == "insufficient"


def test_queue_ordering_and_duplicate_prevention(isolated_data: Path):
    from app.source_manager.downloads.models import create_install_plan
    from app.source_manager.downloads.queue import get_queue_manager

    mgr = get_queue_manager()
    plan_a = create_install_plan(
        component_id="pack_essential_photoreal",
        source_id=None,
        provider_id="fixture",
        artifacts=[{"remotePath": "pack.zip", "expectedSize": 100}],
        destination_root=str(isolated_data / "a"),
        estimated_download_bytes=100,
    )
    plan_b = create_install_plan(
        component_id="pack_essential_anime",
        source_id=None,
        provider_id="fixture",
        artifacts=[{"remotePath": "pack.zip", "expectedSize": 100}],
        destination_root=str(isolated_data / "b"),
        estimated_download_bytes=100,
    )
    op1 = mgr.enqueue(plan_a, priority=50)
    op2 = mgr.enqueue(plan_b, priority=200)
    # Duplicate component returns same op
    again = mgr.enqueue(plan_a, priority=1)
    assert again["id"] == op1["id"]
    listed = mgr.list({"active": True})
    ids = [o["id"] for o in listed]
    assert op2["id"] in ids
    # Higher priority first among queued when both queued
    queued = [o for o in listed if o["phase"] == "queued"]
    if len(queued) >= 2:
        assert queued[0]["priority"] >= queued[1]["priority"]


def test_receipt_immutable(isolated_data: Path):
    from app.source_manager.downloads.receipts import build_managed_receipt, persist_receipt

    receipt = build_managed_receipt(
        operation={
            "id": "dl_test",
            "componentId": "pack_essential_photoreal",
            "installPlanId": "plan_x",
            "providerId": "fixture",
            "plan": {"sourceFingerprint": "abc"},
        },
        destination_root=isolated_data / "dest",
        files=[{"relativePath": "pack.json", "size": 10}],
    )
    persist_receipt(receipt)
    with pytest.raises(ValueError, match="immutable"):
        persist_receipt(receipt)


def test_secret_redaction_in_operation():
    from app.source_manager.downloads.models import create_install_plan, create_operation

    plan = create_install_plan(
        component_id="pack_essential_cinematic",
        source_id=None,
        provider_id="direct_http",
        artifacts=[{"remotePath": "a.bin", "downloadUrl": "https://example.com/a.bin"}],
        destination_root="/tmp/x",
        metadata={"token": "SECRET", "ok": True},
    )
    assert "token" not in (plan.get("metadata") or {})
    op = create_operation(plan)
    assert "token" not in str(op)


def test_pause_capability_false_for_fixture():
    from app.source_manager.downloads.executors.fixture import FixtureDownloadExecutor

    caps = FixtureDownloadExecutor().get_capabilities({"componentId": "pack_essential_photoreal"})
    assert caps.can_pause is False
    assert "not supported" in caps.message.lower()
