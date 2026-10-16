"""Installation lifecycle certification. These are simulations, not physical installs."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adept_lifecycle.cli import main
from adept_lifecycle.desktop import linux_desktop_entry, windows_launcher
from adept_lifecycle.detect import SystemProfile, linux_family_from_os_release
from adept_lifecycle.manager import Hooks, Layout, Lifecycle
from adept_lifecycle.release import ReleaseError, assert_release_url, canonical_bytes, sign_catalog, sign_catalog_rsa, verify_catalog_rsa
from adept_lifecycle.trust import generate_keypair, pinned_public_key, verify_sha256
from adept_lifecycle.safety import is_shared_dependency, resolve_contained

KEY = b"test-release-key"
ROOT = Path(__file__).resolve().parents[3]


def profile(os_name: str = "windows", arch: str = "x64", family: str | None = None, ram: int = 16 << 30) -> SystemProfile:
    return SystemProfile(os_name, "test", arch, family, ram, 50 << 30, "nvidia", 24 << 30)


def catalog(
    version: str = "1.2.0",
    platform: str = "windows",
    arch: str = "x64",
    *,
    approved: bool = True,
    digest: str,
    revision: int | None = None,
) -> dict:
    artifact = {
        "platform": platform,
        "arch": arch,
        "version": version,
        "sha256": digest,
        "bytes": 100,
        "kind": "zip",
        "fileName": "AdeptUI.zip",
        "distributions": ["fedora", "debian"] if platform == "linux" else None,
    }
    body = {
        "approved": approved,
        "channel": "beta",
        "artifacts": [artifact],
    }
    if revision is not None:
        artifact["revision"] = revision
        body["revision"] = revision
    return sign_catalog(body, KEY)


def make_zip(path: Path, name: str = "Adept UI.exe") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name, b"adept")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lifecycle(tmp: Path, system: SystemProfile, **hooks) -> Lifecycle:
    return Lifecycle(Layout(tmp), system, KEY, Hooks(**hooks))


def test_archive_update_does_not_need_a_source_tree(tmp_path: Path, monkeypatch):
    import adept_lifecycle.manager as manager

    monkeypatch.setattr(manager, "PACKAGE_ROOT", tmp_path / "missing-source")
    payload = tmp_path / "app.zip"
    make_zip(payload)
    app = lifecycle(tmp_path / "root", profile("windows", "x64"))
    result = app.apply_with_recovery(payload, {"version": "1.1.5", "kind": "zip"}, "1.1.4")
    assert result.ok
    assert (tmp_path / "root" / "app" / "Adept UI.exe").read_bytes() == b"adept"


def test_linux_families_and_unsupported_mac():
    assert linux_family_from_os_release("ID=fedora") == "fedora"
    assert linux_family_from_os_release("ID=ubuntu") == "debian"
    assert profile("darwin", "x64").supported is False
    assert "Apple Silicon" in profile("darwin", "x64").unsupported_reason
    assert profile("windows", "arm64").supported is False


def test_windows_linux_and_macos_install_alignment(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    for os_name, arch, family in (
        ("windows", "x64", None),
        ("linux", "x64", "fedora"),
        ("linux", "x64", "debian"),
        ("darwin", "arm64", None),
    ):
        home = tmp_path / os_name / (family or "default")
        result = lifecycle(home, profile(os_name, arch, family)).install(
            catalog("1.2.0", os_name, arch, digest=digest),
            payload,
            shortcut=True,
        )
        assert result.ok, result.message
        registry = json.loads((home / "registry.json").read_text(encoding="utf-8"))
        assert registry["installedVersion"] == "1.2.0"
        assert Path(registry["cli"]).is_file()
        assert Path(registry["desktopShortcut"]).is_file()
        second = lifecycle(home, profile(os_name, arch, family)).install(catalog("1.2.0", os_name, arch, digest=digest), payload)
        assert second.code == "ALREADY_INSTALLED"
        again = lifecycle(home, profile(os_name, arch, family))
        again._shortcut(Path(registry["cli"]))
        assert len(list((home / "desktop").glob("Adept UI*"))) == 1
    windows_home = tmp_path / "windows" / "default"
    launched: list[Path] = []
    started = lifecycle(windows_home, profile(), launch=lambda path: launched.append(path) or 0)
    assert started.launch().code == "LAUNCHED"
    assert launched[0].name == "Adept UI.exe"
    assert json.loads((windows_home / "startup-update.json").read_text(encoding="utf-8"))["code"] == "UPDATE_SERVICE_UNAVAILABLE"


def test_selection_refuses_other_platforms_and_bad_signatures(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    signed = catalog("1.2.0", "linux", "x64", digest=digest)
    result = lifecycle(home, profile("windows")).install(signed, payload)
    assert result.code == "NO_UPDATE"
    unsigned = dict(signed)
    unsigned["signature"] = "0" * 64
    refused = lifecycle(home, profile()).install(unsigned, payload)
    assert refused.code == "SIGNATURE_INVALID"
    unapproved = sign_catalog({**signed, "approved": False, "signature": None}, KEY)
    assert lifecycle(home, profile()).install(unapproved, payload).code == "NOT_APPROVED"


def test_update_defers_during_production_and_stops_a_loop(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile()
    installed = lifecycle(home, system).install(catalog("1.1.1", digest=digest), payload)
    assert installed.ok
    newer = tmp_path / "newer.zip"
    newer_digest = make_zip(newer, "Adept UI.exe")
    active = lifecycle(home, system, production_active=lambda: True)
    deferred = active.update(catalog("1.2.0", digest=newer_digest), newer, apply=True)
    assert deferred.code == "DEFERRED"
    assert (home / "user-data").is_dir()
    bad = tmp_path / "bad.zip"
    updater = lifecycle(home, system, production_active=lambda: False)
    for _ in range(3):
        bad.write_bytes(b"corrupted")
        failed = updater.update(catalog("1.2.0", digest=newer_digest), bad, apply=True)
        assert failed.code == "CHECKSUM_MISMATCH"
    stopped = updater.update(catalog("1.2.0", digest=newer_digest), newer, apply=True)
    assert stopped.code == "UPDATE_LOOP_STOPPED"


def test_update_replaces_version_and_keeps_user_work(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile()
    assert lifecycle(home, system).install(catalog("1.1.1", digest=digest), payload).ok
    (home / "user-data").mkdir(exist_ok=True)
    (home / "user-data" / "project.txt").write_text("keep", encoding="utf-8")
    newer = tmp_path / "newer.zip"
    newer_digest = make_zip(newer)
    result = lifecycle(home, system).update(catalog("1.2.0", digest=newer_digest), newer, apply=True)
    assert result.ok
    assert json.loads((home / "registry.json").read_text(encoding="utf-8"))["installedVersion"] == "1.2.0"
    assert (home / "user-data" / "project.txt").read_text(encoding="utf-8") == "keep"
    current = lifecycle(home, system).update(catalog("1.2.0", digest=newer_digest), newer, apply=False)
    assert current.code == "NO_UPDATE"


def test_same_version_revision_updates_and_rejects_a_downgrade(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile()
    installed = lifecycle(home, system).install(catalog("1.1.5", digest=digest), payload)
    assert installed.ok
    recorded = json.loads((home / "registry.json").read_text(encoding="utf-8"))
    assert recorded["installedVersion"] == "1.1.5"
    assert recorded["installedRevision"] == 0
    newer = tmp_path / "revision.zip"
    newer_digest = make_zip(newer, "Adept UI.exe")
    same = lifecycle(home, system).update(catalog("1.1.5", digest=newer_digest, revision=0), newer, apply=False)
    assert same.code == "NO_UPDATE"
    revised = lifecycle(home, system).update(catalog("1.1.5", digest=newer_digest, revision=1), newer, apply=True)
    assert revised.ok
    recorded = json.loads((home / "registry.json").read_text(encoding="utf-8"))
    assert recorded["installedVersion"] == "1.1.5"
    assert recorded["installedRevision"] == 1
    assert recorded["recovery"]["lastGoodVersion"] == "1.1.5"
    assert recorded["recovery"]["lastGoodRevision"] == 0
    assert (home / "app" / "Adept UI.exe").read_bytes() == b"adept"
    again = lifecycle(home, system).update(catalog("1.1.5", digest=newer_digest, revision=1), newer, apply=False)
    assert again.code == "NO_UPDATE"
    older = lifecycle(home, system).update(catalog("1.1.5", digest=newer_digest, revision=0), newer, apply=True)
    assert older.code == "NO_UPDATE"
    assert json.loads((home / "registry.json").read_text(encoding="utf-8"))["installedRevision"] == 1


def test_older_application_version_installs_the_newer_revision(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile()
    assert lifecycle(home, system).install(catalog("1.1.4", digest=digest), payload).ok
    newer = tmp_path / "next.zip"
    newer_digest = make_zip(newer)
    result = lifecycle(home, system).update(catalog("1.1.5", digest=newer_digest, revision=2), newer, apply=True)
    assert result.ok
    recorded = json.loads((home / "registry.json").read_text(encoding="utf-8"))
    assert recorded["installedVersion"] == "1.1.5"
    assert recorded["installedRevision"] == 2


def test_failed_revision_update_does_not_replace_the_installed_revision(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile()
    assert lifecycle(home, system).install(catalog("1.1.5", digest=digest, revision=1), payload).ok
    (home / "app" / "Adept UI.exe").write_bytes(b"original-install")
    original = (home / "app" / "Adept UI.exe").read_bytes()
    newer = tmp_path / "next.zip"
    newer_digest = make_zip(newer, "Adept UI.exe")
    refused = lifecycle(home, system).update(catalog("1.1.5", digest="ab" * 32, revision=2), newer, apply=True)
    assert refused.code == "CHECKSUM_MISMATCH"
    recorded = json.loads((home / "registry.json").read_text(encoding="utf-8"))
    assert recorded["installedVersion"] == "1.1.5"
    assert recorded["installedRevision"] == 1
    assert (home / "app" / "Adept UI.exe").read_bytes() == original
    interrupted = lifecycle(home, system, health=lambda: False).apply_with_recovery(
        newer,
        {"version": "1.1.5", "revision": 2, "kind": "zip", "fileName": newer.name, "sha256": newer_digest},
        "1.1.5",
    )
    assert interrupted.code == "UPDATE_RESTORED"
    recorded = json.loads((home / "registry.json").read_text(encoding="utf-8"))
    assert recorded["installedRevision"] == 1
    assert (home / "app" / "Adept UI.exe").read_bytes() == original
    assert (home / "previous-app").is_dir()


def test_uninstall_preserves_projects_and_refuses_unsafe_models(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile()
    app = lifecycle(home, system)
    assert app.install(catalog("1.2.0", digest=digest), payload).ok
    (home / "user-data").mkdir(exist_ok=True)
    (home / "user-data" / "project.txt").write_text("scene", encoding="utf-8")
    models = home / "models"
    managed = models / "local.bin"
    managed.write_bytes(b"12345")
    shared = models / "python" / "shared.bin"
    shared.parent.mkdir()
    shared.write_bytes(b"no")
    outside = Path("D:/01_Models/foreign.bin")
    link = models / "escape.bin"
    try:
        link.symlink_to(managed)
    except OSError:
        link = None
    inventory = {
        "models": [
            {"name": "Local", "path": str(managed), "managed": True, "owner": "adept-ui"},
            {"name": "Shared", "path": str(shared), "managed": True, "owner": "adept-ui"},
            {"name": "Foreign", "path": str(outside), "managed": True, "owner": "adept-ui"},
            {"name": "Unknown", "path": str(managed), "managed": False, "owner": "adept-ui"},
        ]
    }
    if link is not None:
        inventory["models"].append({"name": "Link", "path": str(link), "managed": True, "owner": "adept-ui"})
    (models / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    dry = app.uninstall(remove_app=True, remove_models=True, remove_settings=False, confirmed=False)
    assert dry.code == "NOT_CONFIRMED"
    assert managed.is_file()
    done = app.uninstall(remove_app=True, remove_models=True, remove_settings=False, confirmed=True)
    assert done.ok
    assert not managed.exists()
    assert shared.exists()
    assert (home / "user-data" / "project.txt").read_text(encoding="utf-8") == "scene"
    assert not (home / "registry.json").exists()
    assert is_shared_dependency(shared)
    assert resolve_contained(home / "user-data" / "project.txt", home / "app") is None


def test_failure_injection(tmp_path: Path):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile()
    denied = lifecycle(home, system, before_write=lambda: (_ for _ in ()).throw(PermissionError("denied")))
    assert denied.install(catalog("1.2.0", digest=digest), payload).code == "PERMISSION_DENIED"
    low = lifecycle(home, system, disk_free=lambda _path: 10)
    assert low.install(catalog("1.2.0", digest=digest), payload).code == "INSUFFICIENT_DISK"
    slipped = tmp_path / "slip.zip"
    with zipfile.ZipFile(slipped, "w") as archive:
        archive.writestr("../outside.txt", b"bad")
    slip_digest = hashlib.sha256(slipped.read_bytes()).hexdigest()
    escaped = lifecycle(home, system).install(catalog("1.2.0", digest=slip_digest), slipped)
    assert escaped.code == "INSTALL_INTERRUPTED"
    assert not (tmp_path / "outside.txt").exists()

    installed = lifecycle(home, system).install(catalog("1.1.1", digest=digest), payload)
    assert installed.ok
    newer = tmp_path / "newer.zip"
    newer_digest = make_zip(newer)
    offered = catalog("1.2.0", digest=newer_digest)
    offered["artifacts"][0]["url"] = "https://example.invalid/app.zip"
    offered = sign_catalog(offered, KEY)

    def boom(_url: str, _dest: Path) -> None:
        raise OSError("network down")

    interrupted = lifecycle(home, system, download=boom).update(offered, newer, apply=True)
    assert interrupted.code == "DOWNLOAD_INTERRUPTED"
    mismatched = tmp_path / "mismatched.zip"
    expected = make_zip(mismatched)
    mismatched.write_bytes(b"not-the-approved-bytes")
    rejected = lifecycle(tmp_path / "fresh-home", system).install(catalog("1.2.1", digest=expected), mismatched)
    assert rejected.code == "CHECKSUM_MISMATCH"
    assert not mismatched.exists()


def test_doctor_repair_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile("linux", "x64", "fedora")
    app = lifecycle(home, system)
    assert app.install(catalog("1.2.0", "linux", "x64", digest=digest), payload).ok
    assert "Name=Adept UI" in linux_desktop_entry(home / "bin" / "adeptui")
    assert app.doctor().code == "HEALTHY"
    cli = Path(json.loads((home / "registry.json").read_text(encoding="utf-8"))["cli"])
    cli.unlink()
    assert app.doctor().code == "NEEDS_REPAIR"
    assert app.repair(payload).ok
    assert cli.is_file()
    assert (home / "user-data").is_dir()
    code = main(["--root", str(home), "--version"], profile=system, key=KEY)
    assert code == 0
    assert "1.2.0" in capsys.readouterr().out
    code = main(["--root", str(home), "doctor"], profile=system, key=KEY)
    assert code == 0


def test_bootstrap_uses_the_pinned_catalog():
    script = ROOT / "install" / "bootstrap" / "install.ps1"
    text = script.read_text(encoding="utf-8")
    assert "not open yet" not in text
    assert "https://adeptui.org/releases/current.json" in text
    assert "https://adeptui.org/releases/current.sig" in text
    assert "releases/download/v" in text
    assert "127.0.0.1" not in text
    assert "localhost" not in text.lower()
    shell = (ROOT / "install" / "bootstrap" / "install.sh").read_text(encoding="utf-8")
    assert "certification pending" not in shell.lower()
    assert "not notarized" in shell.lower()
    assert 'kind="zip"' in shell
    assert "hdiutil" not in shell
    assert "dpkg" not in shell
    assert "rpm -Uvh" not in shell
    assert "Apple Silicon" in shell
    assert "xattr" not in shell
    assert "spctl --master-disable" not in shell
    assert "csrutil" not in shell
    assert "https://adeptui.org/releases/current.json" in shell
    assert "BEGIN PUBLIC KEY" in shell
    assert "127.0.0.1" not in shell
    assert "localhost" not in shell.lower()
    zip_at = shell.index('if [ "$payload_kind" = "zip" ]')
    assert "exit 0" in shell[zip_at:]
    assert "application archive" in shell[zip_at:]
    assert "installedRevision" in shell
    launcher = (ROOT / "install" / "launcher" / "adept_launcher" / "launcher.py").read_text(encoding="utf-8")
    assert "install_native_package" not in launcher
    assert 'kind != "zip"' in launcher


def test_pinned_catalog_signature_matches_the_published_release():
    catalog = (ROOT / "install" / "catalog" / "current.json").read_bytes()
    signature = (ROOT / "install" / "catalog" / "current.sig").read_text(encoding="utf-8").strip()
    key = pinned_public_key()
    assert key is not None
    # The detached signature covers the exact published file bytes — the same
    # contract the public installers enforce (install.sh openssl dgst over the
    # raw file, install.ps1 .NET VerifyData over the downloaded bytes).
    assert verify_sha256(catalog, "rsa-sha256:" + signature, key)
    flipped = bytearray(catalog)
    flipped[20] ^= 1
    assert not verify_sha256(bytes(flipped), "rsa-sha256:" + signature, key)
    body = json.loads(catalog.decode("utf-8"))
    # P0 regression gate (2026-10-15 macOS installer "rsa_verify:bad signature"):
    # the published bytes MUST be the canonical form so the installers'
    # raw-bytes verification and the launcher's canonical verification compute
    # the identical signed message. A pretty-printed catalog with a
    # canonical-form signature fails every public installer.
    assert catalog == canonical_bytes(body)
    assert "signature" not in body
    # The website must serve byte-identical catalog and signature files.
    www_catalog = (ROOT / "www" / "public" / "releases" / "current.json").read_bytes()
    www_signature = (ROOT / "www" / "public" / "releases" / "current.sig").read_text(encoding="utf-8").strip()
    assert www_catalog == catalog
    assert www_signature == signature
    version = body["version"]
    names = {item["fileName"] for item in body["artifacts"]}
    assert names == {
        f"Adept.UI-{version}-terminal-r2-win-x64.zip",
        f"Adept.UI-{version}-terminal-r2-linux-x64.zip",
        f"Adept.UI-{version}-terminal-r2-mac-arm64.zip",
    }
    mac = next(item for item in body["artifacts"] if item["platform"] == "darwin")
    assert mac["arch"] == "arm64"
    assert mac["kind"] == "zip"
    linux = next(item for item in body["artifacts"] if item["platform"] == "linux")
    assert "distributions" not in linux
    assert all(item["url"].startswith(f"https://github.com/bradjohnson79/adeptui/releases/download/v{version}/") for item in body["artifacts"])
    assert not any("appimage" in item["fileName"].lower() for item in body["artifacts"])


def test_rsa_catalog_rejects_branch_urls_and_update_restores_the_previous_app(tmp_path: Path):
    public, private = generate_keypair()
    payload = tmp_path / "app.zip"
    digest = make_zip(payload)
    signed = sign_catalog_rsa(
        {
            "approved": True,
            "channel": "beta",
            "artifacts": [
                {
                    "platform": "windows",
                    "arch": "x64",
                    "version": "1.2.0",
                    "sha256": digest,
                    "bytes": payload.stat().st_size,
                    "kind": "zip",
                    "fileName": "AdeptUI.zip",
                    "url": "https://github.com/bradjohnson79/adeptui/releases/download/v1.2.0/AdeptUI.zip",
                }
            ],
        },
        private,
    )
    verify_catalog_rsa(signed, public)
    tampered = dict(signed)
    tampered["signature"] = "rsa-sha256:" + "AA=="
    with pytest.raises(ReleaseError):
        verify_catalog_rsa(tampered, public)
    with pytest.raises(ReleaseError):
        assert_release_url("https://github.com/bradjohnson79/adeptui/archive/refs/heads/main.zip")
    home = tmp_path / "home"
    system = profile()
    installed = lifecycle(home, system).install_discovered(signed, payload, public, shortcut=True)
    assert installed.ok
    newer = tmp_path / "newer.zip"
    with zipfile.ZipFile(newer, "w") as archive:
        archive.writestr("Adept UI.exe", b"replaced")
    restored = lifecycle(home, system, health=lambda: False).apply_with_recovery(
        newer,
        {"version": "1.3.0", "kind": "zip"},
        "1.2.0",
    )
    assert restored.code == "UPDATE_RESTORED"
    assert (home / "app" / "Adept UI.exe").read_bytes() == b"adept"
    updater = Path(restored.details["updater"])
    assert (home / "app").resolve() not in updater.resolve().parents


def test_windows_shortcut_starts_the_lifecycle_without_a_console():
    script = windows_launcher(Path(r"C:\Adept\bin\adeptui.cmd"))
    assert "Wscript.Shell" in script
    assert ", 0, False" in script
    assert "Adept UI.exe" not in script


def test_terminal_install_does_not_keep_a_package_installer():
    shell = (ROOT / "install" / "bootstrap" / "install.sh").read_text(encoding="utf-8")
    windows = (ROOT / "install" / "bootstrap" / "install.ps1").read_text(encoding="utf-8")
    manager = (ROOT / "install" / "lifecycle" / "adept_lifecycle" / "manager.py").read_text(encoding="utf-8")
    assert "install_native_package" not in manager
    assert "nsis" not in windows.lower()
    assert "hdiutil" not in shell
    assert "dpkg" not in shell


def _installed(tmp_path: Path, version: str = "1.1.2"):
    payload = tmp_path / "installed.zip"
    digest = make_zip(payload)
    home = tmp_path / "home"
    system = profile()
    assert lifecycle(home, system).install(catalog(version, digest=digest), payload).ok
    (home / "user-data").mkdir(exist_ok=True)
    (home / "user-data" / "project.txt").write_text("keep", encoding="utf-8")
    return home, system


def test_boot_without_a_catalog_does_not_show_completion(tmp_path: Path):
    home, system = _installed(tmp_path)
    launched: list[Path] = []
    result = lifecycle(home, system, launch=lambda path: launched.append(path) or 0).launch()
    assert result.code == "LAUNCHED"
    assert result.details["code"] == "UPDATE_SERVICE_UNAVAILABLE"
    progress = home / "update-progress.json"
    assert not progress.exists() or json.loads(progress.read_text(encoding="utf-8")).get("footer") != "Updates complete."
    assert (home / "user-data" / "project.txt").read_text(encoding="utf-8") == "keep"


def test_boot_installs_a_newer_release_and_reports_real_bytes(tmp_path: Path):
    home, system = _installed(tmp_path)
    newer = tmp_path / "newer.zip"
    digest = make_zip(newer)
    offered = catalog("1.1.3", digest=digest)
    offered["artifacts"][0]["bytes"] = newer.stat().st_size
    offered = sign_catalog(offered, KEY)
    launched: list[Path] = []
    seen: list[dict] = []

    def hold() -> None:
        return None

    result = lifecycle(
        home,
        system,
        fetch_catalog=lambda: offered,
        read_payload=lambda _artifact: newer,
        launch=lambda path: launched.append(path) or 0,
        progress=seen.append,
        hold_completion=hold,
        show_updater=True,
    ).launch()
    assert result.code == "UPDATED"
    assert result.details["footer"] == "Updates complete."
    assert launched and launched[0].name == "Adept UI.exe"
    download = [item for item in seen if item["phase"] == "download" and item["downloadBytes"]]
    assert download
    assert download[-1]["downloadBytes"] == newer.stat().st_size
    assert all(item["overallPercent"] != 100 for item in seen if not item["complete"])
    assert seen[-1]["complete"] is True
    assert seen[-1]["overallPercent"] == 100
    assert seen[-1]["footer"] == "Updates complete."
    assert (home / "user-data" / "project.txt").read_text(encoding="utf-8") == "keep"


def test_boot_rejects_a_bad_signature_and_keeps_the_installed_app(tmp_path: Path):
    home, system = _installed(tmp_path)
    bad = catalog("1.1.3", digest="a" * 64)
    bad["signature"] = "0" * 64
    launched: list[Path] = []
    result = lifecycle(home, system, fetch_catalog=lambda: bad, launch=lambda path: launched.append(path) or 0).launch()
    assert result.code == "LAUNCHED"
    assert result.details["code"] == "SIGNATURE_INVALID"
    progress = json.loads((home / "update-progress.json").read_text(encoding="utf-8"))
    assert progress["footer"] != "Updates complete."
    assert progress["complete"] is False
    assert json.loads((home / "registry.json").read_text(encoding="utf-8"))["installedVersion"] == "1.1.2"


def test_boot_stops_after_repeated_checksum_failures(tmp_path: Path):
    home, system = _installed(tmp_path)
    newer = tmp_path / "newer.zip"
    digest = make_zip(newer)
    offered = catalog("1.1.3", digest=digest)
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not-the-archive")
    updater = lifecycle(home, system, fetch_catalog=lambda: offered, read_payload=lambda _artifact: bad, launch=lambda _path: 0)
    for _ in range(3):
        failed = updater.launch()
        assert failed.details["code"] == "CHECKSUM_MISMATCH"
    stopped = updater.launch()
    assert stopped.details["code"] == "UPDATE_LOOP_STOPPED"
    assert json.loads((home / "update-progress.json").read_text(encoding="utf-8"))["footer"] != "Updates complete."
