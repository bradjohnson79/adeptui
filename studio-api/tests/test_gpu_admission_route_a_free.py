"""Hermetic tests for Route A selective unload (gpu_admission.free_route_a_models
+ request_comfy_admission_with_route_a_handoff). No live ports, no GPU.
"""

from __future__ import annotations

import runtime_supervisor.gpu_admission as ga


def test_free_route_a_models_refuses_while_job_running(monkeypatch):
    monkeypatch.setattr(ga, "_route_a_healthy", lambda: True)
    monkeypatch.setattr(ga, "_route_a_queue_running", lambda: 1)
    result = ga.free_route_a_models()
    assert result["ok"] is False
    assert "active generation" in result["reason"]


def test_free_route_a_models_posts_free_when_idle(monkeypatch):
    monkeypatch.setattr(ga, "_route_a_healthy", lambda: True)
    monkeypatch.setattr(ga, "_route_a_queue_running", lambda: 0)
    seen: dict = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["body"] = req.data
        return _Resp()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = ga.free_route_a_models()
    assert result["ok"] is True
    assert seen["url"].endswith(":8192/free")
    assert b"unload_models" in seen["body"]


def test_free_route_a_models_ok_when_down(monkeypatch):
    monkeypatch.setattr(ga, "_route_a_healthy", lambda: False)
    assert ga.free_route_a_models()["ok"] is True


def test_comfy_admission_handoff_frees_idle_route_a(monkeypatch):
    monkeypatch.setattr(
        ga,
        "assess_gpu_admission",
        lambda who: {"allowed": False, "action": "handoff_required"},
    )
    freed = []
    monkeypatch.setattr(ga, "free_route_a_models", lambda: freed.append(1) or {"ok": True})
    result = ga.request_comfy_admission_with_route_a_handoff()
    assert result["allowed"] is True
    assert result["action"] == "start_after_handoff"
    assert freed, "expected Route A /free to be requested"


def test_comfy_admission_handoff_failure_blocks(monkeypatch):
    monkeypatch.setattr(
        ga,
        "assess_gpu_admission",
        lambda who: {"allowed": False, "action": "handoff_required"},
    )
    monkeypatch.setattr(ga, "free_route_a_models", lambda: {"ok": False, "reason": "busy"})
    result = ga.request_comfy_admission_with_route_a_handoff()
    assert result["allowed"] is False
    assert result["action"] == "handoff_failed"


def test_comfy_admission_passthrough_when_allowed(monkeypatch):
    monkeypatch.setattr(
        ga,
        "assess_gpu_admission",
        lambda who: {"allowed": True, "action": "reuse"},
    )
    result = ga.request_comfy_admission_with_route_a_handoff()
    assert result == {"allowed": True, "action": "reuse"}
