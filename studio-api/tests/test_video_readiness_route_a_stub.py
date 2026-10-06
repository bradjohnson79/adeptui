"""Stub :8192 must not block Desktop Comfy LTX admission."""

from __future__ import annotations

import json

import app.production_control.video_readiness as vr


class _Resp:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_stub8192_is_not_vram_resident(monkeypatch):
    def fake_urlopen(url, timeout=3):
        assert "8192" in str(url)
        return _Resp({"system": {"comfyui_version": "stub"}, "devices": []})

    monkeypatch.setattr(vr.urllib.request, "urlopen", fake_urlopen)
    assert vr._route_a_listener_up() is True
    assert vr._route_a_vram_resident() is False


def test_real_route_a_with_device_is_vram_resident(monkeypatch):
    def fake_urlopen(url, timeout=3):
        return _Resp(
            {
                "system": {"comfyui_version": "0.3.0"},
                "devices": [{"name": "cuda:0", "type": "cuda"}],
            }
        )

    monkeypatch.setattr(vr.urllib.request, "urlopen", fake_urlopen)
    assert vr._route_a_vram_resident() is True


def test_desktop_ltx_admission_blocks_only_real_route_a(monkeypatch):
    vr._fact_cache.clear()
    monkeypatch.setattr(vr, "_route_a_vram_resident", lambda: True)
    monkeypatch.setattr(vr, "_comfy_health", lambda: {"ok": True, "vram_total": 32 * (1024**3)})
    monkeypatch.setattr(vr, "_comfy_nodes", lambda: {"LTXVImgToVideo"})
    monkeypatch.setattr(vr, "_verify_components", lambda _c: (True, ""))
    monkeypatch.setattr(vr, "_adapter_registered", lambda _a: True)
    facts = vr.collect_video_facts("ltx-2.5-distilled", locality="local")
    assert facts.admission_ok is False
    assert "Route A is resident" in (facts.admission_reason or "")

    vr._fact_cache.clear()
    monkeypatch.setattr(vr, "_route_a_vram_resident", lambda: False)
    facts2 = vr.collect_video_facts("ltx-2.5-distilled", locality="local")
    assert facts2.admission_ok is not False
