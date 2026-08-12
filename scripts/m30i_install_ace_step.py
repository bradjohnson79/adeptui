#!/usr/bin/env python3
"""Install ACE-Step into M2.10b sandbox as isolated music worker (M3.0i).

Uses a short physical venv path on Windows to avoid WinError 206.
Does not authorize fal. Refuses fixture/stub audio.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = "m2101-music-045"
SANDBOX = ROOT / "data" / "m210b-sandbox" / "providers" / REG
VENV_PHYS = ROOT / "data" / "m210b-ace-venv"
REPO_URL = "https://github.com/ace-step/ACE-Step.git"
REPO_DIR = SANDBOX / "src" / "ACE-Step"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _py() -> Path:
    return VENV_PHYS / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def main() -> int:
    SANDBOX.mkdir(parents=True, exist_ok=True)
    (SANDBOX / "output").mkdir(exist_ok=True)
    (SANDBOX / "models").mkdir(exist_ok=True)
    log: dict = {"startedAt": _now(), "registryId": REG, "source": REPO_URL}

    if not VENV_PHYS.exists():
        print("creating venv", VENV_PHYS)
        venv.create(VENV_PHYS, with_pip=True)
    py = _py()
    if not py.exists():
        print("venv python missing", py)
        return 2

    # Junction/link expected layout venv -> physical
    link = SANDBOX / "venv"
    if not link.exists():
        try:
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(VENV_PHYS)], check=False)
            else:
                link.symlink_to(VENV_PHYS, target_is_directory=True)
        except Exception as exc:
            log["venvLinkWarning"] = str(exc)

    if not REPO_DIR.exists():
        REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)

    # Install package editable + deps (may take long / need torch CUDA)
    req = REPO_DIR / "requirements.txt"
    cmds = [
        [str(py), "-m", "pip", "install", "-U", "pip", "wheel", "setuptools"],
    ]
    if req.is_file():
        cmds.append([str(py), "-m", "pip", "install", "-r", str(req)])
    cmds.append([str(py), "-m", "pip", "install", "-e", str(REPO_DIR)])

    for c in cmds:
        print(">>", " ".join(c))
        r = subprocess.run(c, cwd=str(REPO_DIR))
        log.setdefault("pip", []).append({"cmd": c, "code": r.returncode})
        if r.returncode != 0:
            log["status"] = "INSTALL_FAILED"
            log["finishedAt"] = _now()
            (SANDBOX / "install-manifest.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
            return r.returncode

    # Probe import
    probe = subprocess.run(
        [str(py), "-c", "import importlib; print('ace_step_probe', importlib.util.find_spec('acestep') or importlib.util.find_spec('ace_step') or 'unknown')"],
        capture_output=True,
        text=True,
    )
    log["importProbe"] = {"code": probe.returncode, "stdout": probe.stdout, "stderr": probe.stderr[-2000:]}
    log["installed"] = probe.returncode == 0
    log["sandboxOnly"] = True
    log["productionApproved"] = False
    log["route"] = "isolated_worker_subprocess"
    log["finishedAt"] = _now()
    log["status"] = "RUNTIME_INSTALLED" if log["installed"] else "INSTALL_UNVERIFIED"
    (SANDBOX / "install-manifest.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    out = ROOT / "artifacts" / "m30i" / "native-production" / "preflight" / "ace-step-install.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps({"status": log["status"], "manifest": str(SANDBOX / "install-manifest.json")}, indent=2))
    return 0 if log["installed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
