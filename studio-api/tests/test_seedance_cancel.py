"""Seedance adapter cancel wiring — mocked, no live spend."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.director_timeline_w46.generation.adapters import seedance_api as seedance_mod
from app.director_timeline_w46.generation.adapters.seedance_api import (
    Seedance25ApiAdapter,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.fal_client import FalApiError


@pytest.fixture
def live_submission(monkeypatch: pytest.MonkeyPatch) -> tuple:
    """Submit a live Seedance request without letting the background thread run."""
    monkeypatch.setattr(seedance_mod, "_run_live", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.secrets_store.get_secret", lambda name: "fal-key")

    req = TimelineGenerationRequest(
        projectId="beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        sceneId="scene-1",
        batchBlockId="batch-1",
        executionSnapshotId="snap-1",
        generatorId="seedance-2.5",
        prompt="cancel wiring test",
        duration=5,
    )
    adapter = Seedance25ApiAdapter()
    sub = adapter.submit(req)
    rec = seedance_mod._HOSTED_JOBS[sub.internalJobId]
    # Keep the record at a running-ish state for cancel tests.
    rec["status"] = "running"
    return adapter, sub, rec


def test_seedance_cancel_test_inject_still_works() -> None:
    """Existing regression/test path continues to mark cancelled locally."""
    req = TimelineGenerationRequest(
        projectId="beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        sceneId="scene-1",
        batchBlockId="batch-1",
        executionSnapshotId="snap-1",
        generatorId="seedance-2.5",
        prompt="cancel wiring test",
        duration=5,
        providerOptions={"testInjectResult": {"status": "running", "outputAssetIds": []}},
    )
    adapter = Seedance25ApiAdapter()
    sub = adapter.submit(req)
    adapter.cancel(sub)
    st = adapter.get_status(sub)
    assert st.status == "cancelled"


def test_seedance_cancel_live_calls_fal_cancel(live_submission: tuple) -> None:
    """A live record with captured request id triggers the remote cancel helper."""
    adapter, sub, rec = live_submission
    rec["falModelId"] = "bytedance/seedance-2.5/text-to-video"
    rec["falRequestId"] = "req-abc-123"
    rec["falCancelUrl"] = "https://queue.fal.run/seedance/requests/req-abc-123/cancel"

    cancel_results: list[dict] = []

    def fake_cancel(
        model_id: str,
        request_id: str,
        api_key: str,
        *,
        cancel_url: str | None,
        timeout_sec: float = 30.0,
    ) -> dict:
        cancel_results.append(
            {
                "model_id": model_id,
                "request_id": request_id,
                "api_key": api_key,
                "cancel_url": cancel_url,
            }
        )
        return {"status": "CANCELLATION_REQUESTED", "request_id": request_id}

    with patch("app.fal_client.cancel_fal_request", fake_cancel):
        adapter.cancel(sub)

    st = adapter.get_status(sub)
    assert st.status == "cancelled"
    assert len(cancel_results) == 1
    assert cancel_results[0]["model_id"] == rec["falModelId"]
    assert cancel_results[0]["request_id"] == rec["falRequestId"]
    assert cancel_results[0]["cancel_url"] == rec["falCancelUrl"]
    assert rec["falCancelResult"] == {"status": "CANCELLATION_REQUESTED", "request_id": "req-abc-123"}


def test_seedance_cancel_live_failure_records_rejected(live_submission: tuple) -> None:
    """If the remote cancel is rejected, the in-memory job stays running and records the reason."""
    adapter, sub, rec = live_submission
    rec["falModelId"] = "bytedance/seedance-2.5/text-to-video"
    rec["falRequestId"] = "req-abc-123"

    def fake_cancel(
        model_id: str,
        request_id: str,
        api_key: str,
        *,
        cancel_url: str | None,
        timeout_sec: float = 30.0,
    ) -> dict:
        raise FalApiError("fal cancel failed (404): not found")

    with patch("app.fal_client.cancel_fal_request", fake_cancel):
        adapter.cancel(sub)

    st = adapter.get_status(sub)
    assert st.status == "running"
    assert rec["cancelRejected"] is True
    assert rec["cancelReason"] == "PROVIDER_CANCEL_UNSUPPORTED"
    assert "fal cancel failed (404): not found" in rec["falCancelError"]


def test_seedance_cancel_live_no_request_id_records_rejected(live_submission: tuple) -> None:
    """If the fal request id has not been captured yet, reject rather than invent a cancel."""
    adapter, sub, rec = live_submission

    adapter.cancel(sub)

    st = adapter.get_status(sub)
    assert st.status == "running"
    assert rec["cancelRejected"] is True
    assert rec["cancelReason"] == "PROVIDER_CANCEL_UNSUPPORTED"


def test_seedance_cancel_live_no_api_key_records_rejected(live_submission: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials mean the cancel cannot be attempted; record rejected."""
    adapter, sub, rec = live_submission
    rec["falModelId"] = "bytedance/seedance-2.5/text-to-video"
    rec["falRequestId"] = "req-abc-123"

    monkeypatch.setattr("app.secrets_store.get_secret", lambda name: None)
    adapter.cancel(sub)

    assert rec["cancelRejected"] is True
    assert rec["cancelReason"] == "PROVIDER_CANCEL_UNSUPPORTED"
