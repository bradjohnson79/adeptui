"""Cold-lock un-wedge: single-flight snapshot, shielded wait_for, last-good/unknown.

Proves:
- concurrent snapshot callers share one in-flight build
- wait_for timeout does not cancel the shared Task
- timeout/miss returns last-good or unknown, never Ready
Also: persist=False must not clear Setup's 30s _STATUS_CACHE.
"""

from __future__ import annotations

import asyncio
import time
from copy import deepcopy

import pytest


@pytest.fixture(autouse=True)
def _reset_capability_flight():
    from app.capabilities import service

    service.invalidate_cache()
    for task in list(service._inflight.values()):
        task.cancel()
    service._inflight.clear()
    yield
    service.invalidate_cache()
    for task in list(service._inflight.values()):
        task.cancel()
    service._inflight.clear()


_READY_STATUSES = frozenset(
    {
        "ready",
        "runtime ready",
        "runtime_ready",
        "locally_verified",
        "production_ready",
    }
)


def _clear_inflight():
    from app.capabilities import service

    for task in list(service._inflight.values()):
        task.cancel()
    service._inflight.clear()
    service.invalidate_cache()


def test_cold_lock_single_flight_shield_and_last_good_never_ready(monkeypatch) -> None:
    from app.capabilities import service
    from app.capabilities.probes import ProbeSnapshot
    from app.codirector.tools.capabilities import CapabilityAdapter
    from app.codirector.tools import capability_bridge as bridge_mod
    from app.codirector.tools.capability_bridge import CoDirectorCapabilityBridge

    monkeypatch.setattr(bridge_mod, "_SNAPSHOT_TIMEOUT_SEC", 0.05)

    calls = {"n": 0}

    async def slow_build(*, project_id=None):
        calls["n"] += 1
        await asyncio.sleep(0.35)
        return ProbeSnapshot(
            project_id=project_id,
            checked_at="1999-01-01T00:00:00+00:00",
            correlation_id="built-after-wait",
        )

    monkeypatch.setattr(service, "build_snapshot", slow_build)

    async def main() -> None:
        # --- concurrent callers share ONE in-flight build ---
        gathered = asyncio.gather(
            service._get_snapshot(project_id=None, force=False),
            service._get_snapshot(project_id=None, force=False),
            service._get_snapshot(project_id=None, force=False),
        )
        await asyncio.sleep(0.05)
        assert calls["n"] == 1
        inflight = [task for task in service._inflight.values() if not task.done()]
        assert len(inflight) == 1
        shared = inflight[0]

        # --- wait_for timeout must not cancel the shared Task ---
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(shared), timeout=0.05)
        assert not shared.cancelled()
        assert not shared.done()
        assert calls["n"] == 1

        probes = await gathered
        assert calls["n"] == 1
        assert probes[0] is probes[1] is probes[2]
        assert shared.done()
        assert not shared.cancelled()

        # --- miss/timeout: unknown, never Ready ---
        _clear_inflight()
        adapter = CapabilityAdapter(db=None, project_id=None)  # type: ignore[arg-type]
        states = await adapter.snapshot()
        assert calls["n"] == 2
        inflight2 = [task for task in service._inflight.values() if not task.done()]
        assert len(inflight2) == 1
        assert not inflight2[0].cancelled()
        comfy = states["comfyui"]
        assert comfy.available is False
        assert comfy.status.lower() not in _READY_STATUSES
        assert comfy.status in {"unknown", "unavailable", "checking"}
        raw = await adapter.bridge.readiness_for_tool_key("comfyui")
        assert raw["available"] is False
        assert raw["status"].lower() not in _READY_STATUSES
        assert raw["status"] in {"unknown", "unavailable", "checking"}
        # Let the shielded build finish so it does not leak into last-good.
        await inflight2[0]
        assert not inflight2[0].cancelled()
        assert calls["n"] == 2

        # --- last-good on timeout: stale cache, never invent Ready ---
        last_good = ProbeSnapshot(
            checked_at="2000-01-01T00:00:00+00:00",
            correlation_id="last-good-sentinel",
        )
        service._store_slot("__global__", last_good)
        snap, _ts = service._cache["_slots"]["__global__"]
        service._cache["_slots"]["__global__"] = (
            snap,
            time.monotonic() - service.SNAPSHOT_TTL_SEC - 10,
        )
        # Drop completed inflight so the stale miss starts exactly one refresh.
        service._inflight.clear()

        bridge = CoDirectorCapabilityBridge(db=None, project_id=None)  # type: ignore[arg-type]
        miss_or_good = await bridge.readiness_for_tool_key("provider")
        assert calls["n"] == 3
        assert miss_or_good["available"] is False
        assert miss_or_good["status"].lower() not in _READY_STATUSES
        assert bridge._snapshot is not None
        assert bridge._snapshot.correlationId == "last-good-sentinel"
        inflight3 = [task for task in service._inflight.values() if not task.done()]
        assert len(inflight3) == 1
        assert not inflight3[0].cancelled()
        await inflight3[0]
        assert calls["n"] == 3

    asyncio.run(main())


def test_persist_false_does_not_clear_status_cache(monkeypatch) -> None:
    from app.setup import status
    from app.setup.diagnostics import Verification

    seeded = {"overall_status": "ready", "sentinel": "keep-me"}
    status._STATUS_CACHE = (time.monotonic(), deepcopy(seeded))
    held = status._STATUS_CACHE

    monkeypatch.setattr(
        status,
        "verify_component",
        lambda component_id, state=None: Verification(True, False, None, "ok", version="1"),
    )

    status.build_status(persist=False)
    assert status._STATUS_CACHE is held
    assert status._STATUS_CACHE[1]["sentinel"] == "keep-me"
