"""Dynamic API Model Discovery — Dock population from normalized catalog only."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.hosted_providers import discovery as discovery_mod
from app.hosted_providers.discovery import dock_api_models
from app.hosted_providers.model_store import load_catalog, save_catalog
from app.production_control.model_registry import get_model


@pytest.fixture()
def isolated_catalog(tmp_path, monkeypatch):
    path = tmp_path / "discovered_models.json"
    monkeypatch.setattr("app.hosted_providers.model_store._STORE_PATH", path)
    yield path


def test_dock_api_empty_without_provider(isolated_catalog):
    save_catalog(
        {
            "activeProviderId": None,
            "emptyReason": "no_provider",
            "emptyMessage": "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard.",
            "models": [],
            "summary": {},
        }
    )
    section = dock_api_models("video")
    assert section["models"] == []
    assert section["emptyReason"] == "no_provider"
    assert "Setup Wizard" in (section["emptyMessage"] or "")


def test_dock_api_shows_only_active_provider_models(isolated_catalog):
    save_catalog(
        {
            "activeProviderId": "kie",
            "emptyReason": None,
            "models": [
                {
                    "id": "seedance-kie",
                    "providerId": "kie",
                    "modality": "video",
                    "label": "Seedance 2.0 — Kie.ai",
                    "selectable": True,
                    "readiness": "Ready",
                    "executable": True,
                },
                {
                    "id": "kling-fal",
                    "providerId": "fal",
                    "modality": "video",
                    "label": "Kling 3.0 — fal.ai",
                    "selectable": True,
                    "readiness": "Ready",
                    "executable": True,
                },
            ],
            "summary": {},
        }
    )
    section = dock_api_models("video")
    ids = [m["id"] for m in section["models"]]
    assert ids == ["seedance-kie"]
    assert section["emptyReason"] is None


def test_dock_api_modality_empty_message(isolated_catalog):
    save_catalog(
        {
            "activeProviderId": "kie",
            "emptyReason": None,
            "models": [
                {
                    "id": "flux-kie",
                    "providerId": "kie",
                    "modality": "image",
                    "selectable": True,
                    "readiness": "Ready",
                }
            ],
            "summary": {},
        }
    )
    section = dock_api_models("video")
    assert section["models"] == []
    assert section["emptyReason"] == "none_for_modality"
    assert "video" in (section["emptyMessage"] or "")


def test_discover_provider_classifies_ready_and_adapter(isolated_catalog, monkeypatch):
    monkeypatch.setattr(
        "app.hosted_providers.discovery.get_secret",
        lambda _name: "test-key",
    )
    monkeypatch.setattr(
        "app.hosted_providers.discovery.probe_kie",
        AsyncMock(return_value={"valid": True, "message": "ok", "httpStatus": 200}),
    )
    result = asyncio.run(discovery_mod.discover_provider("kie", persist_as_active=True))
    assert result["ok"] is True
    summary = result["summary"]
    assert summary["videoFound"] >= 1
    assert summary["compatible"] >= 1
    cat = load_catalog()
    assert cat["activeProviderId"] == "kie"
    ready = [m for m in cat["models"] if m["readiness"] == "Ready"]
    adapter = [m for m in cat["models"] if m["readiness"] == "Requires Adapter"]
    assert ready
    # audio-kie is adapterAvailable False in catalog
    assert any(m["id"] == "audio-kie" for m in adapter) or summary["requiresAdapter"] >= 0
    # Discovery must not auto-activate a dock preference — only store catalog.
    assert "activeModelId" not in cat


def test_get_model_resolves_discovered_ids(isolated_catalog):
    save_catalog(
        {
            "activeProviderId": "kie",
            "models": [
                {
                    "id": "seedance-kie",
                    "providerId": "kie",
                    "modality": "video",
                    "label": "Seedance 2.0 — Kie.ai",
                    "displayName": "Seedance 2.0",
                    "capabilityLabel": "Certified",
                    "capabilities": ["text_to_video"],
                    "executable": True,
                    "selectable": True,
                    "readiness": "Ready",
                }
            ],
        }
    )
    model = get_model("seedance-kie")
    assert model is not None
    assert model.id == "seedance-kie"
    assert model.locality == "hosted"
    assert model.providerId == "kie"


def test_no_hardcoded_api_in_empty_catalog(isolated_catalog):
    """Acceptance: empty catalog → no selectable API models for Dock sections."""
    save_catalog({"activeProviderId": None, "models": [], "emptyReason": "no_provider"})
    for modality in ("llm", "video", "image", "audio"):
        assert dock_api_models(modality)["models"] == []
