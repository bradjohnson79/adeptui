#!/usr/bin/env python3
"""Install MMAudio (preferred) or Stable-Audio-Tools (fallback) for M3.0i SFX.

Isolated short-path venv. Capability roles: sfx/ambience/foley only — never music.
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
REG_MMAUDIO = "m2101-sfx-031"
REG_STABLE = "m2101-sfx-021"
SANDBOX_MM = ROOT / "data" / "m210b-sandbox" / "providers" / REG_MMAUDIO
SANDBOX_SA = ROOT / "data" / "m210b-sandbox" / "providers" / REG_STABLE
VENV_PHYS = ROOT / "data" / "m210b-sfx-venv"
MMAUDIO_URL = "https://github.com/hkchengrex/MMAudio.git"
STABLE_URL = "https://github.com/Stability-AI/stable-audio-tools.git"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _py() -> Path:
    return VENV_PHYS / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )


def _link_venv(sandbox: Path) -> None:
    link = sandbox / "venv"
    if link.exists():
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(VENV_PHYS)], check=False
            )
        else:
            link.symlink_to(VENV_PHYS, target_is_directory=True)
    except Exception:
        pass


def _try_mmaudio(py: Path, log: dict) -> bool:
    SANDBOX_MM.mkdir(parents=True, exist_ok=True)
    for sub in ("output", "models", "src"):
        (SANDBOX_MM / sub).mkdir(exist_ok=True)
    _link_venv(SANDBOX_MM)
    repo = SANDBOX_MM / "src" / "MMAudio"
    if not repo.exists():
        r = subprocess.run(
            ["git", "clone", "--depth", "1", MMAUDIO_URL, str(repo)], check=False
        )
        if r.returncode != 0:
            log["mmaudioClone"] = {"code": r.returncode}
            return False
    cmds = [
        [str(py), "-m", "pip", "install", "-U", "pip", "wheel", "setuptools"],
        [str(py), "-m", "pip", "install", "-e", str(repo)],
    ]
    req = repo / "requirements.txt"
    if req.is_file():
        cmds.insert(1, [str(py), "-m", "pip", "install", "-r", str(req)])
    for c in cmds:
        print(">>", " ".join(c))
        r = subprocess.run(c, cwd=str(repo))
        log.setdefault("pip", []).append({"cmd": c, "code": r.returncode})
        if r.returncode != 0:
            return False
    probe = subprocess.run(
        [str(py), "-c", "import mmaudio; print('mmaudio_ok', mmaudio.__file__)"],
        capture_output=True,
        text=True,
    )
    log["importProbe"] = {
        "code": probe.returncode,
        "stdout": probe.stdout[-500:],
        "stderr": probe.stderr[-500:],
    }
    if probe.returncode != 0:
        return False
    log.update(
        {
            "installed": True,
            "provider": "mmaudio",
            "registryId": REG_MMAUDIO,
            "fallbackUsed": False,
            "capabilities": ["sfx.generate", "ambience.generate", "foley.generate"],
            "status": "RUNTIME_INSTALLED",
            "sandboxOnly": True,
            "productionApproved": False,
            "route": "isolated_worker_subprocess",
        }
    )
    (SANDBOX_MM / "install-manifest.json").write_text(
        json.dumps(log, indent=2), encoding="utf-8"
    )
    return True


def _try_stable_audio(py: Path, log: dict) -> bool:
    SANDBOX_SA.mkdir(parents=True, exist_ok=True)
    for sub in ("output", "models", "src"):
        (SANDBOX_SA / sub).mkdir(exist_ok=True)
    _link_venv(SANDBOX_SA)
    repo = SANDBOX_SA / "src" / "stable-audio-tools"
    if not repo.exists():
        r = subprocess.run(
            ["git", "clone", "--depth", "1", STABLE_URL, str(repo)], check=False
        )
        if r.returncode != 0:
            log["stableClone"] = {"code": r.returncode}
            return False
    cmds = [
        [str(py), "-m", "pip", "install", "-U", "pip", "wheel", "setuptools"],
        [str(py), "-m", "pip", "install", "-e", str(repo)],
    ]
    req = repo / "requirements.txt"
    if req.is_file():
        cmds.insert(1, [str(py), "-m", "pip", "install", "-r", str(req)])
    for c in cmds:
        print(">>", " ".join(c))
        r = subprocess.run(c, cwd=str(repo))
        log.setdefault("pip", []).append({"cmd": c, "code": r.returncode})
        if r.returncode != 0:
            return False
    probe = subprocess.run(
        [
            str(py),
            "-c",
            "import stable_audio_tools; print('stable_audio_ok', stable_audio_tools.__file__)",
        ],
        capture_output=True,
        text=True,
    )
    log["importProbe"] = {
        "code": probe.returncode,
        "stdout": probe.stdout[-500:],
        "stderr": probe.stderr[-500:],
    }
    if probe.returncode != 0:
        return False
    log.update(
        {
            "installed": True,
            "provider": "stable-audio-tools",
            "registryId": REG_STABLE,
            "fallbackUsed": True,
            "preferredProvider": "mmaudio",
            "fallbackReason": "MMAudio install failed; local Stable-Audio-Tools used",
            "capabilities": ["sfx.generate", "ambience.generate", "foley.generate"],
            "status": "RUNTIME_INSTALLED",
            "sandboxOnly": True,
            "productionApproved": False,
            "route": "isolated_worker_subprocess",
            "disclosedFallback": True,
        }
    )
    (SANDBOX_SA / "install-manifest.json").write_text(
        json.dumps(log, indent=2), encoding="utf-8"
    )
    return True


def main() -> int:
    out_dir = ROOT / "artifacts" / "m30i" / "native-production" / "preflight"
    out_dir.mkdir(parents=True, exist_ok=True)
    log: dict = {"startedAt": _now(), "task": "m30i_install_sfx"}

    if not VENV_PHYS.exists():
        print("creating venv", VENV_PHYS)
        venv.create(VENV_PHYS, with_pip=True)
    py = _py()
    if not py.exists():
        print("venv python missing", py)
        return 2

    ok = _try_mmaudio(py, log)
    if not ok:
        print("MMAudio failed; attempting Stable-Audio-Tools fallback")
        log["mmaudioFailed"] = True
        ok = _try_stable_audio(py, log)
    if not ok:
        log["status"] = "INSTALL_FAILED"
        log["finishedAt"] = _now()
        (out_dir / "sfx-install.json").write_text(
            json.dumps(log, indent=2), encoding="utf-8"
        )
        return 1

    log["finishedAt"] = _now()
    (out_dir / "sfx-install.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print("STATUS", log.get("status"), "provider", log.get("provider"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
