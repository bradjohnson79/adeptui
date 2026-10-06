"""PoseCraft attach must skip when continuityStrategy=none or temporal rejected."""

from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline_w46.generation.request_builder import _compile_pose_conditioning


class _Caps:
    supportsPromptContinuation = True


def test_compile_pose_skips_when_continuity_strategy_none(monkeypatch):
    called = {"load": False}

    def _boom(*_a, **_k):
        called["load"] = True
        raise AssertionError("load_packet must not run when strategy=none")

    monkeypatch.setattr(
        "app.codirector.pose_intelligence.persist.load_packet",
        _boom,
        raising=False,
    )
    out = _compile_pose_conditioning(
        "proj",
        SimpleNamespace(references=[]),
        _Caps(),
        continuity_strategy="none",
        temporal_rejected=False,
    )
    assert out["applied"] is False
    assert out["reason"] == "CONTINUITY_STRATEGY_NONE"
    assert out["promptPrefix"] == ""
    assert called["load"] is False


def test_compile_pose_skips_when_temporal_creator_rejected(monkeypatch):
    called = {"load": False}

    def _boom(*_a, **_k):
        called["load"] = True
        raise AssertionError("load_packet must not run when temporal rejected")

    monkeypatch.setattr(
        "app.codirector.pose_intelligence.persist.load_packet",
        _boom,
        raising=False,
    )
    out = _compile_pose_conditioning(
        "proj",
        SimpleNamespace(references=[]),
        _Caps(),
        continuity_strategy="last_frame_i2v",
        temporal_rejected=True,
    )
    assert out["applied"] is False
    assert out["reason"] == "TEMPORAL_CREATOR_REJECTED"
    assert out["promptPrefix"] == ""
    assert called["load"] is False
