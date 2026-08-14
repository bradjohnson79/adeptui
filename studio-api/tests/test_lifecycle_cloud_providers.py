"""Cloud Provider cards: secret map, filter, and thin lifecycle key endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


TEN = [
    "google_imagen",
    "openai",
    "replicate",
    "ideogram",
    "recraft",
    "leonardo",
    "runware",
    "together",
    "black_forest_labs",
    "stability",
]
SKIP = {"kie", "fal", "wavespeed"}


@pytest.fixture(autouse=True)
def isolated_secrets(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from app import secrets_store

    secrets_dir = tmp_path / "secrets"
    monkeypatch.setattr(secrets_store, "SECRETS_DIR", secrets_dir)
    monkeypatch.setattr(secrets_store, "MASTER_KEY_FILE", secrets_dir / "master.key")
    return secrets_dir


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_list_cloud_providers_includes_ten_and_omits_api_key_trio():
    from app.setup.lifecycle.service import list_cloud_providers

    payload = list_cloud_providers()
    ids = [item["providerId"] for item in payload["items"]]
    assert set(TEN).issubset(set(ids))
    assert SKIP.isdisjoint(set(ids))
    for item in payload["items"]:
        assert item["providerId"] not in SKIP
        assert item["statusLabel"] in {"Requires Setup", "Ready"}
        assert item["connectionTestAvailable"] is False
        if item["providerId"] in TEN:
            assert item["setupSupported"] is True
            assert item["secretName"]
            assert item["summary"]
            assert item["keysUrl"]
            assert item["docsUrl"]


def test_image_provider_keys_map_bfl_and_stability():
    from app.setup.lifecycle.service import _IMAGE_PROVIDER_KEYS

    assert _IMAGE_PROVIDER_KEYS["black_forest_labs"] == "bfl_api_key"
    assert _IMAGE_PROVIDER_KEYS["stability"] == "stability_api_key"
    assert _IMAGE_PROVIDER_KEYS["openai"] == "openai_api_key"


def test_set_and_clear_cloud_provider_key_is_masked_and_not_ready():
    from app.secrets_store import get_secret
    from app.setup.lifecycle.service import (
        clear_cloud_provider_key,
        list_cloud_providers,
        set_cloud_provider_key,
    )

    secret = "sk-test-openai-cloud-provider-key-xyz9"
    result = set_cloud_provider_key("openai", secret)
    assert result["ok"] is True
    assert result["configured"] is True
    assert result["state"] == "unverified"
    assert result["statusLabel"] == "Requires Setup"
    assert result["hint"]
    assert secret not in str(result)
    assert get_secret("openai_api_key") == secret

    listed = next(item for item in list_cloud_providers()["items"] if item["providerId"] == "openai")
    assert listed["configured"] is True
    assert listed["statusLabel"] == "Requires Setup"
    assert listed["state"] == "unverified"
    assert secret not in str(listed)

    cleared = clear_cloud_provider_key("openai")
    assert cleared["ok"] is True
    assert cleared["configured"] is False
    assert cleared["statusLabel"] == "Requires Setup"
    assert get_secret("openai_api_key") is None


def test_lifecycle_key_http_put_delete_never_echoes_secret():
    client = _client()
    secret = "sk-live-do-not-echo-abcd"
    put = client.put("/api/setup/lifecycle/cloud-providers/openai/key", json={"api_key": secret})
    assert put.status_code == 200
    body = put.json()
    assert body["configured"] is True
    assert body["statusLabel"] == "Requires Setup"
    assert secret not in put.text
    assert "sk-live" not in put.text

    got = client.get("/api/setup/lifecycle/cloud-providers/openai/key")
    assert got.status_code == 200
    assert got.json()["configured"] is True
    assert got.json()["hint"]
    assert secret not in got.text

    listed = client.get("/api/setup/lifecycle/cloud-providers")
    ids = [item["providerId"] for item in listed.json()["items"]]
    assert "kie" not in ids
    assert "fal" not in ids
    assert "wavespeed" not in ids
    assert secret not in listed.text

    deleted = client.delete("/api/setup/lifecycle/cloud-providers/openai/key")
    assert deleted.status_code == 200
    assert deleted.json()["configured"] is False
    assert secret not in deleted.text


def test_lifecycle_key_rejects_hosted_trio_and_empty_key():
    client = _client()
    assert client.put("/api/setup/lifecycle/cloud-providers/kie/key", json={"api_key": "abc"}).status_code == 404
    assert client.put("/api/setup/lifecycle/cloud-providers/fal/key", json={"api_key": "abc"}).status_code == 404
    assert client.put("/api/setup/lifecycle/cloud-providers/wavespeed/key", json={"api_key": "abc"}).status_code == 404
    assert client.put("/api/setup/lifecycle/cloud-providers/openai/key", json={"api_key": "   "}).status_code == 400


def test_set_cloud_provider_key_does_not_call_connect_and_verify(monkeypatch: pytest.MonkeyPatch):
    from app.setup.lifecycle import service as lifecycle_service

    def _boom(*_args, **_kwargs):
        raise AssertionError("connect_and_verify must not be called")

    monkeypatch.setattr("app.hosted_providers.service.connect_and_verify", _boom, raising=False)
    result = lifecycle_service.set_cloud_provider_key("stability", "sk-stability-test-key")
    assert result["configured"] is True
    assert result["statusLabel"] == "Requires Setup"

