"""Twelve critical tests for Download/Install vs Link Existing pack workflows."""

from __future__ import annotations

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


def _pack_json(pack_id: str, version: str = "1.0.0") -> str:
    return json.dumps({"id": pack_id, "version": version, "schemaVersion": 1})


def _wait_status(registry, operation_id: str, statuses: set[str], timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    snapshot = registry.snapshot(operation_id)
    while snapshot["status"] not in statuses and time.monotonic() < deadline:
        time.sleep(0.02)
        snapshot = registry.snapshot(operation_id)
    return snapshot


class _FixtureHandler(BaseHTTPRequestHandler):
    payload = b""
    status = 200
    content_type = "application/zip"

    def do_GET(self) -> None:  # noqa: N802
        body = self.payload
        self.send_response(self.status)
        self.send_header("Content-Type", self.content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.status < 400:
            self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _serve(payload: bytes, *, status: int = 200, content_type: str = "application/zip"):
    handler = type(
        "Handler",
        (_FixtureHandler,),
        {"payload": payload, "status": status, "content_type": content_type},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/pack.zip"
    return server, url


# --- 1 ------------------------------------------------------------------


def test_empty_folder_accepted_as_install_destination(setup_data_dir: Path) -> None:
    from app.setup.pack_install import validate_install_destination

    empty = setup_data_dir / "new_install"
    empty.mkdir()
    result = validate_install_destination("pack_essential_photoreal", str(empty))
    assert result["destination"] == str(empty)
    assert result["empty"] is True

    missing = setup_data_dir / "creatable_install"
    result2 = validate_install_destination("pack_essential_photoreal", str(missing))
    assert result2["destination"] == str(missing)
    assert result2["empty"] is True
    # Creatable destinations are not pre-created as empty pack roots.
    assert not missing.exists()


# --- 2 ------------------------------------------------------------------


def test_empty_folder_rejected_for_link_existing(setup_data_dir: Path) -> None:
    from app.setup.pack_install import PackInstallError, link_existing_pack

    empty = setup_data_dir / "empty_link"
    empty.mkdir()
    with pytest.raises(PackInstallError) as exc:
        link_existing_pack("pack_essential_anime", str(empty))
    assert exc.value.code == "empty_folder"


# --- 3 ------------------------------------------------------------------


def test_valid_existing_pack_folder_accepted(setup_data_dir: Path) -> None:
    from app.setup.pack_install import link_existing_pack

    target = setup_data_dir / "valid_pack"
    target.mkdir()
    (target / "pack.json").write_text(_pack_json("pack_essential_cinematic"), encoding="utf-8")
    result = link_existing_pack("pack_essential_cinematic", str(target))
    assert result["destination"] == str(target)
    assert result["installed_bytes"] > 0


# --- 4 ------------------------------------------------------------------


def test_existing_folder_missing_pack_json_rejected(setup_data_dir: Path) -> None:
    from app.setup.pack_install import PackInstallError, link_existing_pack

    target = setup_data_dir / "no_manifest"
    target.mkdir()
    (target / "readme.txt").write_text("not a pack", encoding="utf-8")
    with pytest.raises(PackInstallError) as exc:
        link_existing_pack("pack_essential_anime", str(target))
    assert exc.value.code == "pack_json_missing"


# --- 5 ------------------------------------------------------------------


def test_existing_folder_wrong_pack_id_rejected(setup_data_dir: Path) -> None:
    from app.setup.pack_install import PackInstallError, link_existing_pack

    target = setup_data_dir / "wrong_id"
    target.mkdir()
    (target / "pack.json").write_text(_pack_json("pack_essential_photoreal"), encoding="utf-8")
    with pytest.raises(PackInstallError) as exc:
        link_existing_pack("pack_essential_anime", str(target))
    assert exc.value.code == "pack_id_mismatch"


# --- 6 ------------------------------------------------------------------


def test_github_repo_exists_but_no_releases(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.pack_providers import github_releases as gh
    from app.setup.pack_settings import clear_pack_settings_cache

    monkeypatch.setenv("ADEPT_PACK_GITHUB_OWNER", "adept-ui")
    monkeypatch.setenv("ADEPT_PACK_GITHUB_REPOSITORY", "empty-packs")
    clear_pack_settings_cache()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]
            if path.startswith("/repos/") and path.endswith("/releases"):
                body = b"[]"
            elif path.startswith("/repos/"):
                body = b'{"id":1}'
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        monkeypatch.setattr(gh, "GITHUB_API", base)
        provider = gh.GitHubReleasePackProvider()
        diag = provider.diagnose_releases(
            "pack_essential_anime", "stable", "0.1.0", force_refresh=True
        )
        assert diag["repo_found"] is True
        assert diag["releases_found"] == 0
        assert diag["release"] is None
        assert "no published releases" in (diag["selection_reason"] or "").lower()
    finally:
        server.shutdown()


# --- 7 ------------------------------------------------------------------


def test_release_exists_but_no_matching_asset(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.pack_providers import github_releases as gh
    from app.setup.pack_settings import clear_pack_settings_cache

    monkeypatch.setenv("ADEPT_PACK_GITHUB_OWNER", "adept-ui")
    monkeypatch.setenv("ADEPT_PACK_GITHUB_REPOSITORY", "mismatch-packs")
    clear_pack_settings_cache()

    releases = [
        {
            "id": 1,
            "tag_name": "packs-v1.0.0",
            "draft": False,
            "prerelease": False,
            "assets": [
                {"id": 11, "name": "other-pack-1.0.0.zip", "size": 10, "browser_download_url": "https://example/x"},
            ],
        }
    ]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]
            if path.startswith("/repos/") and "/releases" in path:
                body = json.dumps(releases).encode()
            elif path.startswith("/repos/"):
                body = b'{"id":1}'
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        monkeypatch.setattr(gh, "GITHUB_API", base)
        provider = gh.GitHubReleasePackProvider()
        diag = provider.diagnose_releases(
            "pack_essential_cinematic", "stable", "0.1.0", force_refresh=True
        )
        assert diag["repo_found"] is True
        assert diag["releases_found"] == 1
        assert diag["release"] is None
        assert "pack_essential_cinematic-*.release.json" in (diag["expected_asset_pattern"] or "")
        assert "no asset matching" in (diag["selection_reason"] or "").lower()
        assert "other-pack-1.0.0.zip" in (diag["available_asset_names"] or [])
    finally:
        server.shutdown()


# --- 8 ------------------------------------------------------------------


def test_download_failure_records_failed_op_without_killing_server(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.pack_manifests import set_source_override

    server, url = _serve(b"nope", status=403)
    try:
        set_source_override("pack_essential_photoreal", url)
        local_registry = OperationRegistry()
        monkeypatch.setattr(orchestrator, "registry", local_registry)

        snapshot = orchestrator.execute_recommended_action("pack_essential_photoreal")
        operation_id = snapshot["operation_id"]
        snapshot = _wait_status(local_registry, operation_id, {"awaiting_checkpoint"})
        assert snapshot["checkpoint"]["workflow"] == "download_install"
        assert "pack.json" not in (snapshot["checkpoint"]["summary"] or "").lower() or "required: pack.json" not in (
            snapshot["checkpoint"]["summary"] or ""
        )

        dest = setup_data_dir / "dl_fail"
        dest.mkdir()
        orchestrator.respond_to_checkpoint(
            operation_id,
            {"checkpoint_id": snapshot["checkpoint"]["checkpoint_id"], "path": str(dest)},
        )
        snapshot = _wait_status(local_registry, operation_id, {"failed", "completed"})
        assert snapshot["status"] == "failed"
        assert "403" in (snapshot.get("error") or "")

        # Server/registry still usable after failure.
        alive = local_registry.create("component_action", ["pack_essential_photoreal"])
        assert alive["operation_id"] != operation_id
    finally:
        server.shutdown()


# --- 9 ------------------------------------------------------------------


def test_extraction_failure_records_failed_op_without_killing_server(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.pack_manifests import set_source_override

    # Valid zip bytes that are not a zip archive → extract_failed / archive_invalid
    server, url = _serve(b"not-a-real-zip-archive-content!!", content_type="application/zip")
    try:
        set_source_override("pack_essential_anime", url)
        local_registry = OperationRegistry()
        monkeypatch.setattr(orchestrator, "registry", local_registry)

        snapshot = orchestrator.execute_recommended_action("pack_essential_anime")
        operation_id = snapshot["operation_id"]
        snapshot = _wait_status(local_registry, operation_id, {"awaiting_checkpoint"})
        dest = setup_data_dir / "extract_fail"
        dest.mkdir()
        orchestrator.respond_to_checkpoint(
            operation_id,
            {"checkpoint_id": snapshot["checkpoint"]["checkpoint_id"], "path": str(dest)},
        )
        snapshot = _wait_status(local_registry, operation_id, {"failed", "completed"})
        assert snapshot["status"] == "failed"
        assert snapshot.get("error")
        # Half-extracted content must not look like a linked install.
        assert not (dest / "pack.json").exists()
        alive = local_registry.create("healthcheck", ["python"])
        assert alive["status"] == "queued"
    finally:
        server.shutdown()


# --- 10 -----------------------------------------------------------------


def test_backend_restart_converts_stale_configuring_ops(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup.operations import OperationRegistry, recover_stale_operations
    from app.setup.state import load_state

    registry = OperationRegistry()
    monkeypatch.setattr("app.setup.operations.registry", registry)
    op = registry.create("component_action", ["pack_essential_cinematic"])
    registry.update(
        op["operation_id"],
        status="running",
        phase="configuring",
        stage="Configuring…",
    )
    # Simulate API restart: new registry loads persisted ops and marks them interrupted.
    fresh = OperationRegistry()
    monkeypatch.setattr("app.setup.operations.registry", fresh)
    # Access snapshot to force load; recover is also safe/idempotent.
    snap = fresh.snapshot(op["operation_id"])
    assert snap["status"] == "interrupted"
    assert snap["recoverable"] is True
    assert "Estimating" not in (snap.get("stage") or "")
    assert "Configuring" not in (snap.get("stage") or "") or "Interrupted" in (snap.get("stage") or "")
    recovered = recover_stale_operations()
    assert recovered == []  # already recovered on load
    persisted = load_state().get("operations", {}).get(op["operation_id"])
    assert persisted["status"] == "interrupted"


# --- 11 -----------------------------------------------------------------


def test_frontend_polling_backoff_helper() -> None:
    """Mirrors studio-web/src/setup/helpers.ts nextPollDelayMs contract."""

    def next_poll_delay_ms(consecutive_failures: int, base_ms: int = 1200, max_ms: int = 30000) -> int:
        if consecutive_failures <= 0:
            return base_ms
        exp = min(consecutive_failures, 6)
        return min(max_ms, base_ms * (2 ** (exp - 1)))

    assert next_poll_delay_ms(0) == 1200
    assert next_poll_delay_ms(1) == 1200
    assert next_poll_delay_ms(2) == 2400
    assert next_poll_delay_ms(3) == 4800
    assert next_poll_delay_ms(10) == 30000


# --- 12 -----------------------------------------------------------------


def test_retry_clears_stale_error_and_starts_fresh_operation(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.pack_manifests import set_source_override
    from app.setup.state import update_state

    server, url = _serve(b"nope", status=404)
    try:
        set_source_override("pack_essential_cinematic", url)
        local_registry = OperationRegistry()
        monkeypatch.setattr(orchestrator, "registry", local_registry)

        first = orchestrator.execute_recommended_action("pack_essential_cinematic")
        first_id = first["operation_id"]
        snap = _wait_status(local_registry, first_id, {"awaiting_checkpoint"})
        dest = setup_data_dir / "retry_dest"
        dest.mkdir()
        orchestrator.respond_to_checkpoint(
            first_id,
            {"checkpoint_id": snap["checkpoint"]["checkpoint_id"], "path": str(dest)},
        )
        snap = _wait_status(local_registry, first_id, {"failed", "completed"})
        assert snap["status"] == "failed"

        # Stale diagnostic/error present — Retry (install again) must start a new op.
        update_state(
            lambda state: state.setdefault("status", {}).setdefault(
                "pack_essential_cinematic", {}
            ).__setitem__(
                "diagnostic",
                {
                    "component_id": "pack_essential_cinematic",
                    "healthy": False,
                    "issue_code": "download_http_error",
                    "summary": "stale",
                    "recommendation": "install",
                },
            )
        )
        second = orchestrator.execute_recommended_action("pack_essential_cinematic")
        assert second["operation_id"] != first_id
        snap2 = _wait_status(local_registry, second["operation_id"], {"awaiting_checkpoint"})
        assert snap2["status"] == "awaiting_checkpoint"
        assert snap2.get("error") in (None, "")
        assert snap2["checkpoint"]["workflow"] == "download_install"
    finally:
        server.shutdown()


def test_install_checkpoint_copy_differs_from_link_existing(setup_data_dir: Path) -> None:
    from app.setup.orchestrator import _checkpoint_for, _install_destination_checkpoint, _link_existing_checkpoint

    install_ck = _checkpoint_for("pack_essential_photoreal", "install")
    link_ck = _checkpoint_for("pack_essential_photoreal", "link_existing")
    assert install_ck["workflow"] == "download_install"
    assert link_ck["workflow"] == "link_existing"
    assert "empty folder" in install_ck["summary"].lower() or "new folder" in install_ck["summary"].lower()
    assert "pack.json" in link_ck["summary"].lower()
    assert "required: pack.json" not in install_ck["summary"].lower()
    assert "empty folders are not accepted" not in install_ck["summary"].lower()
    assert _install_destination_checkpoint("pack_essential_anime")["action"] == "choose_install_location"
    assert _link_existing_checkpoint("pack_essential_anime")["action"] == "link_existing"
