"""Comfy health flap: transient miss must not report offline / Blocked 35."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
import httpx

from app.comfy_health import classify_comfy_probe_error, comfy_health_fast
from app.codirector.status import runner
from app.codirector.status.probe_context import remember_healthy
from app.codirector.status.registry import StatusContext, _probe_comfy


def test_classify_refused_vs_transient() -> None:
    assert classify_comfy_probe_error(ConnectionRefusedError("connection refused")) == "refused"
    assert classify_comfy_probe_error(httpx.ConnectError("Connection refused")) == "refused"
    assert classify_comfy_probe_error(httpx.ConnectError("Connection reset by peer")) == "transient"
    assert classify_comfy_probe_error(asyncio.TimeoutError()) == "timeout"


def test_comfy_health_fast_retries_transient_then_succeeds(monkeypatch) -> None:
    calls = {"n": 0}

    async def _once(_timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("Connection reset by peer")
        return {"system": {"comfyui_version": "0.3.0"}, "devices": [{"name": "GPU", "type": "cuda", "vram_total": 1, "vram_free": 1}]}

    monkeypatch.setattr("app.comfy_health._system_stats_once", _once)
    payload = asyncio.run(comfy_health_fast(timeout_sec=0.2))
    assert payload["reachable"] is True
    assert payload["status"] == "ready"
    assert payload["transientRetry"] is True
    assert payload["attempts"] == 2
    assert payload["trueDeath"] is False


def test_comfy_health_fast_true_death_stays_unreachable(monkeypatch) -> None:
    async def _once(_timeout):
        raise httpx.ConnectError("No connection could be made because the target machine actively refused it")

    monkeypatch.setattr("app.comfy_health._system_stats_once", _once)
    monkeypatch.setattr("app.comfy_health.comfy_port_listening", lambda url=None: False)
    payload = asyncio.run(comfy_health_fast(timeout_sec=0.2))
    assert payload["reachable"] is False
    assert payload["trueDeath"] is True
    assert payload["connectionRefused"] is True
    assert payload["status"] == "unreachable"
    assert payload.get("timeout") is False


def test_probe_comfy_transient_with_lkg_is_not_offline(monkeypatch) -> None:
    remember_healthy("comfy.health", "ComfyUI is reachable and GPU is available.")
    payload = {
        "reachable": False,
        "status": "unreachable",
        "timeout": False,
        "trueDeath": False,
        "listenerPresent": True,
        "errorKind": "transient",
        "message": "ComfyUI is not reachable at http://127.0.0.1:8188.",
    }

    async def _fast(*, timeout_sec=4.0):
        return payload

    monkeypatch.setattr("app.comfy_health.comfy_health_fast", _fast)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.gpu_lease.comfy_generation_active",
        lambda: {"active": False},
    )
    ctx = StatusContext(db=None, mode="standard")  # type: ignore[arg-type]
    ctx.shared = SimpleNamespace(comfy_health=None)
    result = asyncio.run(_probe_comfy(ctx))
    assert result["status"] != "offline"
    assert result["status"] == "healthy"
    assert not result.get("blockers")


def test_probe_comfy_true_death_is_offline(monkeypatch) -> None:
    payload = {
        "reachable": False,
        "status": "unreachable",
        "timeout": False,
        "trueDeath": True,
        "listenerPresent": False,
        "connectionRefused": True,
        "errorKind": "refused",
        "message": "ComfyUI is not reachable at http://127.0.0.1:8188.",
    }

    async def _fast(*, timeout_sec=4.0):
        return payload

    monkeypatch.setattr("app.comfy_health.comfy_health_fast", _fast)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.gpu_lease.comfy_generation_active",
        lambda: {"active": False},
    )
    ctx = StatusContext(db=None, mode="standard")  # type: ignore[arg-type]
    ctx.shared = SimpleNamespace(comfy_health=None)
    result = asyncio.run(_probe_comfy(ctx))
    assert result["status"] == "offline"
    assert result["blockers"]


def test_runner_lkg_rescues_comfy_offline_without_true_death(monkeypatch) -> None:
    remember_healthy("comfy.health", "ok")

    async def _offline(_check_id, _ctx):
        return {
            "status": "offline",
            "summary": "ComfyUI is offline.",
            "message": "unreachable",
            "details": {
                "trueDeath": False,
                "listenerPresent": True,
                "errorKind": "transient",
            },
            "blockers": ["unreachable"],
            "warnings": [],
            "recoveryActions": [],
        }

    monkeypatch.setattr("app.codirector.status.runner.run_probe", _offline)
    result = asyncio.run(
        runner._execute_one(
            StatusContext(db=None, project_id="proj-1"),  # type: ignore[arg-type]
            "comfy.health",
            8.0,
        )
    )
    assert result.status != "offline"
    assert result.status == "healthy"
    assert result.timedOut is False
    assert result.details.get("lastKnownGood") is True
