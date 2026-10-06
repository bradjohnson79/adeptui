"""Wave 3B — Comfy stall watchdog: no early fail while Comfy still running."""
from __future__ import annotations

import asyncio

import pytest

from app.comfy_client import (
    PROMPT_GONE_GRACE_SEC,
    RUNNING_WITHOUT_HISTORY_STALL_SEC,
    ComfyClient,
)


def test_wave3b_stall_constant_aligns_with_job_wall_not_900():
    assert RUNNING_WITHOUT_HISTORY_STALL_SEC >= 3600.0
    assert PROMPT_GONE_GRACE_SEC > 0
    assert PROMPT_GONE_GRACE_SEC < 900.0


async def _noop_sleep(*_a, **_k):
    return None


async def _noop_listen(self, prompt_id, live, stop):
    await stop.wait()


def test_wave3b_queue_running_past_900s_does_not_stall(monkeypatch):
    """While Comfy still has the prompt in queue_running, do not fail at 900s."""
    client = ComfyClient("http://127.0.0.1:8188")
    prompt_id = "prompt-live"

    monkeypatch.setattr("app.comfy_client.settings.poll_interval_sec", 100.0)
    monkeypatch.setattr("app.comfy_client.asyncio.sleep", _noop_sleep)
    monkeypatch.setattr(ComfyClient, "_listen_comfy_progress", _noop_listen)

    async def _run():
        from app.video_runtime.progress import ProgressNormalizer

        history_after = {"n": 0}

        async def get_history(_pid):
            history_after["n"] += 1
            if history_after["n"] >= 10:
                return {
                    prompt_id: {
                        "status": {"completed": True, "status_str": "success"},
                        "outputs": {},
                    }
                }
            return {}

        async def get_queue():
            return {"queue_running": [[0, prompt_id]], "queue_pending": []}

        monkeypatch.setattr(client, "get_history", get_history)
        monkeypatch.setattr(client, "get_queue", get_queue)

        return await client._wait_for_prompt_poll(
            prompt_id,
            timeout=3600.0,
            elapsed=0.0,
            normalizer=ProgressNormalizer(),
            running_without_history_sec=850.0,
            stall_limit_sec=min(RUNNING_WITHOUT_HISTORY_STALL_SEC, 3600.0),
            prompt_gone_sec=0.0,
            on_progress=None,
            cancel_check=None,
        )

    entry = asyncio.run(_run())
    assert entry["status"]["completed"] is True


def test_wave3b_prompt_gone_fails_after_grace(monkeypatch):
    client = ComfyClient("http://127.0.0.1:8188")
    prompt_id = "prompt-gone"
    monkeypatch.setattr("app.comfy_client.settings.poll_interval_sec", 20.0)
    monkeypatch.setattr("app.comfy_client.asyncio.sleep", _noop_sleep)
    monkeypatch.setattr("app.comfy_client.PROMPT_GONE_GRACE_SEC", 40.0)
    monkeypatch.setattr(ComfyClient, "_listen_comfy_progress", _noop_listen)

    async def get_history(_pid):
        return {}

    async def get_queue():
        return {"queue_running": [], "queue_pending": []}

    monkeypatch.setattr(client, "get_history", get_history)
    monkeypatch.setattr(client, "get_queue", get_queue)

    from app.video_runtime.progress import ProgressNormalizer

    async def _run():
        return await client._wait_for_prompt_poll(
            prompt_id,
            timeout=3600.0,
            elapsed=0.0,
            normalizer=ProgressNormalizer(),
            running_without_history_sec=0.0,
            stall_limit_sec=RUNNING_WITHOUT_HISTORY_STALL_SEC,
            prompt_gone_sec=0.0,
            on_progress=None,
            cancel_check=None,
        )

    with pytest.raises(TimeoutError, match="prompt gone"):
        asyncio.run(_run())
