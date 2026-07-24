"""Component installation registry: unpublished packs + credential actions."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def isolated_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "studio-data"
    data.mkdir()
    monkeypatch.setenv("STUDIO_DATA_DIR", str(data))
    monkeypatch.delenv("ADEPT_PACK_PROVIDER", raising=False)
    monkeypatch.delenv("ADEPT_PACK_FIXTURE_BASE_URL", raising=False)
    monkeypatch.delenv("ADEPT_PACK_GITHUB_OWNER", raising=False)
    monkeypatch.delenv("ADEPT_PACK_GITHUB_REPOSITORY", raising=False)
    from app.config import settings

    settings.data_dir = data
    from app.setup.pack_manifests import clear_manifest_cache, clear_source_overrides

    clear_manifest_cache()
    clear_source_overrides()
    yield data
    clear_manifest_cache()
    clear_source_overrides()


def test_essential_packs_are_not_published(isolated_data: Path):
    from app.setup.pack_manifests import load_pack_manifest

    for pack_id in (
        "pack_essential_photoreal",
        "pack_essential_anime",
        "pack_essential_cinematic",
    ):
        manifest = load_pack_manifest(pack_id)
        assert manifest.distribution_status == "not_published"
        assert not manifest.is_published()
        assert not manifest.has_valid_source()


def test_global_github_env_does_not_validate_unpublished_pack(isolated_data: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_PACK_GITHUB_OWNER", "acme")
    monkeypatch.setenv("ADEPT_PACK_GITHUB_REPOSITORY", "assets")
    from app.setup.pack_manifests import clear_manifest_cache, load_pack_manifest
    from app.setup.pack_settings import clear_pack_settings_cache

    clear_pack_settings_cache()
    clear_manifest_cache()
    manifest = load_pack_manifest("pack_essential_anime")
    assert not manifest.has_valid_source()


def test_fixture_http_still_validates_unpublished_pack(isolated_data: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_PACK_PROVIDER", "fixture_http")
    monkeypatch.setenv("ADEPT_PACK_FIXTURE_BASE_URL", "http://127.0.0.1:8765")
    from app.setup.pack_manifests import clear_manifest_cache, load_pack_manifest
    from app.setup.pack_settings import clear_pack_settings_cache

    clear_pack_settings_cache()
    clear_manifest_cache()
    manifest = load_pack_manifest("pack_essential_cinematic")
    assert manifest.has_valid_source()


def test_status_marks_unpublished_as_source_pending(isolated_data: Path):
    from app.setup.status import build_status

    status = build_status()
    by_id = {item["id"]: item for item in status["components"]}
    for pack_id in (
        "pack_essential_photoreal",
        "pack_essential_anime",
        "pack_essential_cinematic",
    ):
        item = by_id[pack_id]
        assert item["status"] == "source_pending"
        assert item["issue_code"] == "source_not_published"
        assert item.get("install_disabled") is True
        assert item["source_state"] == "source_not_published"
        assert "ADEPT_PACK_GITHUB_OWNER" not in (item.get("issue_summary") or "")
        labels = " ".join(a["label"] for a in (item.get("pack_actions") or []))
        assert "Add Source URL" in labels
        assert "Link Existing Folder" in labels


def test_fal_key_primary_action_is_configure_api_key(isolated_data: Path):
    from app.setup.status import build_status

    status = build_status()
    fal = next(item for item in status["components"] if item["id"] == "fal_key")
    assert fal["component_kind"] == "credential"
    assert fal["show_download_sizes"] is False
    assert fal["primary_action"]["action"] == "configure"
    assert fal["primary_action"]["label"] == "Configure API Key"
    assert fal["primary_action"]["label"] != "Download and Install"
    assert fal["download_bytes"] == 0


def test_component_kind_mapping():
    from app.setup.catalog import get_component
    from app.setup.component_kinds import (
        KIND_CREDENTIAL,
        KIND_DOWNLOADABLE_PACK,
        KIND_LINKED_RESOURCE,
        component_kind,
    )

    assert component_kind(get_component("fal_key")) == KIND_CREDENTIAL
    assert component_kind(get_component("pack_essential_photoreal")) == KIND_DOWNLOADABLE_PACK
    assert component_kind(get_component("ltx_checkpoint")) == KIND_LINKED_RESOURCE


def test_manual_override_makes_pack_installable(isolated_data: Path):
    from app.setup.pack_manifests import clear_manifest_cache, get_pack_manifest, set_source_override
    from app.setup.status import build_status

    set_source_override(
        "pack_essential_photoreal",
        "https://github.com/acme/widgets/releases/download/v1/pack.zip",
    )
    clear_manifest_cache()
    manifest = get_pack_manifest("pack_essential_photoreal")
    assert manifest.has_valid_source()
    status = build_status()
    item = next(c for c in status["components"] if c["id"] == "pack_essential_photoreal")
    # Override URL counts as available source even without a release cache
    assert item["source_available"] is True
    assert item["status"] in ("not_installed", "source_pending", "download_unavailable")
