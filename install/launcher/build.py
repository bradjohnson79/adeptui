"""Headless builder for the Universal Adept Launcher.

Builds the frozen launcher with PyInstaller without opening any console
window. Captures stdout/stderr to a structured log so failures remain visible
through Cursor's task output and the log file — never through a terminal popup.

Usage (quiet, from Cursor's integrated shell)::

    pythonw install/launcher/build.py
    python  install/launcher/build.py --show-log

Exit code 0 on success. The frozen executable is written to
``install/launcher/dist/`` and the PyInstaller log to
``install/launcher/dist/build.log``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SPEC = HERE / "launcher.spec"
DIST = HERE / "dist"
BUILD = HERE / "build"
LOG = DIST / "build.log"


def _no_window_kwargs() -> dict:
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startup = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        startup.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startup
    return kwargs


def _run(cmd: list[str], log) -> int:
    log.write("$ " + " ".join(cmd) + "\n")
    log.flush()
    completed = subprocess.run(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
        **_no_window_kwargs(),
    )
    log.write(f"[exit {completed.returncode}]\n\n")
    log.flush()
    return completed.returncode


def _python() -> str:
    return sys.executable


def _ensure_pyinstaller(log) -> bool:
    try:
        import PyInstaller  # noqa: F401

        log.write("pyinstaller: already available\n")
        return True
    except ImportError:
        log.write("pyinstaller: installing\n")
        return _run([_python(), "-m", "pip", "install", "--quiet", "pyinstaller"], log) == 0


def build() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    with LOG.open("w", encoding="utf-8") as log:
        log.write(f"python: {sys.executable}\n")
        log.write(f"platform: {sys.platform}\n\n")
        if not _ensure_pyinstaller(log):
            log.write("FATAL: PyInstaller could not be installed.\n")
            return 1
        rc = _run(
            [
                _python(),
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--clean",
                "--distpath",
                str(DIST),
                "--workpath",
                str(BUILD),
                str(SPEC),
            ],
            log,
        )
        if rc != 0:
            log.write("FATAL: PyInstaller build failed.\n")
            return rc
        log.write("BUILD OK\n")
        return 0


def _staged_name() -> str:
    if sys.platform == "win32":
        return "Adept Launcher.exe"
    if sys.platform == "darwin":
        return "Adept UI"
    return "adept-launcher"


def stage() -> Path | None:
    """Copy the built launcher into electron/build/launcher for electron-builder."""
    import shutil

    built = DIST / _staged_name()
    if not built.is_file():
        return None
    target_dir = REPO_ROOT / "electron" / "build" / "launcher"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _staged_name()
    shutil.copy2(built, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-log", action="store_true")
    parser.add_argument("--stage", action="store_true", help="Stage the launcher into electron/build/launcher")
    args = parser.parse_args()
    rc = build()
    if args.show_log and LOG.is_file():
        sys.stdout.write(LOG.read_text(encoding="utf-8"))
    if rc == 0:
        if args.stage:
            staged = stage()
            if staged:
                print(f"Launcher staged: {staged}")
            else:
                print("Launcher staging FAILED (built exe not found)")
                return 1
        print(f"Launcher built. Log: {LOG}")
    else:
        print(f"Launcher build FAILED (see {LOG})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
