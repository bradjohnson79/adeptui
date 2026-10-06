"""Regression: Route A poll must finalize even when on_wait blocks."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.minimax_h3.route_a_adapter import RouteAJobState, RouteARuntimeAdapter


class _FakeResp:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def test_poll_completes_despite_blocking_on_wait(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """BOT B hang class: blocked heartbeat must not prevent history finalize."""
    adapter = RouteARuntimeAdapter(base_url="http://127.0.0.1:8192")
    mp4 = tmp_path / "out.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    prompt_id = "5854f852-test-prompt"
    history_payload = {
        prompt_id: {
            "status": {"status_str": "success", "completed": True},
            "outputs": {
                "14": {
                    "images": [
                        {"filename": mp4.name, "subfolder": "", "type": "output"}
                    ]
                }
            },
        }
    }

    calls = {"n": 0}

    def fake_get(url: str, timeout: Any = None) -> _FakeResp:
        assert "/history/" in str(url)
        calls["n"] += 1
        # First observation empty (Comfy still running); then success.
        if calls["n"] == 1:
            return _FakeResp({})
        return _FakeResp(history_payload)

    adapter._session = MagicMock()
    adapter._session.get.side_effect = fake_get

    monkeypatch.setattr(
        "app.minimax_h3.route_a_adapter.finalize_h3_colorspace_passthrough",
        lambda path: (Path(path), {"applied": False, "remux": "removed"}),
    )
    monkeypatch.setattr(
        "app.minimax_h3.route_a_adapter.validate_media",
        lambda path: {
            "ok": True,
            "path": str(path),
            "width": 960,
            "height": 544,
            "frameCount": 124,
            "videoCodec": "h264",
            "audioCodec": "aac",
            "audioSampleRate": 32000,
            "audioChannels": 2,
            "durationSeconds": 5.166,
            "sizeBytes": 1000,
            "container": "mp4",
        },
    )
    monkeypatch.setattr(
        adapter,
        "_resolve_output_file",
        lambda filename, subfolder: mp4 if filename == mp4.name else None,
    )
    monkeypatch.setattr(adapter, "_persist_job", lambda state: None)

    state = RouteAJobState(
        job_id="2d6920be-test",
        project_id="proj",
        plan_id="plan",
        prompt="motion",
        seed=1,
        prompt_id=prompt_id,
        status="running",
        stage="Generating",
        started_at=time.time(),
        mode="one-frame",
    )

    blocked = {"entered": False}

    def blocking_on_wait(elapsed: float) -> None:
        blocked["entered"] = True
        time.sleep(60)  # would hang the old poll forever

    t0 = time.time()
    out = adapter.poll(state, timeout_sec=30.0, on_wait=blocking_on_wait)
    elapsed = time.time() - t0

    assert blocked["entered"] is True
    assert out.status == "completed", out.error_message
    assert out.output_path == str(mp4)
    assert elapsed < 25.0, f"poll took too long ({elapsed:.1f}s) — on_wait likely unbounded"
    assert calls["n"] >= 2
