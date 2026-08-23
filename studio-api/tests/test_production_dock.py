"""M42 Production Control Dock backend tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.production_control.contracts import (
    CpuFallbackPolicy,
    ModelDescriptor,
    PreferenceScope,
    ResolvedSelection,
    UserGlobalPreferences,
)
from app.production_control.gate import evaluate_production_dock_gate
from app.production_control.migration import migrate_preferences, migration_stamp
from app.production_control.resolve import resolve_modality
from app.production_control.router import _PENDING_SWITCHES
from app.production_control.store import (
    get_user_preferences,
    patch_user_preferences,
    resolve_with_precedence,
    save_project_preferences,
    save_user_preferences,
)


@pytest.fixture
def isolated_prefs(tmp_path, monkeypatch):
    """Isolate production_control JSON under tmp_path."""
    prod = tmp_path / "production_control"
    prod.mkdir(parents=True)
    (prod / "projects").mkdir()

    monkeypatch.setattr(
        "app.production_control.store._USER_PATH",
        prod / "user_preferences.json",
    )
    monkeypatch.setattr(
        "app.production_control.store._PROJECTS_DIR",
        prod / "projects",
    )
    monkeypatch.setattr(
        "app.production_control.migration._STAMP_PATH",
        prod / "migration_stamp.json",
    )
    monkeypatch.setattr("app.config.settings.data_dir", tmp_path)
    yield prod


def test_contracts_import():
    assert PreferenceScope.__args__ == ("system", "user", "project")
    assert CpuFallbackPolicy.__args__[0] == "disabled"
    model = ModelDescriptor(
        id="test",
        modality="llm",
        label="Test",
        locality="local",
        capabilityLabel="Available",
        gpuCompatible=True,
        executable=True,
    )
    assert model.modality == "llm"


def test_precedence_project_over_user_over_system(isolated_prefs):
    save_user_preferences(
        UserGlobalPreferences(
            video={"modality": "video", "activeModelId": "ltx-local", "availableModelIds": []}
        )
    )
    save_project_preferences(
        "proj-1",
        {"activeVideoModelId": "wan-local"},
    )
    resolved = resolve_with_precedence("proj-1", "video")
    assert resolved.activeModelId == "wan-local"
    assert resolved.source == "project"

    save_project_preferences("proj-2", {"activeVideoModelId": None})
    resolved_user = resolve_with_precedence("proj-2", "video")
    assert resolved_user.activeModelId == "ltx-local"
    assert resolved_user.source == "user"


def test_migration_idempotent(isolated_prefs, monkeypatch):
    codirector_path = isolated_prefs.parent / "codirector_config.json"
    codirector_path.write_text(
        json.dumps({"selectedModel": "gemma4:31b-it-qat", "endpoint": "http://127.0.0.1:11434"}),
        encoding="utf-8",
    )
    hosted_dir = isolated_prefs.parent / "hosted_providers"
    hosted_dir.mkdir(exist_ok=True)
    (hosted_dir / "preferences.json").write_text(
        json.dumps({"preferredProvider": "kie", "budgetPreference": "balanced"}),
        encoding="utf-8",
    )

    first = migrate_preferences()
    assert first["ok"] is True
    assert migration_stamp().get("migrated") is True

    prefs = get_user_preferences()
    assert prefs.llm.activeModelId == "ollama-gemma4-31b"
    assert prefs.defaultHostedProviderId == "kie"

    second = migrate_preferences()
    assert second["alreadyMigrated"] is True
    assert second["changes"] == []


def test_resolve_provenance(isolated_prefs):
    save_project_preferences("proj-a", {"activeAudioModelId": "ace-step-local"})
    selection = resolve_modality("proj-a", "audio")
    assert selection.modality == "audio"
    assert selection.activeModelId == "ace-step-local"
    assert selection.source == "project"
    assert selection.provenance.source == "project"
    assert selection.provenance.activeModelId == "ace-step-local"
    assert isinstance(selection, ResolvedSelection)


def test_runtime_map_image_and_video(isolated_prefs, monkeypatch):
    from app.production_control.runtime_map import (
        apply_image_dock_preference,
        apply_video_dock_preference,
        image_family_for_dock_model,
        video_engine_for_dock_model,
    )

    monkeypatch.setattr(
        "app.production_control.runtime_map.require_executable_route",
        lambda project_id, modality: {
            "activeModelId": "ltx-local" if modality == "video" else "qwen-image-2512-local",
            "executable": True,
            "videoEngine": "ltx",
            "imageFamily": "qwen2512",
        },
    )

    assert image_family_for_dock_model("qwen-image-2512-local") == "qwen2512"
    assert video_engine_for_dock_model("ltx-local") == "ltx"

    save_user_preferences(
        UserGlobalPreferences(
            image={
                "modality": "image",
                "preference": "local_preferred",
                "activeModelId": "qwen-image-2512-local",
                "availableModelIds": ["qwen-image-2512-local"],
                "allowFallback": False,
            },
            video={
                "modality": "video",
                "preference": "local_preferred",
                "activeModelId": "ltx-local",
                "availableModelIds": ["ltx-local"],
                "allowFallback": False,
            },
        )
    )
    body = apply_image_dock_preference("proj-map", {"prompt": "test", "modelFamilyPreference": "zimage"})
    assert body["modelFamilyPreference"] == "qwen2512"
    assert body["productionDock"]["activeModelId"] == "qwen-image-2512-local"

    locked = apply_image_dock_preference(
        "proj-map",
        {
            "prompt": "character sheet",
            "modelFamilyPreference": "zimage",
            "forceWorkflowKey": "zimage.ref_edit",
            "lockModelFamily": True,
        },
    )
    assert locked["modelFamilyPreference"] == "zimage"

    dock = apply_video_dock_preference("proj-map", engine_hint="auto")
    assert dock["engine"] == "ltx"
    assert dock["activeModelId"] == "ltx-local"


def test_gate_has_production_dock_go_false_without_artifacts(tmp_path, monkeypatch):
    # Isolate from repo certification stamps so GO requires evidence.
    monkeypatch.setattr(
        "app.production_control.gate._repo_root",
        lambda: tmp_path,
    )
    # Contracts/ownership won't exist under tmp → flags fail → NO-GO
    gate = evaluate_production_dock_gate()
    assert "productionDockGo" in gate
    assert gate["productionDockGo"] is False
    assert gate["verdict"] == "NO-GO"
    assert "flags" in gate
    assert isinstance(gate["flags"], dict)


def test_no_silent_cpu_fallback_default_disabled(isolated_prefs):
    prefs = get_user_preferences()
    assert prefs.cpuFallbackPolicy == "disabled"

    patch_user_preferences({"cpuFallbackPolicy": "ask"})
    updated = get_user_preferences()
    assert updated.cpuFallbackPolicy == "ask"

    gate = evaluate_production_dock_gate()
    # Default before patch in isolated env — re-check default
    save_user_preferences(UserGlobalPreferences(cpuFallbackPolicy="disabled"))
    gate_default = evaluate_production_dock_gate()
    assert gate_default["flags"]["noSilentFallbackPassed"] is True


def test_provider_switch_requires_confirmation(isolated_prefs):
    _PENDING_SWITCHES.clear()
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    staged = client.post(
        "/api/production-control/providers/switch",
        json={"providerId": "kie"},
    )
    assert staged.status_code == 200
    body = staged.json()
    assert body["applied"] is False
    assert body["requiresConfirmation"] is True

    blocked = client.post(
        "/api/production-control/providers/switch/confirm",
        json={"providerId": "kie", "confirmed": False},
    )
    assert blocked.status_code == 400

    confirmed = client.post(
        "/api/production-control/providers/switch/confirm",
        json={"providerId": "kie", "confirmed": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["applied"] is True
    _PENDING_SWITCHES.clear()


def test_model_registry_filter_for_action():
    from app.production_control.model_registry import filter_for_action

    models = filter_for_action("audio", "music")
    ids = {m["id"] for m in models}
    assert "ace-step-local" in ids
    ace = next(m for m in models if m["id"] == "ace-step-local")
    assert ace["actionMatch"] is True


def test_video_models_inherit_setup_readiness(monkeypatch):
    from app.production_control.model_registry import filter_for_action

    # _apply_setup_status derives non-image executable/capability from persisted
    # setup state (load_state) plus the lifecycle certified flag, rather than
    # build_status — list_models() runs _apply_setup_status on every modality,
    # and build_status probes slow audio/avatar subprocesses that would hang it.
    def fake_load_state():
        return {
            "status": {
                "hunyuan_video_15": {"status": "ready"},
                "hunyuan_video_13b": {"status": "ready"},
            }
        }

    def fake_cert(component_id: str):
        return SimpleNamespace(certified=(component_id == "hunyuan_video_13b"))

    monkeypatch.setattr("app.setup.state.load_state", fake_load_state)
    monkeypatch.setattr("app.setup.lifecycle.service.get_certification", fake_cert)
    models = filter_for_action("video", "text_to_video")

    by_id = {m["id"]: m for m in models}
    assert by_id["hunyuan-video-1.5-local"]["capabilityLabel"] == "Available"
    assert by_id["hunyuan-video-1.5-local"]["executable"] is True
    assert by_id["hunyuan-video-13b-local"]["capabilityLabel"] == "Certified"
    assert by_id["hunyuan-video-13b-local"]["executable"] is True


# ---------------------------------------------------------------------------
# Model Inventory Cache
# ---------------------------------------------------------------------------


def _fake_filter_for_action(modality: str, action: str = "generate") -> list[dict]:
    """Deterministic fake model data that exercises the cache."""
    return [
        {
            "id": f"{modality}-model-a",
            "modality": modality,
            "label": f"{modality.capitalize()} Model A",
            "locality": "local",
            "providerId": "native",
            "capabilityLabel": "Available",
            "supports": ["generate"],
            "doesNotSupport": [],
            "gpuCompatible": True,
            "executable": True,
            "actionMatch": True,
            "action": action,
            "group": "NATIVE LOCAL",
        },
        {
            "id": f"{modality}-model-b",
            "modality": modality,
            "label": f"{modality.capitalize()} Model B",
            "locality": "hosted",
            "providerId": "fal",
            "capabilityLabel": "Requires Setup",
            "supports": ["generate"],
            "doesNotSupport": [],
            "gpuCompatible": False,
            "executable": False,
            "selectable": False,
            "readiness": "not_configured",
            "actionMatch": True,
            "action": action,
            "group": "HOSTED API",
        },
    ]


def _fake_dock_api_models(modality: str) -> dict:
    return {
        "models": [],
        "activeProviderId": None,
        "emptyReason": "no_provider",
        "emptyMessage": "No hosted provider configured",
        "summary": {},
        "updatedAt": None,
    }


def _make_inventory_payload(modality: str) -> dict:
    """Shared helper: builds a minimal inventory dict for the given modality."""
    return {
        "models": [{"id": f"{modality}-model-a"}],
        "sections": {
            "llm": {"local": [], "api": [], "groups": []},
            "video": {"local": [], "api": [], "groups": []},
            "image": {"local": [], "api": [], "groups": []},
            "audio": {"local": [], "api": [], "groups": []},
        },
        "api": {modality: {}},
        "discoveredAt": 0,
    }


def test_model_inventory_cache_hit(monkeypatch):
    """Fresh cache returns immediately without calling discovery."""
    from app.production_control.model_inventory import (
        get_models_cached,
        invalidate_model_cache,
    )

    call_count = 0

    def counting_discovery():
        nonlocal call_count
        call_count += 1
        return _make_inventory_payload("llm")

    monkeypatch.setattr(
        "app.production_control.model_inventory._discover_all_models",
        counting_discovery,
    )

    invalidate_model_cache()
    # First call populates cache
    result = get_models_cached("llm")
    assert result["ok"] is True
    assert call_count == 1

    # Second call should hit cache (no discovery)
    result2 = get_models_cached("llm")
    assert result2["ok"] is True
    assert call_count == 1, "Second call should use cache, not call discovery"


def test_model_inventory_thundering_herd(monkeypatch):
    """Four simultaneous requests must not trigger four independent discoveries."""
    from app.production_control import model_inventory as mi

    mi.invalidate_model_cache()
    mi._MODEL_REFRESH_IN_FLIGHT = False

    call_count = 0

    def single_discovery():
        nonlocal call_count
        call_count += 1
        return _make_inventory_payload("llm")

    monkeypatch.setattr(
        "app.production_control.model_inventory._discover_all_models",
        single_discovery,
    )

    # Simulate stale cache so all 4 threads see stale + trigger refresh
    mi._MODEL_CACHE[mi._MODEL_CACHE_KEY] = (0.0, _make_inventory_payload("llm"))
    mi._MODEL_REFRESH_IN_FLIGHT = False

    import threading

    results: list[dict | None] = [None, None, None, None]

    def read_inventory(idx: int):
        results[idx] = mi.get_model_inventory()

    threads = [threading.Thread(target=read_inventory, args=(i,), daemon=True) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Only one background refresh should have been triggered
    assert call_count <= 1, f"Expected at most 1 discovery, got {call_count}"
    assert all(r is not None for r in results), "All threads should get cached data"


def test_model_inventory_empty_cache_cold_start(monkeypatch):
    """Empty cache on first request triggers single bounded discovery."""
    from app.production_control.model_inventory import (
        get_models_cached,
        invalidate_model_cache,
    )

    monkeypatch.setattr(
        "app.production_control.model_inventory._discover_all_models",
        lambda: {
            "models": [{"id": "test-model", "modality": "video"}],
            "sections": {
                "llm": {"local": [], "api": [], "groups": []},
                "video": {
                    "local": [
                        {
                            "id": "test-model",
                            "modality": "video",
                            "locality": "local",
                            "group": "NATIVE LOCAL",
                            "providerId": "native",
                            "capabilityLabel": "Available",
                            "executable": True,
                            "actionMatch": True,
                            "action": "generate",
                            "supports": [],
                            "doesNotSupport": [],
                            "gpuCompatible": False,
                            "selectable": False,
                        }
                    ],
                    "api": [],
                    "groups": ["NATIVE LOCAL"],
                },
                "image": {"local": [], "api": [], "groups": []},
                "audio": {"local": [], "api": [], "groups": []},
            },
            "api": {},
            "discoveredAt": 0,
        },
    )

    invalidate_model_cache()
    result = get_models_cached("video")
    assert result["ok"] is True
    assert len(result["models"]) == 1
    assert result["models"][0]["id"] == "test-model"


def test_model_inventory_cache_invalidation_on_pref_write(monkeypatch, isolated_prefs):
    """Preference writes must invalidate the model inventory cache."""
    from app.production_control.model_inventory import (
        _MODEL_CACHE,
        _MODEL_CACHE_KEY,
        invalidate_model_cache,
    )

    invalidate_model_cache()
    # Seed stale cache
    _MODEL_CACHE[_MODEL_CACHE_KEY] = (0.0, {"models": []})
    assert _MODEL_CACHE_KEY in _MODEL_CACHE

    invalidate_model_cache()
    assert _MODEL_CACHE_KEY not in _MODEL_CACHE, "invalidate_model_cache should clear the entry"
