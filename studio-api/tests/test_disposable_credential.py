"""Disposable credential storage. A rejected provider key is never written."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import app.secrets_store as store

    secret_dir = tmp_path / "secrets"
    monkeypatch.setattr(store, "SECRETS_DIR", secret_dir)
    monkeypatch.setattr(store, "MASTER_KEY_FILE", secret_dir / "master.key")
    return secret_dir


def test_disposable_credential_can_be_saved_replaced_and_removed(isolated_secrets: Path) -> None:
    import app.secrets_store as store

    store.set_secret("adept_cert_disposable", "disposable-key-v1")
    assert store.get_secret("adept_cert_disposable") == "disposable-key-v1"
    encoded = next(isolated_secrets.glob("*.enc")).read_bytes()
    assert b"disposable-key-v1" not in encoded
    store.set_secret("adept_cert_disposable", "disposable-key-v2")
    assert store.get_secret("adept_cert_disposable") == "disposable-key-v2"
    assert store.get_secret("adept_cert_disposable") != "disposable-key-v1"
    store.clear_secret("adept_cert_disposable")
    assert store.get_secret("adept_cert_disposable") is None


def test_rejected_provider_key_is_not_stored(isolated_secrets: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.secrets_store as store
    from app.hosted_providers import service
    from app.hosted_providers.registry import PROVIDERS

    async def reject(_key: str) -> dict:
        return {"valid": False, "message": "The provider rejected this disposable key."}

    monkeypatch.setitem(service._PROBES, "fal", reject)
    result = asyncio.run(service.connect_and_verify("fal", "adept-cert-disposable-not-real"))
    assert result["ok"] is False
    assert result["error"] == "INVALID_KEY"
    assert store.get_secret(PROVIDERS["fal"].secret_name) is None
    assert not list(isolated_secrets.glob("*.enc"))
