"""P11 regression: a prompt Comfy no longer knows (not running, not pending,
not in history) must fast-fail as STALLED within a short grace period, NOT
poll for up to an hour (the old silent 1h hang).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_vanished_prompt_fast_fails_as_stalled(monkeypatch):
    from app import comfy_client
    from app.config import settings

    comfy = comfy_client.comfy

    # Prompt is nowhere: not in running, not in pending, not in history.
    async def fake_history(_pid):
        return {}

    async def fake_queue():
        return {"queue_running": [], "queue_pending": []}

    monkeypatch.setattr(comfy, "get_history", fake_history)
    monkeypatch.setattr(comfy, "get_queue", fake_queue)

    # Tiny poll interval + tiny timeout so vanish_limit_sec is small and the
    # test fails fast (vanish_limit_sec = min(15, timeout)).
    monkeypatch.setattr(settings, "poll_interval_sec", 0.001, raising=False)
    monkeypatch.setattr(settings, "job_timeout_sec", 0.05, raising=False)

    with pytest.raises(TimeoutError) as exc_info:
        asyncio.run(comfy.wait_for_prompt("vanished-prompt", timeout_sec=0.05))

    msg = str(exc_info.value)
    assert "STALLED" in msg
    assert "lost track of prompt" in msg


def test_prompt_still_in_queue_does_not_vanish_fail(monkeypatch):
    """A prompt that IS in the running queue must not trigger the vanished
    fast-fail (it is tracked, just not done yet)."""
    from app import comfy_client
    from app.config import settings

    comfy = comfy_client.comfy

    async def fake_history(_pid):
        return {}

    async def fake_queue():
        # Prompt is in the running queue → not vanished.
        return {"queue_running": [["x", "live-prompt"]], "queue_pending": []}

    monkeypatch.setattr(comfy, "get_history", fake_history)
    monkeypatch.setattr(comfy, "get_queue", fake_queue)
    monkeypatch.setattr(settings, "poll_interval_sec", 0.001, raising=False)
    monkeypatch.setattr(settings, "job_timeout_sec", 0.02, raising=False)

    with pytest.raises(TimeoutError) as exc_info:
        asyncio.run(comfy.wait_for_prompt("live-prompt", timeout_sec=0.02))

    # Should be the generic timeout (still running), NOT the vanished STALLED.
    msg = str(exc_info.value)
    assert "STALLED" not in msg
