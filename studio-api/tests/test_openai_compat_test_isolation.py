"""Playwright mock OpenAI-compatible endpoints must not enter the owner registry."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.hosted_providers import custom_llm
from app.hosted_providers.preferences import (
    begin_preference_lease,
    load_preferences,
    restore_preference_lease,
    save_preferences,
)


def _probe(models: list[str]):
    async def fake(api_key: str, *, base_url: str, models_path: str = "/v1/models"):
        return {
            "valid": True,
            "httpStatus": 200,
            "message": "ok",
            "models": list(models),
            "capabilities": {"llm": True, "image": False, "video": False, "audio": False},
            "mock": False,
        }

    return fake


def _run_connect(**kwargs):
    return asyncio.run(custom_llm.connect_endpoint(**kwargs))


@pytest.fixture(autouse=True)
def _clean_compat_stores():
    for path in (custom_llm.config_path(), custom_llm.disposable_config_path()):
        if path.exists():
            path.unlink()
    yield
    for path in (custom_llm.config_path(), custom_llm.disposable_config_path()):
        if path.exists():
            path.unlink()


def test_mock_fixture_is_stored_outside_owner_registry(monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.adapters.openai_compatible_adapter.probe_openai_compatible",
        _probe(["mock-chat-mini", "mock-chat-pro"]),
    )
    result = _run_connect(
        display_name="Mock OpenAI Compat",
        base_url="http://127.0.0.1:53260",
        api_key="test-key-not-a-secret-for-prod",
    )
    assert result["ok"] is True
    assert result["disposable"] is True
    assert result["endpoint"]["testArtifact"] is True
    owner = custom_llm._load()
    assert owner["endpoints"] == []
    disposable = custom_llm._load_at(custom_llm.disposable_config_path())
    assert len(disposable["endpoints"]) == 1
    assert disposable["endpoints"][0]["displayName"] == "Mock OpenAI Compat"
    assert all("Mock OpenAI Compat" not in row["label"] for row in custom_llm.dock_llm_models())
    listed = custom_llm.list_endpoints()
    assert listed == []
    raw = json.dumps(result)
    assert "test-key-not-a-secret-for-prod" not in raw


def test_legitimate_endpoint_survives_purge(monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.adapters.openai_compatible_adapter.probe_openai_compatible",
        _probe(["llama3"]),
    )
    result = _run_connect(
        display_name="Studio Local LLM",
        base_url="http://127.0.0.1:11434",
        api_key="owner-local-key",
    )
    assert result["ok"] is True
    assert result["disposable"] is False
    endpoint_id = result["endpoint"]["id"]

    # A leaked fixture sitting beside the legitimate endpoint.
    leaked_id = "a2cb19b2-b924-443b-9e80-443595ef5925"
    owner = custom_llm._load()
    owner["endpoints"].append(
        {
            "id": leaked_id,
            "providerId": "openai_compatible",
            "displayName": "Mock OpenAI Compat",
            "baseUrl": "http://127.0.0.1:60346",
            "discoveredModels": ["mock-chat-mini", "mock-chat-pro"],
        }
    )
    custom_llm._save(owner)
    custom_llm.set_secret(custom_llm.secret_name_for(leaked_id), "leaked-test-key")

    purged = custom_llm.purge_leaked_test_providers()
    assert leaked_id in purged["ownerRemoved"]
    kept = custom_llm.list_endpoints()
    assert [row["id"] for row in kept] == [endpoint_id]
    assert kept[0]["displayName"] == "Studio Local LLM"
    assert custom_llm.get_secret(custom_llm.secret_name_for(leaked_id)) is None
    assert custom_llm.get_secret(custom_llm.secret_name_for(endpoint_id)) == "owner-local-key"


def test_forgotten_disposable_flag_still_cannot_write_owner_registry(monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.adapters.openai_compatible_adapter.probe_openai_compatible",
        _probe(["mock-chat-mini", "mock-chat-pro"]),
    )
    result = _run_connect(
        display_name="Mock OpenAI Compat",
        base_url="http://127.0.0.1:60346",
        api_key="another-test-key",
        disposable=False,
    )
    assert result["disposable"] is True
    assert custom_llm._load()["endpoints"] == []
    assert custom_llm.list_disposable_endpoints()[0]["baseUrl"] == "http://127.0.0.1:60346"


def test_expired_disposable_secret_is_cleared():
    expired_id = "expired-mock-endpoint"
    path = custom_llm.disposable_config_path()
    custom_llm._save_at(
        path,
        {
            "schemaVersion": 1,
            "endpoints": [
                {
                    "id": expired_id,
                    "displayName": "Mock OpenAI Compat",
                    "baseUrl": "http://127.0.0.1:9",
                    "discoveredModels": ["mock-chat-mini"],
                    "expiresAt": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
                    "disposable": True,
                }
            ],
        },
    )
    custom_llm.set_secret(custom_llm.secret_name_for(expired_id), "expired-key")
    removed = custom_llm.sweep_expired_disposable()
    assert removed == [expired_id]
    assert custom_llm.list_disposable_endpoints() == []
    assert custom_llm.get_secret(custom_llm.secret_name_for(expired_id)) is None


def test_preference_lease_restores_owner_and_ignores_later_owner_edit():
    save_preferences(preferred_provider="fal", budget_preference="low_cost")
    begin_preference_lease(preferred_provider="automatic", budget_preference="quality")
    assert load_preferences()["preferredProvider"] == "automatic"
    # Retry must not snapshot the test value as the original.
    begin_preference_lease(preferred_provider="automatic", budget_preference="quality")
    restored = restore_preference_lease()
    assert restored["restored"] is True
    assert restored["preferredProvider"] == "fal"
    assert restored["budgetPreference"] == "low_cost"

    save_preferences(preferred_provider="fal", budget_preference="balanced")
    begin_preference_lease(preferred_provider="automatic", budget_preference="quality")
    save_preferences(preferred_provider="kie", budget_preference="quality")
    kept = restore_preference_lease()
    assert kept["restored"] is False
    assert kept["preferredProvider"] == "kie"
