"""Regression: wait_for_prompt must return after Comfy success even if the
live-preview WebSocket task refuses to stop.

Job 98db381c stranded at writing_output/message=done/progress=0.96 because
wait_for_prompt's finally awaited a hung preview_task forever after emitting
the terminal progress event — finalize never ran.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_wait_for_prompt_returns_despite_hung_preview_cleanup(monkeypatch):
    from app import comfy_client
    from app.config import settings
    import app.video_runtime.live_preview as live_preview

    comfy = comfy_client.comfy
    prompt_id = "preview-hang-prompt"
    started = {"n": 0}
    polls = {"n": 0}

    async def fake_history(_pid):
        polls["n"] += 1
        # Stay incomplete for a couple polls so the preview task is scheduled.
        if polls["n"] < 3:
            return {}
        return {
            prompt_id: {
                "status": {"status_str": "success", "completed": True},
                "outputs": {},
            }
        }

    async def fake_queue():
        return {"queue_running": [["x", prompt_id]], "queue_pending": []}

    async def hung_preview(*_a, **_k):
        started["n"] += 1
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await asyncio.sleep(3600)

    monkeypatch.setattr(comfy, "get_history", fake_history)
    monkeypatch.setattr(comfy, "get_queue", fake_queue)
    monkeypatch.setattr(settings, "poll_interval_sec", 0.05, raising=False)
    monkeypatch.setattr(live_preview, "tap_comfy_previews", hung_preview)

    async def on_frame(_data: bytes) -> None:
        return None

    async def _run():
        return await asyncio.wait_for(
            comfy.wait_for_prompt(
                prompt_id,
                timeout_sec=5.0,
                on_preview_frame=on_frame,
            ),
            timeout=8.0,
        )

    t0 = time.monotonic()
    entry = asyncio.run(_run())
    elapsed = time.monotonic() - t0
    assert entry["status"]["status_str"] == "success"
    assert started["n"] == 1, "preview tap must start so finally cleanup is exercised"
    # Bounded cleanup (2.0s) must run; old code hung forever.
    assert 1.5 <= elapsed <= 7.0, f"expected ~2s bounded cleanup, got {elapsed:.2f}s"
