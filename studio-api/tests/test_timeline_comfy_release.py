"""Timeline unloads Comfy VRAM/cache after each generation — not a restart."""

from __future__ import annotations

from app.codirector.video_intelligence.gpu_lease import reset_handoff_state
from app.director_timeline_w46.generation.comfy_release import release_comfy_after_timeline_generation


def setup_function():
    reset_handoff_state()


def test_release_comfy_posts_unload_and_free(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class _Resp:
        status_code = 200

    def _post(url, json=None, timeout=None):
        calls.append((url, dict(json or {})))
        return _Resp()

    monkeypatch.setattr("httpx.post", _post)
    evidence = release_comfy_after_timeline_generation(reason="timeline-batch-complete:bb_test")
    assert evidence["ok"] is True
    assert evidence["comfyFreeRequested"] is True
    assert calls
    url, payload = calls[0]
    assert url.endswith("/free")
    assert payload == {"unload_models": True, "free_memory": True}


def test_release_comfy_never_raises(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("comfy down")

    monkeypatch.setattr("httpx.post", _boom)
    evidence = release_comfy_after_timeline_generation(reason="timeline-batch-fail:bb_test")
    assert evidence["ok"] is False
    assert "comfyFreeError" in evidence
