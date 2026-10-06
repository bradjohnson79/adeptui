"""P10 regression: sync cancel paths must POST /interrupt to Comfy when the
cancelled job owns the active prompt.

``JobQueue.cancel()`` only sets a cooperative flag a blocked native call (the
SenseNova ``from_pretrained`` loader) never checks, so the in-flight Comfy
prompt keeps running until host-RAM OOM. ``schedule_comfy_interrupt_if_owner``
fires ``POST /interrupt`` when the job owns the active prompt (and no sibling
is running), so a replaced/rejected draft's runtime job actually stops.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.queue_worker import job_queue, schedule_comfy_interrupt_if_owner


@pytest.fixture()
def _clear_active():
    job_queue._active_prompt.clear()
    job_queue._heavy_local_active = None
    yield
    job_queue._active_prompt.clear()
    job_queue._heavy_local_active = None


def test_returns_false_for_empty_job_id():
    assert schedule_comfy_interrupt_if_owner("") is False
    assert schedule_comfy_interrupt_if_owner("   ") is False


def test_does_not_interrupt_when_job_has_no_active_prompt(_clear_active):
    # No prompt bound for this job → nothing to interrupt.
    assert schedule_comfy_interrupt_if_owner("job-no-prompt") is False


def test_does_not_interrupt_when_a_sibling_owns_the_active_prompt(_clear_active):
    # Another job is running a prompt; interrupting would kill the sibling.
    job_queue._active_prompt["sibling"] = "prompt-sibling"
    job_queue._heavy_local_active = "sibling"
    assert schedule_comfy_interrupt_if_owner("job-leftover") is False


def test_interrupts_when_job_owns_the_active_prompt(_clear_active, monkeypatch):
    job_queue._active_prompt["job-stuck"] = "prompt-stuck"
    job_queue._heavy_local_active = "job-stuck"

    called: list[str] = []

    class _FakeComfy:
        async def interrupt(self) -> None:
            called.append("interrupt")

    # The helper imports comfy inside _do; patch the module-level comfy object.
    import app.comfy_client as comfy_client

    monkeypatch.setattr(comfy_client, "comfy", _FakeComfy())

    # Ensure the worker task is not running so the helper falls through to
    # asyncio.run(_do()) and executes synchronously within this test process.
    monkeypatch.setattr(job_queue, "_task", None)

    result = schedule_comfy_interrupt_if_owner("job-stuck")
    assert result is True
    assert called == ["interrupt"]


def test_best_effort_does_not_raise_when_comfy_unreachable(_clear_active, monkeypatch):
    job_queue._active_prompt["job-stuck"] = "prompt-stuck"
    job_queue._heavy_local_active = "job-stuck"

    class _BrokenComfy:
        async def interrupt(self) -> None:
            raise RuntimeError("comfy unreachable")

    import app.comfy_client as comfy_client

    monkeypatch.setattr(comfy_client, "comfy", _BrokenComfy())
    monkeypatch.setattr(job_queue, "_task", None)

    # Must not raise even though /interrupt fails.
    result = schedule_comfy_interrupt_if_owner("job-stuck")
    assert result is True
