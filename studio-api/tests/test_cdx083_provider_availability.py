"""CDX-083 provider inventory availability truth.

A cloud provider whose credential env key is present is CONFIGURED, not
available. availability=True is asserted only when the secrets store has
actually verified the key with the provider (a real live probe at configure
time). A fake key in the environment must never flip a provider to available.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.image_runtime import provider_registry as pr


def _fal_provider() -> dict:
    return {
        "providerId": "fal",
        "displayName": "fal.ai",
        "kind": "cloud",
        "runtime": "fal",
        "credentialEnvKeys": ["FAL_KEY", "FAL_API_KEY"],
    }


def _probe(monkeypatch, verified=None, env: dict | None = None):
    """Run the fal probe with a controlled env and verification state."""
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_API_KEY", raising=False)
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(pr, "_credential_verified", lambda pid: verified)
    return pr.probe_provider_availability(_fal_provider())


def test_fake_key_env_is_not_available(monkeypatch):
    """CDX-083: FAL_KEY=sk-fake with no verified probe -> configured but NOT available."""
    result = _probe(monkeypatch, verified=None, env={"FAL_KEY": "sk-fake"})
    assert result["credentialConfigured"] is True
    assert result["available"] is False
    assert result["verificationState"] == "configured_unverified"
    assert "not verified" in result["reason"]


def test_no_credentials_not_configured(monkeypatch):
    result = _probe(monkeypatch, verified=None, env={})
    assert result["credentialConfigured"] is False
    assert result["available"] is False
    assert result["verificationState"] == "not_configured"


def test_verified_secret_is_available(monkeypatch):
    """A genuinely verified key (secrets store probe succeeded) is available."""
    result = _probe(monkeypatch, verified=True, env={"FAL_KEY": "sk-real"})
    assert result["credentialConfigured"] is True
    assert result["available"] is True
    assert result["verificationState"] == "verified"


def test_rejected_secret_not_available(monkeypatch):
    result = _probe(monkeypatch, verified=False, env={"FAL_KEY": "sk-bad"})
    assert result["credentialConfigured"] is True
    assert result["available"] is False
    assert result["verificationState"] == "invalid"


def test_provider_without_env_keys_never_available(monkeypatch):
    provider = {"providerId": "stability", "kind": "cloud", "credentialEnvKeys": []}
    result = pr.probe_provider_availability(provider)
    assert result["available"] is False
    assert "not configured" in result["reason"]


def test_provider_inventory_cloud_available_only_verified(monkeypatch):
    """provider_inventory.cloudAvailable must only contain verified providers."""
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("FAL_API_KEY", raising=False)
    monkeypatch.setattr(pr, "_credential_verified", lambda pid: None)
    inv = pr.provider_inventory()
    assert "fal" not in inv["cloudAvailable"]

    monkeypatch.setattr(pr, "_credential_verified", lambda pid: True)
    monkeypatch.setenv("FAL_KEY", "sk-real")
    inv2 = pr.provider_inventory()
    assert "fal" in inv2["cloudAvailable"]

