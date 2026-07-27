"""M3.0 Completion Phase 6: promoting a .env fal key into the secret store.

Render jobs read the credential from `secrets_store` only, so a key that lives in `.env`
produces the contradictory pair "fal key present" in diagnostics and "fal.ai API key not
configured" the moment a job runs. These tests pin the bridge that closes that gap, plus
the two rules that keep it safe: a key fal rejects is never stored, and the key never
appears in any report or verification record.
"""

from __future__ import annotations

import asyncio

import pytest

from app import fal_env_bridge, secrets_store

KEY = "fal-env-key-must-not-leak"


@pytest.fixture(autouse=True)
def isolated_secrets(tmp_path, monkeypatch: pytest.MonkeyPatch):
    secrets_dir = tmp_path / "secrets"
    monkeypatch.setattr(secrets_store, "SECRETS_DIR", secrets_dir)
    monkeypatch.setattr(secrets_store, "MASTER_KEY_FILE", secrets_dir / "master.key")
    for name in fal_env_bridge.ENV_KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    return secrets_dir


@pytest.fixture()
def no_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Keep the developer's real .env out of the test."""
    monkeypatch.setattr(fal_env_bridge, "dotenv_candidates", lambda: [tmp_path / "absent.env"])


def probe_returns(monkeypatch: pytest.MonkeyPatch, result: dict) -> list[str]:
    seen: list[str] = []

    async def fake_validate(api_key: str, **_kwargs):
        seen.append(api_key)
        return result

    monkeypatch.setattr(fal_env_bridge, "validate_fal_key", fake_validate)
    return seen


VERIFIED = {"valid": True, "status": "verified", "httpStatus": 404, "message": "Key accepted by fal.ai."}
REJECTED = {"valid": False, "status": "invalid", "httpStatus": 401, "message": "fal.ai rejected this API key."}
UNREACHABLE = {"valid": None, "status": "unverified", "httpStatus": None, "message": "Could not reach fal.ai."}


def test_env_key_is_stored_after_a_successful_probe(monkeypatch: pytest.MonkeyPatch, no_dotenv) -> None:
    monkeypatch.setenv("FAL_API_KEY", KEY)
    probed = probe_returns(monkeypatch, VERIFIED)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_from_env())

    assert report["action"] == "stored"
    assert report["source"] == "FAL_API_KEY"
    assert probed == [KEY]
    assert secrets_store.get_secret("fal_api_key") == KEY
    assert secrets_store.secret_status("fal_api_key")["state"] == "verified"


def test_rejected_key_is_not_stored(monkeypatch: pytest.MonkeyPatch, no_dotenv) -> None:
    monkeypatch.setenv("FAL_KEY", KEY)
    probe_returns(monkeypatch, REJECTED)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_from_env())

    assert report["action"] == "rejected"
    assert secrets_store.get_secret("fal_api_key") is None


def test_unreachable_fal_stores_the_key_but_flags_it_unverified(
    monkeypatch: pytest.MonkeyPatch, no_dotenv
) -> None:
    monkeypatch.setenv("FAL_API_KEY", KEY)
    probe_returns(monkeypatch, UNREACHABLE)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_from_env())

    assert report["action"] == "stored-unverified"
    assert secrets_store.get_secret("fal_api_key") == KEY
    assert secrets_store.secret_status("fal_api_key")["state"] == "unverified"


def test_existing_stored_key_wins_and_is_never_probed(monkeypatch: pytest.MonkeyPatch, no_dotenv) -> None:
    secrets_store.set_secret("fal_api_key", "already-configured-key")
    monkeypatch.setenv("FAL_API_KEY", KEY)
    probed = probe_returns(monkeypatch, VERIFIED)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_from_env())

    assert report["action"] == "already-configured"
    assert probed == []
    assert secrets_store.get_secret("fal_api_key") == "already-configured-key"


def test_missing_key_is_reported_without_touching_the_store(
    monkeypatch: pytest.MonkeyPatch, no_dotenv
) -> None:
    probed = probe_returns(monkeypatch, VERIFIED)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_from_env())

    assert report["action"] == "no-key"
    assert probed == []
    assert secrets_store.get_secret("fal_api_key") is None


def test_key_is_read_from_dotenv_without_a_studio_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# fal credentials\nexport FAL_KEY='dotenv-key-value'\nSTUDIO_DATA_DIR=ignored\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(fal_env_bridge, "dotenv_candidates", lambda: [env_file])
    probe_returns(monkeypatch, VERIFIED)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_from_env())

    assert report["action"] == "stored"
    assert report["source"] == ".env:FAL_KEY"
    assert secrets_store.get_secret("fal_api_key") == "dotenv-key-value"
    # A .env-only key must also become visible to the readiness probes that read os.environ.
    assert fal_env_bridge.os.environ["FAL_API_KEY"] == "dotenv-key-value"


def test_reports_and_verification_records_never_carry_the_key(
    monkeypatch: pytest.MonkeyPatch, no_dotenv, isolated_secrets
) -> None:
    monkeypatch.setenv("FAL_API_KEY", KEY)
    probe_returns(monkeypatch, VERIFIED)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_from_env())

    assert KEY not in repr(report)
    record = secrets_store.get_secret_verification("fal_api_key")
    assert KEY not in repr(record)
    assert record["detail"]["seededFrom"] == "FAL_API_KEY"
    for path in isolated_secrets.glob("*.json"):
        assert KEY not in path.read_text(encoding="utf-8")


def test_startup_hook_is_disabled_by_the_env_switch(monkeypatch: pytest.MonkeyPatch, no_dotenv) -> None:
    monkeypatch.setenv("FAL_API_KEY", KEY)
    monkeypatch.setenv("STUDIO_FAL_ENV_BRIDGE", "0")
    probed = probe_returns(monkeypatch, VERIFIED)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_at_startup())

    assert report["action"] == "disabled"
    assert probed == []
    assert secrets_store.get_secret("fal_api_key") is None


def test_startup_hook_swallows_failures(monkeypatch: pytest.MonkeyPatch, no_dotenv) -> None:
    monkeypatch.setenv("STUDIO_FAL_ENV_BRIDGE", "1")
    monkeypatch.setenv("FAL_API_KEY", KEY)

    async def boom(*_args, **_kwargs):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(fal_env_bridge, "validate_fal_key", boom)

    report = asyncio.run(fal_env_bridge.bridge_fal_key_at_startup())

    assert report["action"] == "error"
