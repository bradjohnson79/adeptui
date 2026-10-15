"""Isolated Update Manager demo. Does not touch the installed Adept UI."""

from __future__ import annotations

import hashlib
import os
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adept_lifecycle.detect import SystemProfile
from adept_lifecycle.manager import Hooks, Layout, Lifecycle
from adept_lifecycle.release import sign_catalog

KEY = b"test-release-key"


def catalog(version: str, digest: str, size: int) -> dict:
    body = {
        "approved": True,
        "channel": "beta",
        "artifacts": [
            {
                "platform": "windows",
                "arch": "x64",
                "version": version,
                "sha256": digest,
                "bytes": size,
                "kind": "zip",
                "fileName": "AdeptUI.zip",
            }
        ],
    }
    return sign_catalog(body, KEY)


def main() -> None:
    root = Path(os.environ.get("ADEPT_DEMO_ROOT") or Path(os.environ["TEMP"]) / "adept-update-demo")
    if root.exists():
        import shutil

        shutil.rmtree(root)
    root.mkdir()
    install_root = root / "install"
    payload = root / "app.zip"
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("Adept UI.exe", b"adept")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    profile = SystemProfile("windows", "test", "x64", None, 16 << 30, 50 << 30, "nvidia", 24 << 30)
    installed = Lifecycle(Layout(install_root), profile, KEY, Hooks())
    result = installed.install(catalog("1.1.2", digest, payload.stat().st_size), payload)
    if not result.ok:
        raise SystemExit(result.message)
    (install_root / "user-data").mkdir(exist_ok=True)
    (install_root / "user-data" / "project.txt").write_text("keep", encoding="utf-8")
    scenario = os.environ.get("ADEPT_DEMO_SCENARIO", "update")
    newer = root / "newer.zip"
    with zipfile.ZipFile(newer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("Adept UI.exe", b"updated" + (b"x" * 6_000_000))
    good_digest = hashlib.sha256(newer.read_bytes()).hexdigest()
    if scenario == "fail":
        offered = catalog("1.1.3", good_digest, newer.stat().st_size)
        payload_path = root / "bad.zip"
        payload_path.write_bytes(b"not-the-archive")
    elif scenario == "noupdate":
        offered = catalog("1.1.2", digest, payload.stat().st_size)
        payload_path = newer
    else:
        offered = catalog("1.1.3", good_digest, newer.stat().st_size)
        payload_path = newer
    url_name = os.environ.get("ADEPT_UPDATER_URL_FILE")
    if url_name:
        os.environ["ADEPT_UPDATER_URL_FILE"] = url_name

    def hold() -> None:
        time.sleep(float(os.environ.get("ADEPT_HOLD_SECONDS", "20")))

    updated = Lifecycle(
        Layout(install_root),
        profile,
        KEY,
        Hooks(
            fetch_catalog=lambda: offered,
            read_payload=lambda _artifact: payload_path,
            launch=lambda _path: 0,
            show_updater=scenario != "noupdate",
            hold_completion=hold,
            chunk_pause=float(os.environ.get("ADEPT_CHUNK_PAUSE", "0.08")),
        ),
    ).launch()
    (root / "result.txt").write_text(f"{updated.code}\n{updated.message}\n", encoding="utf-8")
    if scenario == "fail":
        time.sleep(float(os.environ.get("ADEPT_HOLD_SECONDS", "8")))


if __name__ == "__main__":
    main()
