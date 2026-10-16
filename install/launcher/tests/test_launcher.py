"""Universal Adept Launcher contract tests.

These run BEFORE any packaging. They drive the real launcher orchestrator and
worker against disposable install roots and disposable signed catalogs, proving:

- startup and installed-version discovery
- signed catalog verification (pinned RSA key path, patched to a test key)
- NO_UPDATE passthrough (no reinstall, app launches)
- update applied via a worker staged OUTSIDE the replaceable payload
- post-install registry verification and restart without reinstall
- failure recovery (checksum mismatch restores the installed app)
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

LAUNCHER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = LAUNCHER_DIR.parents[1]
for _p in (LAUNCHER_DIR, REPO_ROOT / "install" / "lifecycle"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from adept_lifecycle.manager import Layout, Lifecycle  # noqa: E402
from adept_lifecycle.release import sign_catalog_rsa  # noqa: E402
from adept_lifecycle.trust import generate_keypair  # noqa: E402

import adept_launcher.launcher as launcher  # noqa: E402

OS_NAME = {"win32": "windows", "darwin": "darwin"}.get(sys.platform, "linux")
EXE_NAME = {"windows": "Adept UI.exe", "darwin": "Adept UI.app", "linux": "Adept UI"}[OS_NAME]


@pytest.fixture()
def keys(monkeypatch):
    public, private = generate_keypair()
    monkeypatch.setattr("adept_lifecycle.trust.pinned_public_key", lambda: public)
    return public, private


def make_payload(path: Path, exe_name: str = EXE_NAME) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(exe_name, b"adept")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signed_catalog(private, version: str, digest: str, file_name: str = "AdeptUI.zip", kind: str = "zip") -> dict:
    body = {
        "approved": True,
        "channel": "beta",
        "artifacts": [
            {
                "platform": OS_NAME,
                "arch": "x64" if OS_NAME != "darwin" else "arm64",
                "version": version,
                "sha256": digest,
                "bytes": 100,
                "kind": kind,
                "fileName": file_name,
                "distributions": ["fedora", "debian"] if OS_NAME == "linux" else None,
            }
        ],
    }
    return sign_catalog_rsa(body, private)


def install_app(root: Path, version: str) -> Path:
    app_dir = root / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / EXE_NAME).write_bytes(b"installed")
    registry = {
        "installedVersion": version,
        "channel": "beta",
        "health": "ok",
        "updateFailures": {},
    }
    (root / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    return app_dir


def run_launcher(monkeypatch, tmp_path: Path, catalog: dict, payload_file: Path):
    """Run the orchestrator with a local catalog + download hook; capture app launches."""
    launched: list[str] = []

    # read_payload returns the local signed payload and drives byte progress; it is
    # the cleanest hook for a local catalog with no download URL.
    monkeypatch.setattr(
        launcher,
        "_build_hooks",
        lambda: launcher.Hooks(fetch_catalog=lambda: catalog, read_payload=lambda artifact: payload_file),
    )

    def fake_launch(self: Lifecycle, executable: Path) -> None:
        launched.append(str(executable))

    monkeypatch.setattr(launcher, "_launch_app", fake_launch)
    # Run the worker in-process (deterministic) rather than re-exec a frozen exe.
    monkeypatch.setattr(launcher, "_frozen_exe", lambda: None)

    rc = launcher.run(["--root", str(tmp_path)])
    return rc, launched


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_no_update_launches_without_reinstall(monkeypatch, tmp_path, keys):
    _, private = keys
    install_app(tmp_path, "1.1.3")
    catalog = signed_catalog(private, "1.1.3", digest="0" * 64)  # same version -> NO_UPDATE
    rc, launched = run_launcher(monkeypatch, tmp_path, catalog, tmp_path / "unused.zip")
    assert rc == 0
    assert len(launched) == 1
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "NO_UPDATE"
    # No update progress file, no payload staged.
    assert not (tmp_path / "staging").exists()


def test_update_applied_from_outside_payload(monkeypatch, tmp_path, keys):
    _, private = keys
    app_dir = install_app(tmp_path, "1.1.2")
    payload = tmp_path / "incoming" / "AdeptUI.zip"
    digest = make_payload(payload)
    catalog = signed_catalog(private, "1.1.3", digest)

    staged_outside: dict[str, str] = {}
    real_stage = launcher._stage_worker

    def spy_stage(layout: Layout):
        worker = real_stage(layout)
        staged_outside["app_dir"] = str(layout.app_dir.resolve())
        staged_outside["worker"] = str(worker) if worker else "in-process"
        return worker

    monkeypatch.setattr(launcher, "_stage_worker", spy_stage)
    rc, launched = run_launcher(monkeypatch, tmp_path, catalog, payload)
    assert rc == 0
    assert len(launched) == 1

    # Registry now records the new version.
    registry = read_json(tmp_path / "registry.json")
    assert registry["installedVersion"] == "1.1.3"
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "UPDATED"

    # The payload was replaced with the new build.
    assert (app_dir / EXE_NAME).read_bytes() == b"adept"
    # The staged worker (when frozen) must never live inside the payload.
    assert "app_dir" in staged_outside

    progress = read_json(tmp_path / "update-progress.json")
    assert progress["complete"] is True
    assert progress["overallPercent"] == 100
    assert progress["footer"] == "Updates complete."


def test_restart_after_update_does_not_reinstall(monkeypatch, tmp_path, keys):
    _, private = keys
    app_dir = install_app(tmp_path, "1.1.2")
    payload = tmp_path / "incoming" / "AdeptUI.zip"
    digest = make_payload(payload)
    catalog = signed_catalog(private, "1.1.3", digest)

    rc, _ = run_launcher(monkeypatch, tmp_path, catalog, payload)
    assert rc == 0
    first_bytes = (app_dir / EXE_NAME).read_bytes()

    # Second launch: catalog still offers 1.1.3 but installed is already 1.1.3.
    rc2, launched2 = run_launcher(monkeypatch, tmp_path, catalog, payload)
    assert rc2 == 0
    assert len(launched2) == 1
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "NO_UPDATE"
    assert (app_dir / EXE_NAME).read_bytes() == first_bytes


def test_checksum_mismatch_restores_installed_app(monkeypatch, tmp_path, keys):
    _, private = keys
    app_dir = install_app(tmp_path, "1.1.2")
    original = (app_dir / EXE_NAME).read_bytes()
    payload = tmp_path / "incoming" / "AdeptUI.zip"
    make_payload(payload)
    # Catalog digest does NOT match the payload -> CHECKSUM_MISMATCH.
    catalog = signed_catalog(private, "1.1.3", digest="f" * 64)

    rc, launched = run_launcher(monkeypatch, tmp_path, catalog, payload)
    assert rc == 0  # launcher continues to the installed app after a failed update
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "CHECKSUM_MISMATCH"
    # Installed app is untouched.
    assert (app_dir / EXE_NAME).read_bytes() == original
    # Failure was recorded toward the loop guard.
    registry = read_json(tmp_path / "registry.json")
    assert registry["updateFailures"].get("1.1.3") == 1


def test_update_loop_stopped_after_repeated_failures(monkeypatch, tmp_path, keys):
    _, private = keys
    install_app(tmp_path, "1.1.2")
    registry = read_json(tmp_path / "registry.json")
    registry["updateFailures"] = {"1.1.3": 3}
    (tmp_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")

    payload = tmp_path / "incoming" / "AdeptUI.zip"
    digest = make_payload(payload)
    catalog = signed_catalog(private, "1.1.3", digest)
    rc, launched = run_launcher(monkeypatch, tmp_path, catalog, payload)
    assert rc == 0
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "UPDATE_LOOP_STOPPED"
    assert len(launched) == 1


def test_offline_catalog_unavailable_launches_installed_app(monkeypatch, tmp_path, keys):
    """Offline / update service down: launcher must continue to the installed app."""
    _, private = keys
    install_app(tmp_path, "1.1.3")
    # fetch_catalog returns None -> UPDATE_SERVICE_UNAVAILABLE
    monkeypatch.setattr(launcher, "_build_hooks", lambda: launcher.Hooks(fetch_catalog=lambda: None))
    monkeypatch.setattr(launcher, "_launch_app", lambda self, exe: None)
    rc = launcher.run(["--root", str(tmp_path)])
    assert rc == 0
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "UPDATE_SERVICE_UNAVAILABLE"


def test_invalid_signature_refuses_update(monkeypatch, tmp_path):
    """A catalog that fails RSA verification must not update; app still launches."""
    install_app(tmp_path, "1.1.2")
    # Sign with a DIFFERENT key than the pinned one -> SIGNATURE_INVALID.
    other_public, other_private = generate_keypair()
    monkeypatch.setattr("adept_lifecycle.trust.pinned_public_key", lambda: other_public)
    # Build a catalog signed by yet another key so verification against other_public fails.
    wrong_public, wrong_private = generate_keypair()
    payload = tmp_path / "incoming" / "AdeptUI.zip"
    digest = make_payload(payload)
    catalog = signed_catalog(wrong_private, "1.1.3", digest)
    monkeypatch.setattr(launcher, "_build_hooks", lambda: launcher.Hooks(fetch_catalog=lambda: catalog))
    monkeypatch.setattr(launcher, "_launch_app", lambda self, exe: None)
    rc = launcher.run(["--root", str(tmp_path)])
    assert rc == 0
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "SIGNATURE_INVALID"
    # Installed app untouched.
    registry = read_json(tmp_path / "registry.json")
    assert registry["installedVersion"] == "1.1.2"


def test_update_lock_blocks_concurrent_update(monkeypatch, tmp_path, keys):
    """A held update.lock must refuse a second update and not launch."""
    _, private = keys
    install_app(tmp_path, "1.1.2")
    # Hold the lock with a fresh mtime.
    (tmp_path / "update.lock").write_text("999999", encoding="utf-8")
    payload = tmp_path / "incoming" / "AdeptUI.zip"
    digest = make_payload(payload)
    catalog = signed_catalog(private, "1.1.3", digest)
    monkeypatch.setattr(launcher, "_build_hooks", lambda: launcher.Hooks(fetch_catalog=lambda: catalog))
    launched = []
    monkeypatch.setattr(launcher, "_launch_app", lambda self, exe: launched.append(str(exe)))
    rc = launcher.run(["--root", str(tmp_path)])
    assert rc == 1  # update already running -> launcher reports failure, no launch
    assert len(launched) == 0


def test_production_active_defers_update(monkeypatch, tmp_path, keys):
    """An active production must defer the update and start the installed app."""
    _, private = keys
    app_dir = install_app(tmp_path, "1.1.2")
    original = (app_dir / EXE_NAME).read_bytes()
    # production-active marker defers any update.
    (tmp_path / "user-data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "user-data" / "production-active").write_text("1", encoding="utf-8")
    payload = tmp_path / "incoming" / "AdeptUI.zip"
    digest = make_payload(payload)
    catalog = signed_catalog(private, "1.1.3", digest)
    monkeypatch.setattr(launcher, "_build_hooks", lambda: launcher.Hooks(fetch_catalog=lambda: catalog))
    launched = []
    monkeypatch.setattr(launcher, "_launch_app", lambda self, exe: launched.append(str(exe)))
    rc = launcher.run(["--root", str(tmp_path)])
    assert rc == 0
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "DEFERRED"
    assert len(launched) == 1
    assert (app_dir / EXE_NAME).read_bytes() == original


def test_first_launch_records_packaged_version_before_catalog_check(monkeypatch, tmp_path, keys):
    _, private = keys
    app = tmp_path / "app"
    resources = app / ("Resources" if sys.platform == "darwin" else "resources")
    if sys.platform == "darwin":
        exe = app / "MacOS" / "Adept UI.bin"
    else:
        exe = app / EXE_NAME
    exe.parent.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b"installed")
    (resources / "version.json").write_text('{"version":"1.1.4"}', encoding="utf-8")
    monkeypatch.setenv("ADEPT_APP_EXECUTABLE", str(exe))
    catalog = signed_catalog(private, "1.1.4", digest="0" * 64)
    rc, launched = run_launcher(monkeypatch, tmp_path, catalog, tmp_path / "unused.zip")
    assert rc == 0
    assert len(launched) == 1
    registry = read_json(tmp_path / "registry.json")
    assert registry["installedVersion"] == "1.1.4"
    status = read_json(tmp_path / "startup-update.json")
    assert status["code"] == "NO_UPDATE"


def test_newer_release_uses_the_platform_installer(monkeypatch, tmp_path, keys):
    _, private = keys
    install_app(tmp_path, "1.1.5")
    keep = tmp_path / "user-data" / "project.txt"
    keep.parent.mkdir(parents=True)
    keep.write_text("keep", encoding="utf-8")
    payload = tmp_path / "incoming" / "Adept.UI-Setup.exe"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"installer-bytes")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    kind = {"windows": "nsis", "darwin": "dmg"}.get(OS_NAME, "deb")
    catalog = signed_catalog(private, "1.1.6", digest, file_name=payload.name, kind=kind)
    calls: list[tuple[str, str]] = []

    def fake_install(package: Path, package_kind: str, app_path: Path | None = None) -> None:
        calls.append((package_kind, package.name))
        assert package.read_bytes() == b"installer-bytes"

    monkeypatch.setattr("adept_lifecycle.manager.install_native_package", fake_install)
    rc, launched = run_launcher(monkeypatch, tmp_path, catalog, payload)
    assert rc == 0
    assert calls == [(kind, payload.name)]
    assert len(launched) == 1
    assert read_json(tmp_path / "registry.json")["installedVersion"] == "1.1.6"
    assert read_json(tmp_path / "startup-update.json")["code"] == "UPDATED"
    assert keep.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "app" / payload.name).exists()


def test_launcher_downloads_only_published_releases(tmp_path, monkeypatch):
    from adept_lifecycle.cli import _download_release

    with pytest.raises(OSError):
        _download_release("https://example.com/Adept.UI.exe", tmp_path / "bad.exe")

    class Response:
        def __enter__(self):
            self.done = False
            return self

        def __exit__(self, *args):
            return False

        def read(self, _size):
            if self.done:
                return b""
            self.done = True
            return b"installer"

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    dest = tmp_path / "Adept.UI.exe"
    _download_release(
        "https://github.com/bradjohnson79/adeptui/releases/download/v1.1.7/Adept.UI.exe",
        dest,
    )
    assert dest.read_bytes() == b"installer"
    assert launcher._build_hooks().download is _download_release


def test_launcher_forwards_local_electron_args(monkeypatch):
    monkeypatch.setenv("ADEPT_ELECTRON_ARGS", "--user-data-dir=C:\\adept-isolated")
    assert launcher.electron_command(Path("Adept UI.exe")) == [
        "Adept UI.exe",
        "--user-data-dir=C:\\adept-isolated",
    ]
    monkeypatch.delenv("ADEPT_ELECTRON_ARGS")
    assert launcher.electron_command(Path("Adept UI.exe")) == ["Adept UI.exe"]
