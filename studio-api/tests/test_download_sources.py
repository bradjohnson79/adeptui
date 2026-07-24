"""Unit tests for Download Sources URL parsing, security, and CLI mock detection."""

from __future__ import annotations

import json
import os

import pytest

from app.setup.download_sources.cli_detect import detect_github_cli, detect_huggingface_cli
from app.setup.download_sources.security import SourceSecurityError, validate_remote_url
from app.setup.download_sources.url_parse import parse_source_url


@pytest.mark.parametrize(
    "url,provider,kind",
    [
        ("https://github.com/acme/widgets", "github", "repo"),
        ("https://github.com/acme/widgets/releases", "github", "release"),
        ("https://github.com/acme/widgets/releases/tag/v1.2.3", "github", "release"),
        (
            "https://github.com/acme/widgets/releases/download/v1.2.3/pack.zip",
            "github",
            "release_asset",
        ),
        (
            "https://github.com/acme/widgets/archive/refs/heads/main.zip",
            "github",
            "branch_archive",
        ),
        (
            "https://github.com/acme/widgets/archive/refs/tags/v1.zip",
            "github",
            "tag_archive",
        ),
        ("https://huggingface.co/acme/cool-model", "huggingface", "hf_repo"),
        ("https://huggingface.co/acme/cool-model/tree/main", "huggingface", "hf_repo"),
        (
            "https://huggingface.co/acme/cool-model/blob/main/weights.safetensors",
            "huggingface",
            "hf_file",
        ),
        (
            "https://huggingface.co/acme/cool-model/resolve/main/weights.safetensors",
            "huggingface",
            "hf_file",
        ),
        ("hf://acme/cool-model@main/weights.safetensors", "huggingface", "hf_file"),
    ],
)
def test_parse_supported_urls(url: str, provider: str, kind: str) -> None:
    parsed = parse_source_url(url)
    assert parsed.provider == provider
    assert parsed.kind == kind


def test_http_rejected_outside_fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    with pytest.raises(SourceSecurityError) as exc:
        validate_remote_url("http://github.com/acme/widgets")
    assert exc.value.code == "url_scheme_rejected"


def test_localhost_rejected_outside_fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    with pytest.raises(SourceSecurityError) as exc:
        validate_remote_url("https://127.0.0.1/pack.zip")
    assert exc.value.code in {"url_localhost_rejected", "url_private_ip_rejected", "url_host_rejected"}


def test_private_ip_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    with pytest.raises(SourceSecurityError):
        validate_remote_url("https://10.0.0.5/secret.zip")


def test_file_scheme_rejected() -> None:
    with pytest.raises(SourceSecurityError) as exc:
        validate_remote_url("file:///C:/temp/pack.zip")
    assert exc.value.code == "url_scheme_rejected"


def test_cli_mock_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ADEPT_CLI_MOCK_JSON",
        json.dumps(
            {
                "github": {
                    "status": "Ready",
                    "cli_detected": True,
                    "executable_path": "C:/mock/gh.exe",
                    "executable_name": "gh",
                    "version": "2.40.0",
                    "authenticated": True,
                    "account_name": "adept-tester",
                    "token_available": True,
                    "message": "GitHub CLI is ready and authenticated.",
                }
            }
        ),
    )
    result = detect_github_cli()
    assert result.status == "Ready"
    assert result.authenticated is True
    assert result.account_name == "adept-tester"
    assert "ghp_" not in json.dumps(result.to_dict())


def test_cli_mock_hf_legacy_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ADEPT_CLI_MOCK_JSON",
        json.dumps(
            {
                "huggingface": {
                    "status": "Installed but not authenticated",
                    "cli_detected": True,
                    "executable_path": "C:/mock/huggingface-cli.exe",
                    "executable_name": "huggingface-cli",
                    "version": "0.20.0",
                    "authenticated": False,
                    "account_name": None,
                    "token_available": False,
                    "message": "The CLI is installed, but this source may require you to sign in.",
                }
            }
        ),
    )
    result = detect_huggingface_cli()
    assert result.executable_name == "huggingface-cli"
    assert result.authenticated is False


def test_branch_archive_blocked_for_pack_component() -> None:
    from app.setup.download_sources.service import verify_source_url

    result = verify_source_url(
        url="https://github.com/acme/widgets/archive/refs/heads/main.zip",
        component_id="pack_essential_cinematic",
    )
    assert result["ok"] is False
    assert any("Source archives" in err["message"] for err in result["blocking_errors"])


def test_source_override_roundtrip(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.setup.download_sources.overrides import get_override, remove_override, save_override
    from app.setup.download_sources.service import apply_verified_override

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    verification = {
        "ok": True,
        "source": {
            "provider": "github",
            "source_url": "https://github.com/acme/widgets/releases/download/v1/pack.zip",
            "asset_name": "pack.zip",
        },
        "repository": "acme/widgets",
        "revision": "v1",
        "selected_file": "pack.zip",
        "installation_method": "direct_http",
        "verification_fingerprint": "abc",
    }
    saved = apply_verified_override("pack_essential_photoreal", verification)
    assert saved["userDefined"] is True
    assert get_override("pack_essential_photoreal")["sourceUrl"].endswith("pack.zip")
    assert remove_override("pack_essential_photoreal") is True
    assert get_override("pack_essential_photoreal") is None
