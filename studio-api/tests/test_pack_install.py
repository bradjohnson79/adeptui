from __future__ import annotations

import hashlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


@pytest.fixture()
def setup_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup.pack_manifests import clear_manifest_cache, clear_source_overrides

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "comfy_input_dir", tmp_path / "missing-comfy" / "input")
    if hasattr(settings, "comfy_models_dir"):
        monkeypatch.setattr(settings, "comfy_models_dir", None)
    clear_manifest_cache()
    clear_source_overrides()
    yield tmp_path
    clear_source_overrides()
    clear_manifest_cache()


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


def test_empty_download_url_prevents_installation(setup_data_dir: Path) -> None:
    from app.setup.orchestrator import execute_recommended_action
    from app.setup.paths import suggested_install_path
    from app.setup.status import build_status

    suggested = Path(suggested_install_path("pack_essential_photoreal"))
    status = build_status()
    pack = next(c for c in status["components"] if c["id"] == "pack_essential_photoreal")
    assert pack["status"] == "source_pending"
    assert pack["installed_bytes"] == 0
    assert pack["primary_action"]["action"] == "add_source_url"

    result = execute_recommended_action("pack_essential_photoreal")
    assert result["status"] == "failed"
    assert result["error"] in {
        "download_source_missing",
        "pack_provider_not_configured",
        "pack_release_not_found",
        "source_not_published",
        "add_source_url_required",
    }
    assert not suggested.exists()


def test_refresh_source_does_not_create_folders(setup_data_dir: Path) -> None:
    from app.setup.orchestrator import refresh_component_source
    from app.setup.paths import suggested_install_path

    suggested = Path(suggested_install_path("pack_essential_anime"))
    result = refresh_component_source("pack_essential_anime")
    assert result["source_valid"] is False
    assert result["error"]["code"] in {"download_source_missing", "pack_provider_not_configured", "pack_release_not_found"}
    assert not suggested.exists()


def test_empty_destination_reports_zero_installed_bytes(setup_data_dir: Path) -> None:
    from app.setup.state import save_state
    from app.setup.status import build_status

    empty = setup_data_dir / "models" / "creative_assets" / "essential_cinematic"
    empty.mkdir(parents=True)
    save_state({"model_locations": {"pack_essential_cinematic": str(empty)}})
    status = build_status()
    pack = next(c for c in status["components"] if c["id"] == "pack_essential_cinematic")
    assert pack["status"] != "ready"
    assert pack["installed_bytes"] == 0
    assert pack["download_bytes"] > 0
    assert pack["installed_bytes"] != pack["download_bytes"]


def test_successful_zip_install_becomes_ready(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.pack_install import directory_byte_size, make_test_zip_bytes
    from app.setup.pack_manifests import get_pack_manifest, set_source_override
    from app.setup.status import build_status

    manifest = get_pack_manifest("pack_essential_photoreal")
    payload = make_test_zip_bytes(manifest.install.required_files, b"verified-pack-bytes")
    server, url = _serve(payload)
    try:
        set_source_override("pack_essential_photoreal", url)
        local_registry = OperationRegistry()
        monkeypatch.setattr(orchestrator, "registry", local_registry)

        snapshot = orchestrator.execute_recommended_action("pack_essential_photoreal")
        operation_id = snapshot["operation_id"]
        deadline = time.monotonic() + 5
        snapshot = local_registry.snapshot(operation_id)
        while snapshot["status"] != "awaiting_checkpoint" and time.monotonic() < deadline:
            time.sleep(0.02)
            snapshot = local_registry.snapshot(operation_id)
        assert snapshot["status"] == "awaiting_checkpoint"
        dest = setup_data_dir / "photoreal_dest"
        dest.mkdir()
        orchestrator.respond_to_checkpoint(
            operation_id,
            {"checkpoint_id": snapshot["checkpoint"]["checkpoint_id"], "path": str(dest)},
        )
        deadline = time.monotonic() + 5
        snapshot = local_registry.snapshot(operation_id)
        while snapshot["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
            time.sleep(0.02)
            snapshot = local_registry.snapshot(operation_id)

        assert snapshot["status"] == "completed", snapshot.get("error")
        status = build_status()
        pack = next(c for c in status["components"] if c["id"] == "pack_essential_photoreal")
        assert pack["status"] == "ready"
        assert pack["installed_bytes"] == directory_byte_size(Path(pack["installation_path"]))
        assert pack["installed_bytes"] > 0
        assert pack["installed_bytes"] != pack["estimated_installed_bytes"]
    finally:
        server.shutdown()


def test_http_403_fails_honestly(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.pack_manifests import set_source_override

    server, url = _serve(b"nope", status=403)
    try:
        set_source_override("pack_essential_anime", url)
        local_registry = OperationRegistry()
        monkeypatch.setattr(orchestrator, "registry", local_registry)
        snapshot = orchestrator.execute_recommended_action("pack_essential_anime")
        operation_id = snapshot["operation_id"]
        deadline = time.monotonic() + 5
        snapshot = local_registry.snapshot(operation_id)
        while snapshot["status"] != "awaiting_checkpoint" and time.monotonic() < deadline:
            time.sleep(0.02)
            snapshot = local_registry.snapshot(operation_id)
        dest = setup_data_dir / "anime_403"
        dest.mkdir()
        orchestrator.respond_to_checkpoint(
            operation_id,
            {"checkpoint_id": snapshot["checkpoint"]["checkpoint_id"], "path": str(dest)},
        )
        deadline = time.monotonic() + 5
        snapshot = local_registry.snapshot(operation_id)
        while snapshot["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
            time.sleep(0.02)
            snapshot = local_registry.snapshot(operation_id)
        assert snapshot["status"] == "failed"
        assert "403" in (snapshot.get("error") or "")
    finally:
        server.shutdown()


def test_http_404_fails_honestly(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.pack_manifests import set_source_override

    server, url = _serve(b"missing", status=404)
    try:
        set_source_override("pack_essential_cinematic", url)
        local_registry = OperationRegistry()
        monkeypatch.setattr(orchestrator, "registry", local_registry)
        snapshot = orchestrator.execute_recommended_action("pack_essential_cinematic")
        operation_id = snapshot["operation_id"]
        deadline = time.monotonic() + 5
        snapshot = local_registry.snapshot(operation_id)
        while snapshot["status"] != "awaiting_checkpoint" and time.monotonic() < deadline:
            time.sleep(0.02)
            snapshot = local_registry.snapshot(operation_id)
        dest = setup_data_dir / "cine_404"
        dest.mkdir()
        orchestrator.respond_to_checkpoint(
            operation_id,
            {"checkpoint_id": snapshot["checkpoint"]["checkpoint_id"], "path": str(dest)},
        )
        deadline = time.monotonic() + 5
        snapshot = local_registry.snapshot(operation_id)
        while snapshot["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
            time.sleep(0.02)
            snapshot = local_registry.snapshot(operation_id)
        assert snapshot["status"] == "failed"
        assert "404" in (snapshot.get("error") or "")
    finally:
        server.shutdown()


def test_html_masquerading_as_archive_fails(setup_data_dir: Path) -> None:
    from app.setup.pack_install import PackInstallError, download_to_file

    server, url = _serve(b"<!DOCTYPE html><html>error</html>", content_type="text/html")
    try:
        target = setup_data_dir / "bad.zip"
        with pytest.raises(PackInstallError) as exc:
            download_to_file(url, target)
        assert exc.value.code == "download_content_invalid"
        assert not target.exists()
    finally:
        server.shutdown()


def test_zero_byte_response_fails(setup_data_dir: Path) -> None:
    from app.setup.pack_install import PackInstallError, download_to_file

    server, url = _serve(b"", content_type="application/zip")
    try:
        with pytest.raises(PackInstallError) as exc:
            download_to_file(url, setup_data_dir / "empty.zip")
        assert exc.value.code == "download_zero_bytes"
    finally:
        server.shutdown()


def test_checksum_mismatch_fails(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup import pack_install
    from app.setup.pack_install import PackInstallError, install_asset_pack, make_test_zip_bytes
    from app.setup.pack_manifests import AssetPackManifest, PackArchive, PackInstallSpec, PackSource, set_source_override

    payload = make_test_zip_bytes(("pack.json",))
    server, url = _serve(payload)
    try:
        set_source_override("pack_essential_photoreal", url)
        wrong = hashlib.sha256(b"not-the-payload").hexdigest()
        bad = AssetPackManifest(
            id="pack_essential_photoreal",
            name="Essential Photoreal Pack",
            version="1.0.0",
            source=PackSource(type="http", url=url),
            archive=PackArchive(
                format="zip",
                checksum_algorithm="sha256",
                checksum=wrong,
                expected_download_bytes=None,
            ),
            install=PackInstallSpec(
                recommended_path="creative_assets/essential_photoreal",
                required_files=("pack.json",),
            ),
        )
        monkeypatch.setattr(pack_install, "get_pack_manifest", lambda _id: bad)
        with pytest.raises(PackInstallError) as exc:
            install_asset_pack("pack_essential_photoreal", "op-checksum")
        assert exc.value.code == "download_checksum_failed"
    finally:
        server.shutdown()


def test_missing_required_files_fails_final_verification(setup_data_dir: Path) -> None:
    from app.setup.pack_install import PackInstallError, install_asset_pack, make_test_zip_bytes
    from app.setup.pack_manifests import set_source_override
    from app.setup.paths import suggested_install_path

    # Zip without pack.json
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("readme.txt", "no pack json")
    server, url = _serve(buffer.getvalue())
    try:
        set_source_override("pack_essential_anime", url)
        with pytest.raises(PackInstallError) as exc:
            install_asset_pack("pack_essential_anime", "op-missing-files")
        assert exc.value.code == "required_files_missing"
        assert not Path(suggested_install_path("pack_essential_anime")).exists()
    finally:
        server.shutdown()


def test_failed_staging_leaves_final_directory_unchanged(setup_data_dir: Path) -> None:
    from app.setup.pack_install import PackInstallError, install_asset_pack
    from app.setup.pack_manifests import get_pack_manifest, set_source_override
    from app.setup.paths import recommended_pack_path

    final_dir = recommended_pack_path("pack_essential_cinematic")
    final_dir.mkdir(parents=True)
    marker = final_dir / "keep-me.bin"
    marker.write_bytes(b"original")

    server, url = _serve(b"<!DOCTYPE html>", content_type="text/html")
    try:
        set_source_override("pack_essential_cinematic", url)
        with pytest.raises(PackInstallError):
            install_asset_pack("pack_essential_cinematic", "op-rollback")
        assert marker.read_bytes() == b"original"
        assert list(final_dir.iterdir()) == [marker]
    finally:
        server.shutdown()


def test_stale_ready_downgraded_after_files_removed(setup_data_dir: Path) -> None:
    from app.setup.state import save_state
    from app.setup.status import build_status

    pack_dir = setup_data_dir / "models" / "creative_assets" / "essential_photoreal"
    pack_dir.mkdir(parents=True)
    pack_file = pack_dir / "pack.json"
    pack_file.write_text("{}", encoding="utf-8")
    save_state({"model_locations": {"pack_essential_photoreal": str(pack_dir)}})
    status = build_status()
    pack = next(c for c in status["components"] if c["id"] == "pack_essential_photoreal")
    assert pack["status"] == "ready"

    pack_file.unlink()
    status = build_status()
    pack = next(c for c in status["components"] if c["id"] == "pack_essential_photoreal")
    assert pack["status"] != "ready"
    assert pack["installed_bytes"] == 0


def test_invalid_url_prevents_directory_creation(setup_data_dir: Path) -> None:
    from app.setup.pack_manifests import PackInstallError, set_source_override
    from app.setup.paths import suggested_install_path

    with pytest.raises(PackInstallError):
        set_source_override("pack_essential_photoreal", "adept://marketplace/pack")
    assert not Path(suggested_install_path("pack_essential_photoreal")).exists()


def test_link_existing_populated_pack_passes(setup_data_dir: Path) -> None:
    from app.setup.pack_install import link_existing_pack

    target = setup_data_dir / "existing"
    target.mkdir()
    (target / "pack.json").write_text(
        '{"id":"pack_essential_anime","version":"1.0.0"}',
        encoding="utf-8",
    )
    result = link_existing_pack("pack_essential_anime", str(target))
    assert result["installed_bytes"] > 0
