"""Install, update, repair, and uninstall. One registry, no second installer."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import zipfile
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .desktop import menu_entry, write_launcher
from .detect import SystemProfile
from .registry import atomic_write, empty_registry, read_registry
from .release import ReleaseError, select_artifact, verify_catalog, verify_catalog_rsa, verify_file
from .trust import PublicKey
from .safety import is_shared_dependency, resolve_contained, windows_model_on_system_drive

PACKAGE_ROOT = Path(__file__).resolve().parent
FAILURE_LIMIT = 3


def package_install_plan(kind: str, payload: Path) -> list[str] | None:
    """Command that replaces an installed package. It does not clear Gatekeeper or quarantine."""
    if kind == "nsis":
        return [str(payload), "/S"]
    if kind == "deb":
        return ["dpkg", "-i", str(payload)]
    if kind == "rpm":
        return ["rpm", "-Uvh", str(payload)]
    if kind == "dmg":
        return ["hdiutil", "attach", "-nobrowse", "-readonly", str(payload)]
    return None


@dataclass
class Hooks:
    disk_free: Callable[[Path], int] | None = None
    production_active: Callable[[], bool] | None = None
    download: Callable[[str, Path], None] | None = None
    read_payload: Callable[[dict[str, Any]], Path] | None = None
    fetch_catalog: Callable[[], dict[str, Any] | None] | None = None
    install_package: Callable[[Path, dict[str, Any]], None] | None = None
    launch: Callable[[Path], int] | None = None
    before_write: Callable[[], None] | None = None
    health: Callable[[], bool] | None = None
    progress: Callable[[dict[str, Any]], None] | None = None
    show_updater: bool = False
    hold_completion: Callable[[], None] | None = None
    chunk_pause: float = 0.0


@dataclass
class Layout:
    root: Path
    system_drive: str = "C:"

    @property
    def registry_path(self) -> Path:
        return self.root / "registry.json"

    @property
    def app_dir(self) -> Path:
        return self.root / "app"

    @property
    def bin_dir(self) -> Path:
        return self.root / "bin"

    @property
    def model_dir(self) -> Path:
        return self.root / "models"

    @property
    def staging_dir(self) -> Path:
        return self.root / "staging"

    @property
    def user_data(self) -> Path:
        return self.root / "user-data"

    @property
    def desktop_dir(self) -> Path:
        return self.root / "desktop"

    @property
    def applications_dir(self) -> Path:
        return self.root / "applications"

    @property
    def log_path(self) -> Path:
        return self.root / "logs" / "lifecycle.log"


@dataclass
class Result:
    ok: bool
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class Lifecycle:
    def __init__(self, layout: Layout, profile: SystemProfile, key: bytes | None, hooks: Hooks | None = None):
        self.layout = layout
        self.profile = profile
        self.key = key
        self.hooks = hooks or Hooks()

    def log(self, message: str) -> None:
        self.layout.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.layout.log_path.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")

    def _registry(self) -> dict[str, Any]:
        current = read_registry(self.layout.registry_path)
        if current is None:
            return empty_registry(self.profile.os_name, self.profile.arch, str(self.layout.app_dir))
        return current

    def _save(self, registry: dict[str, Any]) -> None:
        atomic_write(self.layout.registry_path, registry)

    def _disk_free(self) -> int:
        if self.hooks.disk_free:
            return int(self.hooks.disk_free(self.layout.root))
        return self.profile.disk_free_bytes

    def _production_active(self) -> bool:
        if self.hooks.production_active:
            return bool(self.hooks.production_active())
        marker = self.layout.user_data / "production-active"
        return marker.is_file()

    def install(
        self,
        catalog: dict[str, Any],
        payload: Path,
        *,
        shortcut: bool = True,
        launch: bool = False,
        force: bool = False,
        already_verified: bool = False,
    ) -> Result:
        if not self.profile.supported or (
            self.profile.os_name == "linux" and self.profile.linux_family not in {"fedora", "debian"}
        ):
            return Result(False, "UNSUPPORTED", self.profile.unsupported_reason or "This computer is not a supported Adept UI install target.")
        registry = self._registry()
        if registry.get("installedVersion") and not force:
            return Result(
                False,
                "ALREADY_INSTALLED",
                f"Adept UI {registry['installedVersion']} is already installed. Use update to replace it.",
                {"version": registry.get("installedVersion")},
            )
        try:
            if not already_verified:
                verify_catalog(catalog, self.key)
            artifact = select_artifact(catalog, self.profile, None)
        except ReleaseError as exc:
            self.log(exc.code)
            return Result(False, exc.code, exc.message)
        needed = int(artifact.get("bytes") or payload.stat().st_size) + (200 * 1024 * 1024)
        if self._disk_free() < needed:
            return Result(False, "INSUFFICIENT_DISK", "There is not enough free storage to install Adept UI.")
        try:
            verify_file(payload, str(artifact["sha256"]))
        except ReleaseError as exc:
            if payload.exists():
                payload.unlink()
            return Result(False, exc.code, exc.message)
        try:
            if self.hooks.before_write:
                self.hooks.before_write()
            extracted = self._materialize(payload, artifact)
        except PermissionError:
            return Result(False, "PERMISSION_DENIED", "Adept UI could not write the installation folder.")
        except OSError as exc:
            return Result(False, "INSTALL_INTERRUPTED", f"Installation stopped before it finished. {exc}")
        managed = extracted + self._copy_manager()
        cli = self._write_cli()
        shortcut_path = None
        if shortcut:
            shortcut_path = self._shortcut(cli)
        menu = None
        if self.profile.os_name == "linux":
            menu = str(menu_entry(self.layout.applications_dir, cli))
        version = str(artifact["version"])
        registry.update(
            {
                "installedVersion": version,
                "channel": catalog.get("channel") or "beta",
                "location": str(self.layout.app_dir),
                "managedFiles": managed,
                "managedRuntime": [str(self.layout.app_dir)],
                "desktopShortcut": shortcut_path,
                "cli": str(cli),
                "modelInventory": str(self.layout.model_dir / "inventory.json"),
                "userData": str(self.layout.user_data),
                "health": "installed",
                "recovery": {"lastGoodVersion": version},
            }
        )
        history = list(registry.get("updateHistory") or [])
        history.append({"version": version, "action": "install"})
        registry["updateHistory"] = history
        self._save(registry)
        self.layout.user_data.mkdir(parents=True, exist_ok=True)
        self._write_model_inventory([])
        launched = False
        if launch and self.hooks.launch:
            self.hooks.launch(cli)
            launched = True
        self.log(f"installed {version}")
        return Result(True, "INSTALLED", f"Adept UI {version} is installed.", {"launched": launched, "menu": menu})

    def launch(self) -> Result:
        """Check the signed catalog, install a newer release, then start the application.

        The lifecycle process stays outside the application directory. The
        application is started only after that check finishes.
        """
        registry = read_registry(self.layout.registry_path)
        remembered = os.environ.get("ADEPT_INSTALLED_VERSION")
        if (not registry or not registry.get("installedVersion")) and remembered:
            registry = empty_registry(self.profile.os_name, self.profile.arch, str(self.layout.app_dir))
            registry["installedVersion"] = remembered
            self._save(registry)
        if not registry or not registry.get("installedVersion"):
            executable = self._executable()
            if executable is not None and os.environ.get("ADEPT_APP_EXECUTABLE"):
                self._start_app(executable)
                return Result(True, "LAUNCHED", "Adept UI is starting.", {"action": "continue", "code": "NOT_TRACKED"})
            return Result(False, "NOT_INSTALLED", "Install Adept UI before launching it.")
        executable = self._executable()
        if executable is None:
            return Result(False, "EXECUTABLE_MISSING", "The installed Adept UI application was not found.")
        if self._production_active():
            return self._continue(executable, "DEFERRED", str(registry.get("installedVersion")), "Adept UI is starting.")
        if not self._acquire_update_lock():
            return Result(False, "UPDATE_IN_PROGRESS", "An update is already running.")
        try:
            catalog = None
            if self.hooks.fetch_catalog is not None:
                try:
                    catalog = self.hooks.fetch_catalog()
                except OSError:
                    catalog = None
            if not catalog:
                return self._continue(
                    executable,
                    "UPDATE_SERVICE_UNAVAILABLE",
                    str(registry.get("installedVersion")),
                    "Adept UI is starting.",
                )
            return self._boot_update(catalog, executable, registry)
        finally:
            self._release_update_lock()

    def _continue(self, executable: Path, code: str, version: str, message: str) -> Result:
        status = {"action": "continue", "code": code, "version": version}
        atomic_write(self.layout.root / "startup-update.json", status)
        self._start_app(executable)
        self.log(f"launch {code}")
        return Result(True, "LAUNCHED", message, status)

    def _start_app(self, executable: Path) -> None:
        if self.hooks.launch:
            self.hooks.launch(executable)
            return
        env = os.environ.copy()
        env["ADEPT_LAUNCHED_BY_UPDATER"] = "1"
        subprocess.Popen([str(executable)], close_fds=True, env=env)

    def _acquire_update_lock(self) -> bool:
        lock = self.layout.root / "update.lock"
        if lock.is_file():
            age = time.time() - lock.stat().st_mtime
            if age < 3600:
                return False
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()), encoding="utf-8")
        return True

    def _release_update_lock(self) -> None:
        lock = self.layout.root / "update.lock"
        if lock.is_file():
            lock.unlink()

    def _emit(self, **fields: Any) -> None:
        payload = {
            "phase": fields.get("phase") or "",
            "installedVersion": fields.get("installedVersion") or "",
            "targetVersion": fields.get("targetVersion") or "",
            "operation": fields.get("operation") or "",
            "downloadBytes": int(fields.get("downloadBytes") or 0),
            "downloadTotal": int(fields.get("downloadTotal") or 0),
            "downloadPercent": fields.get("downloadPercent"),
            "bytesPerSecond": fields.get("bytesPerSecond") or 0,
            "overallPercent": fields.get("overallPercent"),
            "indeterminate": bool(fields.get("indeterminate")),
            "complete": bool(fields.get("complete")),
            "footer": fields.get("footer") or "",
            "error": fields.get("error") or "",
        }
        atomic_write(self.layout.root / "update-progress.json", payload)
        if self.hooks.progress:
            self.hooks.progress(payload)

    def _serve_updater(self) -> str:
        if getattr(self, "_updater_server", None) is not None:
            port = self._updater_server.server_address[1]
            return f"http://127.0.0.1:{port}/"
        page_path = PACKAGE_ROOT / "updater_page.html"
        page = page_path.read_text(encoding="utf-8") if page_path.is_file() else "<p>Update Manager</p>"
        progress_path = self.layout.root / "update-progress.json"
        emblem = PACKAGE_ROOT.parents[2] / "studio-web" / "public" / "brand" / "adept-ui-emblem.webp"

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                if self.path.startswith("/progress"):
                    body = progress_path.read_bytes() if progress_path.is_file() else b"{}"
                    self._send(body, "application/json")
                    return
                if self.path.startswith("/brand/") and emblem.is_file():
                    self._send(emblem.read_bytes(), "image/webp")
                    return
                self._send(page.encode("utf-8"), "text/html; charset=utf-8")

            def _send(self, body: bytes, content_type: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self._updater_server = server
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        if os.environ.get("ADEPT_OPEN_UPDATER") == "1":
            import webbrowser

            webbrowser.open(url)
        return url

    def _boot_update(self, catalog: dict[str, Any], executable: Path, registry: dict[str, Any]) -> Result:
        version = str(registry.get("installedVersion"))
        self._emit(
            phase="catalog",
            installedVersion=version,
            operation="Checking the signed release catalog",
            indeterminate=True,
        )
        try:
            if self.key:
                verify_catalog(catalog, self.key)
            else:
                from .trust import pinned_public_key

                public = pinned_public_key()
                if public is None:
                    raise ReleaseError("SIGNATURE_MISSING", "The release catalog has no verifiable signature.")
                verify_catalog_rsa(catalog, public)
            artifact = select_artifact(catalog, self.profile, version)
        except ReleaseError as exc:
            if exc.code == "NO_UPDATE":
                return self._continue(executable, "NO_UPDATE", version, "Adept UI is up to date.")
            self._emit(phase="error", installedVersion=version, operation=exc.message, error=exc.code, indeterminate=True)
            return self._continue(executable, exc.code, version, exc.message)
        target = str(artifact["version"])
        failures = dict(registry.get("updateFailures") or {})
        if int(failures.get(target) or 0) >= FAILURE_LIMIT:
            self._emit(
                phase="error",
                installedVersion=version,
                targetVersion=target,
                operation="This update failed repeatedly and will not be tried again automatically.",
                error="UPDATE_LOOP_STOPPED",
                indeterminate=True,
            )
            return self._continue(executable, "UPDATE_LOOP_STOPPED", version, "Adept UI is starting with the installed version.")
        if self.hooks.show_updater:
            updater_url = self._serve_updater()
            marker = os.environ.get("ADEPT_UPDATER_URL_FILE")
            if marker:
                Path(marker).write_text(updater_url, encoding="utf-8")
        self._emit(
            phase="download",
            installedVersion=version,
            targetVersion=target,
            operation="Downloading update",
            downloadPercent=0,
            indeterminate=False,
        )
        payload = self.layout.staging_dir / str(artifact.get("fileName") or "update.bin")
        try:
            self._obtain_payload(artifact, payload, version, target)
            self._emit(
                phase="checksum",
                installedVersion=version,
                targetVersion=target,
                operation="Checking the download",
                indeterminate=True,
            )
            verify_file(payload, str(artifact["sha256"]))
        except ReleaseError as exc:
            self._record_update_failure(registry, failures, target)
            if payload.exists() and exc.code == "CHECKSUM_MISMATCH":
                payload.unlink()
            self._emit(phase="error", installedVersion=version, targetVersion=target, operation=exc.message, error=exc.code, indeterminate=True)
            return self._continue(executable, exc.code, version, exc.message)
        except OSError as exc:
            self._record_update_failure(registry, failures, target)
            self._emit(
                phase="error",
                installedVersion=version,
                targetVersion=target,
                operation="The update download did not finish.",
                error="DOWNLOAD_INTERRUPTED",
                indeterminate=True,
            )
            return self._continue(executable, "DOWNLOAD_INTERRUPTED", version, f"The update download did not finish. {exc}")
        needed = int(artifact.get("bytes") or payload.stat().st_size) + (200 * 1024 * 1024)
        if self._disk_free() < needed:
            self._emit(
                phase="error",
                installedVersion=version,
                targetVersion=target,
                operation="There is not enough free storage to install the update.",
                error="INSUFFICIENT_DISK",
                indeterminate=True,
            )
            return self._continue(executable, "INSUFFICIENT_DISK", version, "There is not enough free storage to install the update.")
        self._emit(
            phase="install",
            installedVersion=version,
            targetVersion=target,
            operation="Installing the update",
            indeterminate=True,
        )
        self.external_updater_dir()
        kind = str(artifact.get("kind") or "zip")
        if kind == "zip":
            result = self.apply_with_recovery(payload, artifact, version)
        elif self.hooks.install_package:
            try:
                self.hooks.install_package(payload, artifact)
            except OSError as exc:
                self._record_update_failure(registry, failures, target)
                self._emit(phase="error", installedVersion=version, targetVersion=target, operation=str(exc), error="INSTALL_INTERRUPTED", indeterminate=True)
                return self._continue(executable, "INSTALL_INTERRUPTED", version, "The update did not finish. The installed Adept UI was left in place.")
            registry = self._registry()
            registry["installedVersion"] = target
            registry["health"] = "updated"
            registry["recovery"] = {"lastGoodVersion": version}
            self._save(registry)
            result = Result(True, "UPDATED", f"Adept UI is now {target}.", {"previous": version})
        else:
            self._emit(
                phase="error",
                installedVersion=version,
                targetVersion=target,
                operation="This package cannot be replaced while Adept UI is open.",
                error="UNSUPPORTED_PACKAGE",
                indeterminate=True,
            )
            return self._continue(executable, "UNSUPPORTED_PACKAGE", version, "Adept UI is starting with the installed version.")
        if not result.ok:
            self._record_update_failure(registry, failures, target)
            self._emit(phase="error", installedVersion=version, targetVersion=target, operation=result.message, error=result.code, indeterminate=True)
            restored = self._executable() or executable
            return self._continue(restored, result.code, version, result.message)
        self._emit(
            phase="complete",
            installedVersion=target,
            targetVersion=target,
            operation=f"Adept UI {target} installed successfully.",
            overallPercent=100,
            downloadPercent=100,
            indeterminate=False,
            complete=True,
            footer="Updates complete.",
        )
        status = {"action": "updated", "code": "UPDATED", "version": target, "footer": "Updates complete."}
        atomic_write(self.layout.root / "startup-update.json", status)
        if self.hooks.hold_completion:
            self.hooks.hold_completion()
        else:
            time.sleep(1.25)
        self._start_app(self._executable() or executable)
        self.log(f"launch UPDATED {version} -> {target}")
        return Result(True, "UPDATED", f"Adept UI is now {target}.", status)

    def _record_update_failure(self, registry: dict[str, Any], failures: dict[str, Any], target: str) -> None:
        failures[target] = int(failures.get(target) or 0) + 1
        registry["updateFailures"] = failures
        self._save(registry)

    def _obtain_payload(self, artifact: dict[str, Any], dest: Path, installed: str, target: str) -> None:
        if self.hooks.read_payload:
            source = self.hooks.read_payload(artifact)
            total = int(artifact.get("bytes") or source.stat().st_size)
            self._copy_progress(source, dest, total, installed, target)
            return
        if self.hooks.download and artifact.get("url"):
            self.layout.staging_dir.mkdir(parents=True, exist_ok=True)
            self.hooks.download(str(artifact["url"]), dest)
            return
        raise OSError("The update file was not provided.")

    def _copy_progress(self, source: Path, dest: Path, total: int, installed: str, target: str) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        sent = 0
        started = time.monotonic()
        safe_total = total if total > 0 else 1
        with source.open("rb") as incoming, dest.open("wb") as outgoing:
            while True:
                chunk = incoming.read(64 * 1024)
                if not chunk:
                    break
                outgoing.write(chunk)
                sent += len(chunk)
                elapsed = max(time.monotonic() - started, 0.001)
                percent = min(99, int(sent * 100 / safe_total))
                self._emit(
                    phase="download",
                    installedVersion=installed,
                    targetVersion=target,
                    operation="Downloading update",
                    downloadBytes=sent,
                    downloadTotal=safe_total if total > 0 else sent,
                    downloadPercent=percent if total > 0 else None,
                    bytesPerSecond=int(sent / elapsed),
                    indeterminate=total <= 0,
                )
                if self.hooks.chunk_pause:
                    time.sleep(self.hooks.chunk_pause)

    def install_discovered(
        self,
        catalog: dict[str, Any],
        payload: Path,
        public_key: PublicKey,
        *,
        shortcut: bool = True,
    ) -> Result:
        try:
            verify_catalog_rsa(catalog, public_key)
        except ReleaseError as exc:
            return Result(False, exc.code, exc.message)
        return self.install(catalog, payload, shortcut=shortcut, already_verified=True)

    def apply_with_recovery(self, payload: Path, artifact: dict[str, Any], previous_version: str) -> Result:
        """Replace the application from a staged file, restoring the previous copy on failure."""
        if self._production_active():
            return Result(False, "DEFERRED", "An update is waiting. It will install the next time Adept UI starts and nothing is rendering.")
        previous = self.layout.root / "previous-app"
        if previous.exists():
            shutil.rmtree(previous)
        if self.layout.app_dir.exists():
            shutil.copytree(self.layout.app_dir, previous)
        updater = self.external_updater_dir()
        try:
            self._materialize(payload, artifact)
            if self.hooks.health and not self.hooks.health():
                raise OSError("The updated application did not pass its health check.")
        except OSError as exc:
            self._restore_previous(previous)
            self.log(f"update restored after {exc}")
            return Result(False, "UPDATE_RESTORED", "The update did not finish. Adept UI was restored to the last working version.", {"updater": str(updater)})
        registry = self._registry()
        registry["installedVersion"] = str(artifact.get("version") or registry.get("installedVersion"))
        registry["recovery"] = {"lastGoodVersion": previous_version}
        registry["health"] = "updated"
        self._save(registry)
        return Result(True, "UPDATED", f"Adept UI is now {registry['installedVersion']}.", {"updater": str(updater), "previous": previous_version})

    def external_updater_dir(self) -> Path:
        """Copy the lifecycle manager outside the application directory before replacement."""
        destination = self.layout.root / "updater" / "adept_lifecycle"
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PACKAGE_ROOT, destination)
        if self.layout.app_dir.resolve() in destination.resolve().parents:
            raise OSError("The updater must not live inside the application it replaces.")
        return destination.parent

    def _restore_previous(self, previous: Path) -> None:
        if not previous.is_dir():
            return
        if self.layout.app_dir.exists():
            shutil.rmtree(self.layout.app_dir)
        shutil.copytree(previous, self.layout.app_dir)

    def update(self, catalog: dict[str, Any], payload: Path | None, *, apply: bool) -> Result:
        if self._production_active():
            return Result(False, "DEFERRED", "An update is waiting. It will install the next time Adept UI starts and nothing is rendering.")
        registry = self._registry()
        version = registry.get("installedVersion")
        if not version:
            return Result(False, "NOT_INSTALLED", "Install Adept UI before checking for updates.")
        failures = dict(registry.get("updateFailures") or {})
        try:
            verify_catalog(catalog, self.key)
            artifact = select_artifact(catalog, self.profile, str(version))
        except ReleaseError as exc:
            if exc.code == "NO_UPDATE":
                return Result(True, "NO_UPDATE", "Adept UI is up to date.")
            return Result(False, exc.code, exc.message)
        target = str(artifact["version"])
        if int(failures.get(target) or 0) >= FAILURE_LIMIT:
            return Result(False, "UPDATE_LOOP_STOPPED", "This update failed repeatedly and will not be tried again automatically.")
        if not apply:
            return Result(True, "UPDATE_AVAILABLE", f"Adept UI {target} is available.", {"version": target})
        if payload is None:
            return Result(False, "PAYLOAD_MISSING", "The update file was not provided.")
        try:
            if self.hooks.download and artifact.get("url"):
                self.layout.staging_dir.mkdir(parents=True, exist_ok=True)
                self.hooks.download(str(artifact["url"]), payload)
            verify_file(payload, str(artifact["sha256"]))
            self._materialize(payload, artifact)
        except ReleaseError as exc:
            failures[target] = int(failures.get(target) or 0) + 1
            registry["updateFailures"] = failures
            self._save(registry)
            if payload and payload.exists() and exc.code == "CHECKSUM_MISMATCH":
                payload.unlink()
            return Result(False, exc.code, exc.message)
        except OSError as exc:
            failures[target] = int(failures.get(target) or 0) + 1
            registry["updateFailures"] = failures
            self._save(registry)
            partial = self.layout.staging_dir / "partial"
            if partial.exists():
                partial.unlink()
            return Result(False, "DOWNLOAD_INTERRUPTED", f"The update download did not finish. {exc}")
        registry["installedVersion"] = target
        registry["health"] = "updated"
        registry["recovery"] = {"lastGoodVersion": version}
        history = list(registry.get("updateHistory") or [])
        history.append({"version": target, "action": "update", "previous": version})
        registry["updateHistory"] = history
        registry["updateFailures"] = {key: value for key, value in failures.items() if key != target}
        self._save(registry)
        self.log(f"updated {version} -> {target}")
        return Result(True, "UPDATED", f"Adept UI is now {target}.", {"previous": version})

    def doctor(self) -> Result:
        registry = read_registry(self.layout.registry_path)
        problems: list[str] = []
        if registry is None:
            return Result(False, "NOT_INSTALLED", "Adept UI is not installed.")
        if not registry.get("installedVersion"):
            problems.append("version")
        location = Path(str(registry.get("location") or ""))
        if not location.is_dir():
            problems.append("application")
        cli = registry.get("cli")
        if not cli or not Path(str(cli)).is_file():
            problems.append("command")
        shortcut = registry.get("desktopShortcut")
        if shortcut and not Path(str(shortcut)).is_file():
            problems.append("shortcut")
        if self.profile.ram_bytes and self.profile.ram_bytes < 8 * 1024 * 1024 * 1024:
            problems.append("memory")
        code = "HEALTHY" if not problems else "NEEDS_REPAIR"
        return Result(not problems, code, "Adept UI installation looks healthy." if not problems else "Adept UI needs repair.", {"problems": problems})

    def repair(self, payload: Path | None) -> Result:
        registry = self._registry()
        if not registry.get("installedVersion"):
            return Result(False, "NOT_INSTALLED", "There is no Adept UI installation to repair.")
        user_marker = self.layout.user_data / "project.txt"
        before = user_marker.read_text(encoding="utf-8") if user_marker.is_file() else None
        if payload and payload.is_file():
            self._materialize(payload, {"kind": "zip"})
        self._copy_manager()
        cli = self._write_cli()
        registry["cli"] = str(cli)
        registry["health"] = "repaired"
        self._save(registry)
        after = user_marker.read_text(encoding="utf-8") if user_marker.is_file() else None
        if before != after:
            return Result(False, "USER_DATA_CHANGED", "Repair stopped because personal files would have changed.")
        return Result(True, "REPAIRED", "Missing Adept UI files were restored. Projects were left in place.")

    def uninstall(
        self,
        *,
        remove_app: bool,
        remove_models: bool,
        remove_settings: bool,
        confirmed: bool,
    ) -> Result:
        if not confirmed:
            return Result(False, "NOT_CONFIRMED", "Uninstall did not continue. Nothing was removed.")
        if not remove_app:
            return Result(False, "APP_KEPT", "The Adept UI application was left installed.")
        registry = read_registry(self.layout.registry_path)
        if registry is None:
            return Result(False, "NOT_INSTALLED", "Adept UI is not installed.")
        removed_models: list[str] = []
        recovered = 0
        if remove_models:
            model_result = self.remove_managed_models()
            if not model_result.ok and model_result.code != "NO_MODELS":
                return model_result
            removed_models = list(model_result.details.get("removed") or [])
            recovered = int(model_result.details.get("recoveredBytes") or 0)
        removed_files: list[str] = []
        for recorded in list(registry.get("managedFiles") or []):
            path = Path(str(recorded))
            contained = resolve_contained(path, self.layout.app_dir)
            if contained is None or is_shared_dependency(path):
                self.log(f"refused {recorded}")
                continue
            if contained.is_file():
                contained.unlink()
                removed_files.append(str(contained))
        self._remove_launcher_files(registry)
        if remove_settings:
            settings = self.layout.root / "settings"
            if settings.is_dir() and resolve_contained(settings, self.layout.root):
                shutil.rmtree(settings)
        if self.layout.registry_path.is_file():
            self.layout.registry_path.unlink()
        user_kept = self.layout.user_data.is_dir()
        self.log("uninstalled")
        return Result(
            True,
            "UNINSTALLED",
            "Adept UI was removed. Personal projects were kept.",
            {"removed": removed_files, "models": removed_models, "recoveredBytes": recovered, "userDataKept": user_kept},
        )

    def remove_managed_models(self) -> Result:
        inventory_path = self.layout.model_dir / "inventory.json"
        if not inventory_path.is_file():
            return Result(True, "NO_MODELS", "No Adept UI model inventory was found.", {"removed": [], "recoveredBytes": 0})
        try:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return Result(False, "INVENTORY_INVALID", "The model inventory could not be read. No models were removed.")
        removed: list[dict[str, Any]] = []
        recovered = 0
        for item in inventory.get("models") or []:
            if not isinstance(item, dict) or item.get("managed") is not True or item.get("owner") != "adept-ui":
                continue
            path = Path(str(item.get("path") or ""))
            if self.profile.os_name == "windows" and not windows_model_on_system_drive(path, self.layout.system_drive):
                self.log(f"model outside system drive {path}")
                continue
            contained = resolve_contained(path, self.layout.model_dir)
            if contained is None or is_shared_dependency(path):
                self.log(f"model refused {path}")
                continue
            if not contained.is_file():
                continue
            size = contained.stat().st_size
            contained.unlink()
            recovered += size
            removed.append({"name": item.get("name"), "path": str(contained), "bytes": size})
        self._write_model_inventory([])
        return Result(True, "MODELS_REMOVED", "Approved Adept UI models were removed.", {"removed": removed, "recoveredBytes": recovered})

    def _materialize(self, payload: Path, artifact: dict[str, Any]) -> list[str]:
        self.layout.app_dir.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        kind = str(artifact.get("kind") or "zip")
        if kind == "zip":
            with zipfile.ZipFile(payload) as archive:
                for info in archive.infolist():
                    if not info.filename or info.filename.endswith("/"):
                        continue
                    destination = (self.layout.app_dir / info.filename).resolve()
                    if self.layout.app_dir.resolve() not in destination.parents:
                        raise OSError("The archive tried to write outside the installation folder.")
                archive.extractall(self.layout.app_dir)
            for file in self.layout.app_dir.rglob("*"):
                if file.is_file() and "lifecycle" not in file.parts:
                    written.append(str(file))
            return written
        marker = self.layout.app_dir / payload.name
        shutil.copy2(payload, marker)
        written.append(str(marker))
        return written

    def _executable(self) -> Path | None:
        override = os.environ.get("ADEPT_APP_EXECUTABLE")
        if override and Path(override).exists():
            return Path(override)
        names = {
            "windows": ["Adept UI.exe"],
            "darwin": ["Adept UI.app"],
            "linux": ["Adept UI.AppImage", "Adept UI"],
        }
        for name in names.get(self.profile.os_name, []):
            candidate = self.layout.app_dir / name
            if candidate.exists():
                return candidate
        return None

    def _copy_manager(self) -> list[str]:
        destination = self.layout.app_dir / "lifecycle" / "adept_lifecycle"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(PACKAGE_ROOT, destination)
        managed: list[str] = []
        for file in destination.rglob("*"):
            if file.is_file():
                managed.append(str(file))
        return managed

    def _write_cli(self) -> Path:
        self.layout.bin_dir.mkdir(parents=True, exist_ok=True)
        module = self.layout.app_dir / "lifecycle"
        if self.profile.os_name == "windows":
            path = self.layout.bin_dir / "adeptui.cmd"
            path.write_text(
                f"@echo off\r\nset PYTHONPATH={module}\r\nwhere pythonw >nul 2>&1 && pythonw -m adept_lifecycle %* && exit /b 0\r\npython -m adept_lifecycle %*\r\n",
                encoding="utf-8",
            )
        else:
            path = self.layout.bin_dir / "adeptui"
            path.write_text(
                f"#!/bin/sh\nexport PYTHONPATH=\"{module}\"\nexec python3 -m adept_lifecycle \"$@\"\n",
                encoding="utf-8",
            )
            path.chmod(0o755)
        return path

    def _shortcut(self, cli: Path) -> str:
        if self.profile.os_name == "linux":
            destination = self.layout.desktop_dir / "Adept UI.desktop"
        elif self.profile.os_name == "darwin":
            destination = self.layout.desktop_dir / "Adept UI.command"
        else:
            destination = self.layout.desktop_dir / "Adept UI.vbs"
        write_launcher(destination, cli, self.profile.os_name)
        return str(destination)

    def _remove_launcher_files(self, registry: dict[str, Any]) -> None:
        for key in ("desktopShortcut", "cli"):
            recorded = registry.get(key)
            if not recorded:
                continue
            path = Path(str(recorded))
            root = self.layout.desktop_dir if key == "desktopShortcut" else self.layout.bin_dir
            contained = resolve_contained(path, root)
            if contained is not None and contained.is_file():
                contained.unlink()
        menu = self.layout.applications_dir / "adept-ui.desktop"
        if menu.is_file():
            menu.unlink()

    def _write_model_inventory(self, models: list[dict[str, Any]]) -> None:
        self.layout.model_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(self.layout.model_dir / "inventory.json", {"models": models})
