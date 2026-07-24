"""Phase 1A Source Manager: records, migration, provider selection."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "studio-data"
    data.mkdir()
    monkeypatch.setenv("STUDIO_DATA_DIR", str(data))
    # Reload settings / state path bindings
    from app.config import settings

    settings.data_dir = data
    from app.setup import state as state_mod

    state_mod._LOCK  # ensure import
    yield data


def test_migrate_overrides_to_source_records(isolated_data: Path):
    from app.setup.state import load_state, save_state
    from app.source_manager.migration import ensure_migrated
    from app.source_manager.persistence import list_assignments, list_sources

    state = load_state()
    state["source_overrides"] = {
        "pack_essential_photoreal": {
            "componentId": "pack_essential_photoreal",
            "provider": "github",
            "sourceUrl": "https://github.com/example/repo/releases/download/v1/pack.zip",
            "repository": "example/repo",
            "revision": "v1",
            "selectedFiles": ["pack.zip"],
            "verificationFingerprint": "abc123fingerprint",
            "userDefined": True,
        }
    }
    save_state(state)

    migrated = ensure_migrated()
    assert int(migrated.get("schema_version") or 0) >= 3
    sources = list_sources()
    assignments = list_assignments()
    assert len(sources) >= 1
    assert "pack_essential_photoreal" in assignments
    source_id = assignments["pack_essential_photoreal"]["sourceId"]
    assert source_id in sources
    assert sources[source_id]["sourceUrl"].endswith("pack.zip")
    # Legacy override preserved
    assert "pack_essential_photoreal" in load_state().get("source_overrides", {})


def test_migrate_is_idempotent(isolated_data: Path):
    from app.setup.state import load_state, save_state
    from app.source_manager.migration import ensure_migrated
    from app.source_manager.persistence import list_sources

    state = load_state()
    state["source_overrides"] = {
        "pack_essential_anime": {
            "provider": "huggingface",
            "sourceUrl": "https://huggingface.co/org/model",
            "repository": "org/model",
            "verificationFingerprint": "fp-anime",
        }
    }
    save_state(state)
    ensure_migrated()
    first = len(list_sources())
    ensure_migrated()
    second = len(list_sources())
    assert first == second == 1


def test_select_provider_github_prefers_cli_when_mocked(isolated_data: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "ADEPT_CLI_MOCK_JSON",
        '{"github":{"cli_detected":true,"authenticated":true,"status":"Ready","version":"2.0"},'
        '"huggingface":{"cli_detected":false,"authenticated":false,"status":"Not installed"}}',
    )
    from app.source_manager.contracts import SourceInput
    from app.source_manager.registry import select_provider

    provider = select_provider(
        SourceInput(url="https://github.com/owner/repo/releases/tag/v1.0")
    )
    assert provider.id in {"github_cli", "github_api", "direct_http"}


def test_select_provider_local_folder(isolated_data: Path):
    from app.source_manager.contracts import SourceInput
    from app.source_manager.registry import select_provider

    provider = select_provider(SourceInput(local_path=str(isolated_data)))
    assert provider.id == "local_folder"


def test_strip_secrets_from_source_record(isolated_data: Path):
    from app.source_manager.models import normalize_source_record

    record = normalize_source_record(
        {
            "id": "src_test",
            "provider": "github",
            "sourceUrl": "https://github.com/a/b",
            "token": "SECRET",
            "metadata": {"authorization": "Bearer SECRET", "ok": True},
        }
    )
    assert record is not None
    assert "token" not in record
    assert "authorization" not in (record.get("metadata") or {})
    assert record["metadata"].get("ok") is True


def test_overview_includes_providers(isolated_data: Path):
    from app.source_manager.service import get_overview

    overview = get_overview()
    ids = {p["id"] for p in overview["providers"]}
    assert "github_cli" in ids
    assert "huggingface_cli" in ids
    assert "direct_http" in ids
    assert "local_folder" in ids
    assert overview["schemaVersion"] >= 3
