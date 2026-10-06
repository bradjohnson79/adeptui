"""Regression for the audio runtime status cache.

Root cause this locks in: local_runtime_status() imports torch-heavy audio
adapters and runs subprocess health checks (~13s) on every call. The status
cross-check calls it on every poll, which blocked the event loop and
intermittently timed out library.preflight. The repair adds a short-TTL cache
for the read-only status path while keeping the generation path (refresh=True)
fresh.
"""
from __future__ import annotations

import time

from app.audio_studio import provider_resolver


def _install_fast_probe(monkeypatch, *, ready: bool = True) -> dict[str, int]:
    calls = {"n": 0}

    def _fast_probe(adapter_cls_name, module_path, runtime, registry_id):
        calls["n"] += 1
        return {
            "runtime": runtime,
            "ready": ready,
            "cuda": ready,
            "accelerator": "cuda" if ready else "cpu",
            "message": "ready" if ready else "not ready",
        }

    monkeypatch.setattr(provider_resolver, "_probe_sandbox", _fast_probe)
    return calls


def _reset_cache():
    provider_resolver._LOCAL_STATUS_CACHE = None
    provider_resolver._LOCAL_STATUS_CACHED_AT = 0.0


def test_local_runtime_status_caches_within_ttl(monkeypatch):
    _reset_cache()
    calls = _install_fast_probe(monkeypatch)

    first = provider_resolver.local_runtime_status()
    second = provider_resolver.local_runtime_status()

    assert first is second, "second call did not reuse the cached snapshot"
    assert calls["n"] == 2, "first call should probe both sandboxes once"
    # Second call must NOT re-probe (within TTL).
    assert calls["n"] == 2, "second call re-probed sandboxes instead of using the cache"
    _reset_cache()


def test_local_runtime_status_refresh_bypasses_cache(monkeypatch):
    _reset_cache()
    calls = _install_fast_probe(monkeypatch)

    provider_resolver.local_runtime_status()
    before = calls["n"]
    provider_resolver.local_runtime_status(refresh=True)

    assert calls["n"] == before + 2, "refresh=True did not re-probe both sandboxes"
    _reset_cache()


def test_local_runtime_status_cache_expires_after_ttl(monkeypatch):
    _reset_cache()
    calls = _install_fast_probe(monkeypatch)

    provider_resolver.local_runtime_status()
    assert calls["n"] == 2

    # Force the cache to look stale.
    provider_resolver._LOCAL_STATUS_CACHED_AT = (
        time.monotonic() - provider_resolver._LOCAL_STATUS_TTL_SEC - 1
    )
    provider_resolver.local_runtime_status()
    assert calls["n"] == 4, "expired cache was not re-probed"
    _reset_cache()


def test_resolve_execution_uses_fresh_status(monkeypatch):
    """The generation path must bypass the cache so routing never uses stale readiness."""
    _reset_cache()
    calls = _install_fast_probe(monkeypatch)

    # Warm the status cache (read-only path).
    provider_resolver.local_runtime_status()
    cached_probe_count = calls["n"]

    # resolve_execution (generation path) must force a fresh probe.
    try:
        provider_resolver.resolve_execution("music")
    except Exception:
        pass
    assert calls["n"] > cached_probe_count, (
        "resolve_execution reused the cache instead of probing fresh readiness"
    )
    _reset_cache()


def test_local_runtime_status_light_never_probes(monkeypatch):
    """Regression (P0/P1-5): the STATUS path (light=True) must NEVER run the
    ~25s torch/subprocess probe synchronously. It serves fresh cache, stale
    cache (while a background thread refreshes), or a minimal 'checking'
    payload."""
    _reset_cache()
    calls = _install_fast_probe(monkeypatch)
    bg_calls = {"n": 0}

    # Neutralize the fire-and-forget background refresh with a spy so the test
    # is deterministic: the light path must not probe synchronously, and must
    # delegate any refresh to the background hook.
    monkeypatch.setattr(provider_resolver, "_maybe_trigger_background_refresh", lambda: bg_calls.__setitem__("n", bg_calls["n"] + 1))

    # No cache: light path returns a 'checking' payload, zero synchronous probes.
    out0 = provider_resolver.local_runtime_status(light=True)
    assert calls["n"] == 0, "light path probed sandboxes instead of serving 'checking'"
    assert out0.get("ACE-Step", {}).get("message") == "checking audio runtime..."
    assert bg_calls["n"] == 1, "light path did not trigger a background refresh when no cache"

    # Populate cache via a real (fast, monkeypatched) probe.
    provider_resolver.local_runtime_status(refresh=True)
    assert calls["n"] == 2
    cached = provider_resolver._LOCAL_STATUS_CACHE

    # Fresh cache: light path returns the cache, zero new probes, no bg refresh.
    out1 = provider_resolver.local_runtime_status(light=True)
    assert out1 is cached, "light path did not return the fresh cache"
    assert calls["n"] == 2
    assert bg_calls["n"] == 1, "light path triggered an unnecessary refresh while fresh"

    # Stale cache: light path returns the stale cache, zero synchronous probes,
    # and delegates a refresh to the background hook.
    provider_resolver._LOCAL_STATUS_CACHED_AT = (
        time.monotonic() - provider_resolver._LOCAL_STATUS_TTL_SEC - 1
    )
    out2 = provider_resolver.local_runtime_status(light=True)
    assert out2 is cached, "light path did not serve the stale cache"
    assert calls["n"] == 2, "light path probed on stale cache instead of serving stale"
    assert bg_calls["n"] == 2, "light path did not trigger a background refresh when stale"
    _reset_cache()


def test_aggregate_status_uses_light_audio_path(monkeypatch):
    """Regression (P0/P1-5): aggregate_status() must route audio through the
    light path (_audio_status_light -> local_runtime_status(light=True)) so
    the status path never blocks on the ~25s audio probe, and must run the
    independent probes in bounded parallel threads."""
    from app.production_control import status as pc_status
    from app.production_control import store as pc_store

    called = {"audio": False, "queue_thread": None}
    import threading

    main_thread = threading.get_ident()

    def _audio_light():
        called["audio"] = True
        return {"ACE-Step": {"ready": False, "cuda": False}}, {"status": "Unknown", "cuda": None}

    def _queue():
        called["queue_thread"] = threading.get_ident()
        return {"queued": 0, "running": 0}

    monkeypatch.setattr(pc_status, "_audio_status_light", _audio_light)
    monkeypatch.setattr(pc_status, "_codirector_status", lambda: {"configured": False})
    monkeypatch.setattr(pc_status, "_hosted_status", lambda: {"providers": [], "preferred": None})
    monkeypatch.setattr(pc_status, "_queue_counts", _queue)
    monkeypatch.setattr(pc_store, "get_user_preferences", lambda: type("U", (), {"runtimeSource": "local"})())

    result = pc_status.aggregate_status()

    assert called["audio"] is True, "aggregate_status did not call the light audio path"
    assert result["ok"] is True
    # Bounded parallelism: queue_counts must run in a worker thread, not the caller thread.
    assert called["queue_thread"] is not None and called["queue_thread"] != main_thread, (
        "aggregate_status ran probes serially on the caller thread (no bounded parallelism)"
    )
    _reset_cache()
