"""GPU lease: Comfy :8188 /free, then idle Route A :8192 /free when Qwen still cannot fit."""

from __future__ import annotations

from app.codirector.video_intelligence import gpu_lease


def test_best_effort_free_generator_handoffs_idle_route_a(monkeypatch):
    vram = {"n": 0}

    def fake_vram():
        vram["n"] += 1
        # before, after Comfy /free, then wait_for_free_vram samples
        return {1: 0.8, 2: 0.8}.get(vram["n"], 28.4)

    seen = {"route_a": 0}

    def fake_route_a(*, timeout=10.0):
        seen["route_a"] += 1
        assert timeout >= 10.0
        return {"ok": True}

    class _Resp:
        status_code = 200

    monkeypatch.setattr(gpu_lease, "query_free_vram_gb", fake_vram)
    monkeypatch.setattr(gpu_lease, "_free_idle_route_a", lambda: fake_route_a(timeout=30.0))

    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())

    evidence = gpu_lease.best_effort_free_generator()
    assert evidence["comfyFreeRequested"] is True
    assert seen["route_a"] == 1
    assert evidence["vramAfterRouteAFreeGb"] == 28.4
    assert evidence["vramFullyReleased"] is True


def test_best_effort_free_generator_skips_route_a_when_qwen_already_fits(monkeypatch):
    monkeypatch.setattr(gpu_lease, "query_free_vram_gb", lambda: 24.0)

    def _boom():
        raise AssertionError("Route A must stay warm when Qwen already fits")

    monkeypatch.setattr(gpu_lease, "_free_idle_route_a", _boom)

    class _Resp:
        status_code = 200

    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())

    evidence = gpu_lease.best_effort_free_generator()
    assert "routeAFree" not in evidence
    assert evidence["vramAfterFreeGb"] == 24.0
    assert evidence["vramFullyReleased"] is True
