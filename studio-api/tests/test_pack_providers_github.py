from __future__ import annotations

import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


@pytest.fixture()
def setup_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup.pack_manifests import clear_manifest_cache, clear_source_overrides
    from app.setup.pack_release_cache import clear_cached_release
    from app.setup.pack_settings import clear_pack_settings_cache

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "comfy_input_dir", tmp_path / "missing-comfy" / "input")
    if hasattr(settings, "comfy_models_dir"):
        monkeypatch.setattr(settings, "comfy_models_dir", None)
    clear_manifest_cache()
    clear_source_overrides()
    clear_cached_release()
    clear_pack_settings_cache()
    yield tmp_path
    clear_source_overrides()
    clear_manifest_cache()
    clear_cached_release()
    clear_pack_settings_cache()


def _configure_github(monkeypatch: pytest.MonkeyPatch, owner: str = "adept-ui", repo: str = "gen-studio-packs") -> None:
    from app.setup import pack_settings

    monkeypatch.setenv("ADEPT_PACK_GITHUB_OWNER", owner)
    monkeypatch.setenv("ADEPT_PACK_GITHUB_REPOSITORY", repo)
    monkeypatch.setenv("ADEPT_PACK_PROVIDER", "github_releases")
    pack_settings.clear_pack_settings_cache()


class _GitHubFixture(BaseHTTPRequestHandler):
    releases_payload: list = []
    assets: dict[str, bytes] = {}
    status_map: dict[str, int] = {}

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        status = self.status_map.get(path, 200)
        if path.startswith("/repos/") and ("/releases" in path):
            body = json.dumps(self.releases_payload).encode()
        elif path.startswith("/repos/") and path.count("/") == 3:
            # GET /repos/{owner}/{repo}
            body = b'{"id":1,"full_name":"fixture/repo"}'
        elif path in self.assets:
            body = self.assets[path]
        else:
            status = self.status_map.get(path, 404)
            body = b'{"message":"Not Found"}'
        self.send_response(status)
        if status == 403:
            self.send_header("X-RateLimit-Remaining", "0")
            self.send_header("X-RateLimit-Reset", "9999999999")
        is_json = "/releases" in path or (path.startswith("/repos/") and path.count("/") == 3)
        self.send_header("Content-Type", "application/json" if is_json else "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _serve_github(releases: list, assets: dict[str, bytes], status_map: dict[str, int] | None = None):
    handler = type(
        "H",
        (_GitHubFixture,),
        {"releases_payload": [], "assets": assets, "status_map": status_map or {}},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    rewritten = []
    for release in releases:
        item = dict(release)
        assets_out = []
        for asset in release.get("assets") or []:
            entry = dict(asset)
            url = str(entry.get("browser_download_url") or "")
            if url.startswith("/"):
                entry["browser_download_url"] = base + url
            else:
                entry["browser_download_url"] = url.replace("{base}", base)
            assets_out.append(entry)
        item["assets"] = assets_out
        rewritten.append(item)
    handler.releases_payload = rewritten
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, base


def test_missing_provider_configuration(setup_data_dir: Path) -> None:
    from app.setup.pack_manifests import refresh_pack_source
    from app.setup.status import build_status

    result = refresh_pack_source("pack_essential_photoreal")
    assert result["error"]["code"] == "pack_provider_not_configured"
    status = build_status()
    pack = next(c for c in status["components"] if c["id"] == "pack_essential_photoreal")
    # Honest unavailable states: source still pending configuration, or download unavailable.
    assert pack["status"] in {"download_unavailable", "source_pending"}
    assert pack["install_disabled"] is True


def test_stable_ignores_prereleases(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.pack_install import make_test_zip_bytes
    from app.setup.pack_providers import github_releases as gh

    _configure_github(monkeypatch)
    zip_bytes = make_test_zip_bytes(("pack.json",), pack_id="pack_essential_photoreal", version="1.0.0")
    digest = hashlib.sha256(zip_bytes).hexdigest()
    release_json = {
        "schemaVersion": 1,
        "packId": "pack_essential_photoreal",
        "version": "1.0.0",
        "channel": "stable",
        "minimumStudioVersion": "0.1.0",
        "archive": {
            "assetName": "pack_essential_photoreal-1.0.0.zip",
            "format": "zip",
            "expectedBytes": len(zip_bytes),
            "checksumAlgorithm": "sha256",
            "checksum": digest,
        },
        "install": {"requiredFiles": ["pack.json"]},
    }
    meta_bytes = json.dumps(release_json).encode()
    server, base = _serve_github(
        releases=[
            {
                "id": 1,
                "tag_name": "packs-v1.0.0-rc1",
                "draft": False,
                "prerelease": True,
                "assets": [
                    {
                        "id": 11,
                        "name": "pack_essential_photoreal-1.0.0.release.json",
                        "size": len(meta_bytes),
                        "browser_download_url": "/meta.json",
                    },
                    {
                        "id": 12,
                        "name": "pack_essential_photoreal-1.0.0.zip",
                        "size": len(zip_bytes),
                        "browser_download_url": "/pack.zip",
                    },
                ],
            }
        ],
        assets={"/meta.json": meta_bytes, "/pack.zip": zip_bytes},
    )
    try:
        monkeypatch.setattr(gh, "GITHUB_API", base)
        # Allow http localhost for metadata download host check in tests
        monkeypatch.setattr(
            gh,
            "ALLOWED_DOWNLOAD_HOSTS",
            gh.ALLOWED_DOWNLOAD_HOSTS | {"127.0.0.1", "localhost"},
        )
        provider = gh.GitHubReleasePackProvider()
        assert provider.get_latest_release("pack_essential_photoreal", "stable", "0.1.0", force_refresh=True) is None
        found = provider.get_latest_release("pack_essential_photoreal", "beta", "0.1.0", force_refresh=True)
        assert found is not None
        assert found.version == "1.0.0"
    finally:
        server.shutdown()


def test_public_release_lookup_and_install(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.pack_install import make_test_zip_bytes
    from app.setup.pack_manifests import refresh_pack_source
    from app.setup.pack_providers import github_releases as gh
    from app.setup.status import build_status

    _configure_github(monkeypatch)
    zip_bytes = make_test_zip_bytes(("pack.json", "README.md"), pack_id="pack_essential_anime", version="1.0.0")
    digest = hashlib.sha256(zip_bytes).hexdigest()
    release_json = {
        "schemaVersion": 1,
        "packId": "pack_essential_anime",
        "version": "1.0.0",
        "channel": "stable",
        "minimumStudioVersion": "0.1.0",
        "archive": {
            "assetName": "pack_essential_anime-1.0.0.zip",
            "format": "zip",
            "expectedBytes": len(zip_bytes),
            "checksumAlgorithm": "sha256",
            "checksum": digest,
        },
        "install": {"requiredFiles": ["pack.json"]},
    }
    meta_bytes = json.dumps(release_json).encode()
    server, base = _serve_github(
        releases=[
            {
                "id": 9,
                "tag_name": "packs-v1.0.0",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "id": 91,
                        "name": "pack_essential_anime-1.0.0.release.json",
                        "size": len(meta_bytes),
                        "browser_download_url": "/meta.json",
                    },
                    {
                        "id": 92,
                        "name": "pack_essential_anime-1.0.0.zip",
                        "size": len(zip_bytes),
                        "browser_download_url": "/pack.zip",
                    },
                ],
            }
        ],
        assets={"/meta.json": meta_bytes, "/pack.zip": zip_bytes},
    )
    try:
        monkeypatch.setattr(gh, "GITHUB_API", base)
        monkeypatch.setattr(
            gh,
            "ALLOWED_DOWNLOAD_HOSTS",
            gh.ALLOWED_DOWNLOAD_HOSTS | {"127.0.0.1", "localhost"},
        )
        from app.setup.pack_manifests import validate_download_url as vdu
        from app.setup import pack_manifests

        # Allow http localhost downloads in install path for this test.
        monkeypatch.setattr(
            pack_manifests,
            "ALLOWED_DOWNLOAD_HOSTS",
            pack_manifests.ALLOWED_DOWNLOAD_HOSTS | {"127.0.0.1", "localhost"},
        )

        refreshed = refresh_pack_source("pack_essential_anime", force_refresh=True)
        assert refreshed["source_available"] is True
        assert refreshed["available_version"] == "1.0.0"
        assert "://" not in json.dumps(refreshed)

        local_registry = OperationRegistry()
        monkeypatch.setattr(orchestrator, "registry", local_registry)
        snapshot = orchestrator.execute_recommended_action("pack_essential_anime")
        operation_id = snapshot["operation_id"]
        deadline = time.monotonic() + 8
        snapshot = local_registry.snapshot(operation_id)
        while snapshot["status"] != "awaiting_checkpoint" and time.monotonic() < deadline:
            time.sleep(0.02)
            snapshot = local_registry.snapshot(operation_id)
        assert snapshot["status"] == "awaiting_checkpoint"
        assert snapshot["checkpoint"]["workflow"] == "download_install"
        dest = setup_data_dir / "install_anime"
        dest.mkdir()
        orchestrator.respond_to_checkpoint(
            operation_id,
            {"checkpoint_id": snapshot["checkpoint"]["checkpoint_id"], "path": str(dest)},
        )
        deadline = time.monotonic() + 8
        snapshot = local_registry.snapshot(operation_id)
        while snapshot["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
            time.sleep(0.02)
            snapshot = local_registry.snapshot(operation_id)
        assert snapshot["status"] == "completed", snapshot.get("error")
        status = build_status()
        pack = next(c for c in status["components"] if c["id"] == "pack_essential_anime")
        assert pack["status"] == "ready"
        assert pack["installed_bytes"] > 0
    finally:
        server.shutdown()


def test_github_rate_limit_separate_code(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.pack_manifests import refresh_pack_source
    from app.setup.pack_providers import github_releases as gh

    _configure_github(monkeypatch)
    server, base = _serve_github(
        releases=[],
        assets={},
        status_map={"/repos/adept-ui/gen-studio-packs/releases": 403},
    )
    try:
        monkeypatch.setattr(gh, "GITHUB_API", base)
        result = refresh_pack_source("pack_essential_cinematic", force_refresh=True)
        assert result["error"]["code"] == "github_rate_limited"
    finally:
        server.shutdown()


def test_builder_rejects_empty_and_generates_checksum(setup_data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import pack_builder

    empty_root = tmp_path / "sources"
    empty = empty_root / "empty_pack"
    empty.mkdir(parents=True)
    (empty / "pack.json").write_text('{"id":"empty_pack","version":"1.0.0"}', encoding="utf-8")
    (empty / "README.md").write_text("x", encoding="utf-8")
    real_sources = pack_builder.SOURCES_ROOT
    real_ids = pack_builder.ASSET_PACK_IDS
    monkeypatch.setattr(pack_builder, "SOURCES_ROOT", empty_root)
    monkeypatch.setattr(pack_builder, "ASSET_PACK_IDS", ("empty_pack",))
    with pytest.raises(SystemExit):
        pack_builder.build_pack("empty_pack")

    monkeypatch.setattr(pack_builder, "SOURCES_ROOT", real_sources)
    monkeypatch.setattr(pack_builder, "ASSET_PACK_IDS", real_ids)
    result = pack_builder.build_pack("pack_essential_photoreal")
    zip_path = Path(result["zip_path"])
    assert zip_path.is_file()
    assert result["checksum"] == hashlib.sha256(zip_path.read_bytes()).hexdigest()
    meta = json.loads(Path(result["release_json_path"]).read_text(encoding="utf-8"))
    assert meta["archive"]["expectedBytes"] == result["expected_bytes"]
    assert meta["archive"]["checksum"] == result["checksum"]


def test_cache_expiry_and_check_again_bypass(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.pack_release_cache import get_cached_release, put_cached_release
    from app.setup.pack_settings import clear_pack_settings_cache

    put_cached_release(
        "pack_essential_photoreal",
        {
            "provider_id": "github_releases",
            "repository": "adept-ui/gen-studio-packs",
            "version": "1.0.0",
            "channel": "stable",
            "expected_bytes": 10,
            "checksum": "abc",
            "required_files": ["pack.json"],
        },
    )
    assert get_cached_release("pack_essential_photoreal") is not None
    monkeypatch.setenv("ADEPT_PACK_CACHE_TTL_SECONDS", "0")
    clear_pack_settings_cache()
    # TTL 0 means immediately expired
    from app.setup import pack_settings as ps

    monkeypatch.setattr(ps.pack_settings(), "cache_ttl_seconds", 0)
    assert get_cached_release("pack_essential_photoreal") is None
