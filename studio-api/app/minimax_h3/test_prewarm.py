"""Hermetic tests for MiniMax H3 opportunistic prewarm (app.minimax_h3.prewarm).

No live :8192, no GPU, no control plane — all HTTP/admission boundaries mocked.
"""

from __future__ import annotations

import app.minimax_h3.prewarm as pw


def _reset():
    pw._set(status="idle", promptId=None, clientId=None, startedAt=None,
            completedAt=None, reason=None)


def test_prewarm_refuses_when_route_a_busy(monkeypatch):
    _reset()
    monkeypatch.setattr(pw, "_gpu_blocked_by_comfy", lambda: None)
    monkeypatch.setattr(pw, "_route_a_queue_running", lambda base: 1)
    result = pw.start_prewarm()
    assert result["ok"] is False
    assert "render in progress" in result["message"]
    assert pw.prewarm_status()["status"] == "idle"


def test_prewarm_refuses_when_comfy_8188_rendering(monkeypatch):
    _reset()
    monkeypatch.setattr(pw, "_gpu_blocked_by_comfy",
                        lambda: "Comfy :8188 is rendering — prewarm would contend for the GPU")
    result = pw.start_prewarm()
    assert result["ok"] is False
    assert "8188" in result["message"]


def test_prewarm_submits_micro_render_graph(monkeypatch):
    _reset()
    monkeypatch.setattr(pw, "_gpu_blocked_by_comfy", lambda: None)
    monkeypatch.setattr(pw, "_route_a_queue_running", lambda base: 0)
    monkeypatch.setattr(pw, "_ensure_route_a", lambda base: (True, None))
    seen: dict = {}

    def fake_http(method, url, payload=None, timeout=30.0):
        seen["url"] = url
        seen["payload"] = payload
        return {"prompt_id": "pw-test-1"}

    monkeypatch.setattr(pw, "_http", fake_http)
    monkeypatch.setattr(pw, "_watch_completion", lambda base, pid: None)  # no thread
    # stop the real watcher thread from spawning
    import threading
    monkeypatch.setattr(threading, "Thread", lambda *a, **k: type("T", (), {"start": lambda s: None})())

    result = pw.start_prewarm()
    assert result["ok"] is True
    assert seen["url"].endswith(":8192/prompt") or "/prompt" in seen["url"]
    graph = seen["payload"]["prompt"]
    # micro-render must touch all four canonical H3 models
    loaders = [n for n in graph.values() if n.get("class_type") in ("UNETLoader", "CLIPLoader", "VAELoader")]
    assert len(loaders) == 4
    # 1-step, 5-frame micro render
    sched = next(n for n in graph.values() if n.get("class_type") == "BasicScheduler")
    assert sched["inputs"]["steps"] == 1
    assert pw.prewarm_status()["status"] == "loading"
    _reset()


def test_prewarm_idempotent_while_loading():
    pw._set(status="loading", promptId="pw-x")
    result = pw.start_prewarm()
    assert result["ok"] is True
    assert "already in flight" in result["message"]
    _reset()


def test_prewarm_warm_reverifies_with_probe(monkeypatch):
    """No stale 'warm' short-circuit: external /free eviction is invisible to module
    state, so an explicit selection always re-submits the cache-cheap micro-render
    as the truth probe (Build Law #6 — no fake readiness)."""
    pw._set(status="warm")
    monkeypatch.setattr(pw, "_gpu_blocked_by_comfy", lambda: None)
    monkeypatch.setattr(pw, "_route_a_queue_running", lambda base: 0)
    monkeypatch.setattr(pw, "_ensure_route_a", lambda base: (True, None))
    seen: dict = {}

    def fake_http(method, url, payload=None, timeout=30.0):
        seen["url"] = url
        return {"prompt_id": "pw-rewarm"}

    monkeypatch.setattr(pw, "_http", fake_http)
    import threading
    monkeypatch.setattr(threading, "Thread", lambda *a, **k: type("T", (), {"start": lambda s: None})())
    result = pw.start_prewarm()
    assert result["ok"] is True
    assert seen.get("url", "").endswith("/prompt"), "warm state must re-probe, not short-circuit"
    assert pw.prewarm_status()["status"] == "loading"
    _reset()


def test_cancel_prewarm_noop_when_idle():
    _reset()
    result = pw.cancel_prewarm()
    assert result["ok"] is True
    assert "no prewarm in flight" in result["message"]


def test_cancel_prewarm_interrupts_loading(monkeypatch):
    pw._set(status="loading", promptId="pw-9", clientId="c-9")
    calls: list[str] = []

    def fake_http(method, url, payload=None, timeout=30.0):
        calls.append(url)
        return {}

    monkeypatch.setattr(pw, "_http", fake_http)
    monkeypatch.setattr(pw, "_cleanup_outputs", lambda: None)
    result = pw.cancel_prewarm(reason="generator switched")
    assert result["ok"] is True
    assert any("/queue" in u for u in calls)
    assert any("/interrupt" in u for u in calls)
    assert pw.prewarm_status()["status"] == "cancelled"
    _reset()


def test_prewarm_reports_runtime_start_failure(monkeypatch):
    _reset()
    monkeypatch.setattr(pw, "_gpu_blocked_by_comfy", lambda: None)
    monkeypatch.setattr(pw, "_route_a_queue_running", lambda base: 0)
    monkeypatch.setattr(pw, "_ensure_route_a", lambda base: (False, "GPU admission refused"))
    result = pw.start_prewarm()
    assert result["ok"] is False
    assert "GPU admission refused" in result["message"]
    assert pw.prewarm_status()["status"] == "idle"
