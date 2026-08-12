"""Hunyuan Setup status honesty + profile allow_patterns."""

from __future__ import annotations


def test_hunyuan_not_installed_status_honest():
    from app.video_runtime.hunyuan_providers import describe_provider, HUNYUAN_15

    cap = describe_provider(HUNYUAN_15)
    # Current workspace has no verified weights — must not report Installed*
    if not cap.installed:
        assert not str(cap.status).startswith("Installed")
        assert cap.executable is False


def test_consumer_allow_patterns_include_i2v_and_vae():
    from app.video_runtime.hunyuan_install import _ALLOW_PATTERNS
    from app.video_runtime.hunyuan_providers import HUNYUAN_15

    patterns = _ALLOW_PATTERNS[HUNYUAN_15]["consumer"]
    assert "config.json" in patterns
    assert "vae/*" in patterns
    assert any("720p_i2v" in p for p in patterns)


def test_enqueue_returns_message():
    from app.video_runtime.hunyuan_install import enqueue_install

    res = enqueue_install("hunyuan_video_15")
    assert res.get("ok") is True
    assert res.get("message")
    assert res.get("providerId") == "hunyuan-video-1.5-local"
