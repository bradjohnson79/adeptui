"""Universal Adept Launcher orchestration.

The launcher runs *before* the Electron application. It is the single update
authority and reuses the existing :mod:`adept_lifecycle` engine end to end:

- read the installed version from the registry
- fetch and verify the signed release catalog (pinned RSA key)
- when a newer release is approved, apply it **from outside the replaceable
  payload** by re-executing a frozen worker staged under the lifecycle root
  (``external_updater_dir``), so the running process is never overwritten
- start the application only after the check finishes

There is no second lifecycle engine and no Electron self-handoff.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from adept_lifecycle.cli import _fetch_official_catalog
from adept_lifecycle.detect import live_profile
from adept_lifecycle.manager import FAILURE_LIMIT, Hooks, Layout, Lifecycle
from adept_lifecycle.registry import atomic_write, read_registry
from adept_lifecycle.release import ReleaseError, select_artifact, verify_catalog, verify_file

from ._paths import brand_emblem, meipass


def _default_root() -> Path:
    override = os.environ.get("ADEPT_LIFECYCLE_ROOT")
    if override:
        return Path(override)
    return Path.home() / ".adept-ui"


def _sibling_app_executable() -> Path | None:
    """The Electron application installed next to this launcher.

    The packaged launcher sits beside the Electron binary in the install dir
    (Windows), inside the .app as a sibling of the real Electron binary (macOS,
    where the launcher is ``Adept UI`` and Electron is ``Adept UI.bin``), or next
    to the AppImage/ELF (Linux). When the registry has no recorded executable
    yet, the launcher adopts this sibling so a first launch boots the app.
    """
    exe = _frozen_exe()
    if exe is None:
        return None
    base = exe.parent
    if sys.platform == "win32":
        candidates = [base / "Adept UI.exe"]
    elif sys.platform == "darwin":
        # Launcher is Contents/MacOS/Adept UI; Electron is Contents/MacOS/Adept UI.bin
        candidates = [base / "Adept UI.bin"]
    else:
        # afterPack renames the real Electron ELF to "Adept UI.bin" and installs the
        # launcher as "Adept UI". Prefer the renamed sibling; fall back to a plain
        # "Adept UI" (unswapped layout) or the AppImage for direct launches.
        candidates = [base / "Adept UI.bin", base / "Adept UI", base / "Adept UI.AppImage"]
    for candidate in candidates:
        if candidate.is_file() and candidate.resolve() != exe.resolve():
            return candidate
    return None


def _packaged_version(executable: Path) -> str | None:
    """Version shipped beside Electron. A first launch records this so the next check is real."""
    import json

    if sys.platform == "darwin":
        candidate = executable.parent.parent / "Resources" / "version.json"
    else:
        candidate = executable.parent / "resources" / "version.json"
    if not candidate.is_file():
        return None
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return str(version) if version else None


def _build_hooks() -> Hooks:
    """Launch hooks: official signed catalog, no second package installer."""
    return Hooks(fetch_catalog=_fetch_official_catalog)


def _apply_brand_env() -> None:
    emblem = brand_emblem()
    if emblem is not None:
        os.environ.setdefault("ADEPT_BRAND_EMBLEM", str(emblem))


def _frozen_exe() -> Path | None:
    """The running frozen launcher executable, or None under a plain interpreter."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None


def _stage_worker(layout: Layout) -> Path | None:
    """Stage the frozen worker OUTSIDE the replaceable payload.

    Returns the staged worker executable path, or None when the launcher is not
    frozen (tests drive the worker in-process instead). The worker is a copy of
    the launcher binary placed under ``<root>/updater/`` so the replace can
    overwrite the payload without touching the running worker.
    """
    exe = _frozen_exe()
    if exe is None:
        return None
    updater_dir = layout.root / "updater"
    updater_dir.mkdir(parents=True, exist_ok=True)
    destination = updater_dir / exe.name
    # The worker must not live inside the application payload it replaces.
    if layout.app_dir.resolve() in destination.resolve().parents:
        raise OSError("The update worker must not live inside the application it replaces.")
    if destination.resolve() != exe.resolve():
        import shutil

        shutil.copy2(exe, destination)
    return destination


def _run_worker(layout: Layout, catalog: dict, artifact: dict, payload: Path, previous: str) -> int:
    """Re-exec a worker OUTSIDE the payload to apply the verified update.

    The catalog was already signature-verified and the payload already
    checksum-verified by the orchestrator before the worker was staged; the
    worker re-verifies defensively before mutating any files.
    """
    staged = _stage_worker(layout)
    args = [
        "--apply-update",
        "--root",
        str(layout.root),
        "--payload",
        str(payload),
        "--target",
        str(artifact.get("version") or ""),
        "--previous",
        previous,
    ]
    if staged is not None:
        argv = [str(staged), *args]
        kwargs = {"close_fds": True}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(argv, **kwargs)
        return completed.returncode
    return _worker_main(argparse.Namespace(root=layout.root, payload=payload, target=str(artifact.get("version") or ""), previous=previous))


def _worker_main(args: argparse.Namespace) -> int:
    """Worker entry: apply the already-verified update with recovery.

    Runs from the staged binary outside the payload. Re-verifies the payload
    checksum before replacing files and restores the previous copy on any
    failure. Never launches the application.
    """
    _apply_brand_env()
    root = Path(args.root)
    layout = Layout(root)
    profile = live_profile(str(root))
    lifecycle = Lifecycle(layout, profile, None, Hooks())
    payload = Path(args.payload)
    registry = read_registry(layout.registry_path) or {}
    artifact = {"version": args.target, "fileName": payload.name}
    try:
        result = lifecycle.apply_with_recovery(payload, artifact, args.previous)
    except OSError as exc:
        lifecycle._emit(
            phase="error",
            installedVersion=args.previous,
            targetVersion=args.target,
            operation=str(exc),
            error="INSTALL_INTERRUPTED",
            indeterminate=True,
        )
        return 1
    return 0 if result.ok else 1


def electron_command(executable: Path) -> list[str]:
    """Electron argv. ADEPT_ELECTRON_ARGS is one local override, never catalog data."""
    command = [str(executable)]
    extra = os.environ.get("ADEPT_ELECTRON_ARGS", "").strip()
    if extra:
        command.append(extra)
    return command


def _launch_app(lifecycle: Lifecycle, executable: Path) -> None:
    env = os.environ.copy()
    env["ADEPT_LAUNCHED_BY_UPDATER"] = "1"
    kwargs = {"close_fds": True, "env": env}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(electron_command(executable), **kwargs)


def _continue(lifecycle: Lifecycle, executable: Path, code: str, version: str, message: str) -> int:
    status = {"action": "continue", "code": code, "version": version}
    atomic_write(lifecycle.layout.root / "startup-update.json", status)
    _launch_app(lifecycle, executable)
    lifecycle.log(f"launch {code}")
    print(message)
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adept-launcher", description="Adept UI launcher and update authority.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--apply-update", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--payload", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--target", default="", help=argparse.SUPPRESS)
    parser.add_argument("--previous", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.apply_update:
        return _worker_main(args)

    _apply_brand_env()
    root = args.root or _default_root()
    layout = Layout(root)
    profile = live_profile(str(root))
    hooks = _build_hooks()
    lifecycle = Lifecycle(layout, profile, None, hooks)

    # Adopt the sibling Electron application for first launch / untracked installs so
    # the packaged launcher boots the app it was shipped beside.
    if not os.environ.get("ADEPT_APP_EXECUTABLE"):
        sibling = _sibling_app_executable()
        if sibling is not None:
            os.environ["ADEPT_APP_EXECUTABLE"] = str(sibling)

    registry = read_registry(layout.registry_path)
    remembered = os.environ.get("ADEPT_INSTALLED_VERSION")
    if not registry or not registry.get("installedVersion"):
        packaged = _packaged_version(lifecycle._executable()) if lifecycle._executable() else None
        if packaged and not remembered:
            remembered = packaged
    if (not registry or not registry.get("installedVersion")) and remembered:
        from adept_lifecycle.registry import empty_registry

        registry = empty_registry(profile.os_name, profile.arch, str(layout.app_dir))
        registry["installedVersion"] = remembered
        lifecycle._save(registry)
    if not registry or not registry.get("installedVersion"):
        executable = lifecycle._executable()
        if executable is not None and os.environ.get("ADEPT_APP_EXECUTABLE"):
            _launch_app(lifecycle, executable)
            print("Adept UI is starting.")
            return 0
        print("Install Adept UI before launching it.")
        return 1

    executable = lifecycle._executable()
    if executable is None:
        print("The installed Adept UI application was not found.")
        return 1
    version = str(registry.get("installedVersion"))
    if lifecycle._production_active():
        return _continue(lifecycle, executable, "DEFERRED", version, "Adept UI is starting.")
    if not lifecycle._acquire_update_lock():
        print("An update is already running.")
        return 1

    try:
        catalog = None
        try:
            catalog = hooks.fetch_catalog() if hooks.fetch_catalog else None
        except OSError:
            catalog = None
        if not catalog:
            return _continue(lifecycle, executable, "UPDATE_SERVICE_UNAVAILABLE", version, "Adept UI is starting.")

        # Verify the signed catalog and select the artifact (or NO_UPDATE).
        lifecycle._emit(phase="catalog", installedVersion=version, operation="Checking the signed release catalog", indeterminate=True)
        try:
            from adept_lifecycle.trust import pinned_public_key

            public = pinned_public_key()
            if public is None:
                raise ReleaseError("SIGNATURE_MISSING", "The release catalog has no verifiable signature.")
            from adept_lifecycle.release import verify_catalog_rsa

            verify_catalog_rsa(catalog, public)
            artifact = select_artifact(catalog, profile, version)
        except ReleaseError as exc:
            if exc.code == "NO_UPDATE":
                return _continue(lifecycle, executable, "NO_UPDATE", version, "Adept UI is up to date.")
            lifecycle._emit(phase="error", installedVersion=version, operation=exc.message, error=exc.code, indeterminate=True)
            return _continue(lifecycle, executable, exc.code, version, exc.message)

        target = str(artifact["version"])
        failures = dict(registry.get("updateFailures") or {})
        if int(failures.get(target) or 0) >= FAILURE_LIMIT:
            lifecycle._emit(
                phase="error",
                installedVersion=version,
                targetVersion=target,
                operation="This update failed repeatedly and will not be tried again automatically.",
                error="UPDATE_LOOP_STOPPED",
                indeterminate=True,
            )
            return _continue(lifecycle, executable, "UPDATE_LOOP_STOPPED", version, "Adept UI is starting with the installed version.")

        # Progress screen: serve the existing updater page.
        updater_url = lifecycle._serve_updater()
        marker = os.environ.get("ADEPT_UPDATER_URL_FILE")
        if marker:
            Path(marker).write_text(updater_url, encoding="utf-8")

        # Download with byte progress, then verify checksum before any replace.
        lifecycle._emit(
            phase="download",
            installedVersion=version,
            targetVersion=target,
            operation="Downloading update",
            downloadPercent=0,
            indeterminate=False,
        )
        payload = layout.staging_dir / str(artifact.get("fileName") or "update.bin")
        try:
            lifecycle._obtain_payload(artifact, payload, version, target)
            lifecycle._emit(phase="checksum", installedVersion=version, targetVersion=target, operation="Checking the download", indeterminate=True)
            verify_file(payload, str(artifact["sha256"]))
        except (ReleaseError, OSError) as exc:
            code = getattr(exc, "code", "INSTALL_INTERRUPTED")
            message = getattr(exc, "message", str(exc))
            lifecycle._record_update_failure(registry, failures, target)
            if payload.exists() and code == "CHECKSUM_MISMATCH":
                payload.unlink()
            lifecycle._emit(phase="error", installedVersion=version, targetVersion=target, operation=message, error=code, indeterminate=True)
            return _continue(lifecycle, executable, code, version, message)

        # Apply from OUTSIDE the payload via the staged worker.
        lifecycle._emit(phase="install", installedVersion=version, targetVersion=target, operation="Installing the update", indeterminate=True)
        worker_rc = _run_worker(layout, catalog, artifact, payload, version)
        if worker_rc != 0:
            lifecycle._record_update_failure(registry, failures, target)
            restored = lifecycle._executable() or executable
            lifecycle._emit(
                phase="error",
                installedVersion=version,
                targetVersion=target,
                operation="The update did not finish. The installed Adept UI was left in place.",
                error="INSTALL_INTERRUPTED",
                indeterminate=True,
            )
            return _continue(lifecycle, restored, "INSTALL_INTERRUPTED", version, "The update did not finish. The installed Adept UI was left in place.")

        lifecycle._emit(
            phase="complete",
            installedVersion=target,
            targetVersion=target,
            operation=f"Adept UI {target} installed successfully.",
            overallPercent=100,
            downloadPercent=100,
            complete=True,
            footer="Updates complete.",
        )
        atomic_write(layout.root / "startup-update.json", {"action": "continue", "code": "UPDATED", "version": target})
        new_executable = lifecycle._executable() or executable
        _launch_app(lifecycle, new_executable)
        lifecycle.log(f"launch UPDATED {version} -> {target}")
        print(f"Adept UI is now {target}.")
        return 0
    finally:
        lifecycle._release_update_lock()


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
