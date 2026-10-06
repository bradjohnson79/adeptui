"""Single Task Scheduler authority for AdeptRuntimeService.

Setup Wizard and Settings must both call this module.
Do not register AdeptUI-Runtime-Manager or AdeptBetaBackendManager as Comfy owners.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .canonical_config import RuntimeConfig, try_load_runtime_config
from .constants import LEGACY_TASK_NAMES, TASK_NAME

ELEVATING_ENV = "ADEPT_TASK_ELEVATING"


class PrivilegeRequired(RuntimeError):
    """schtasks needs a one-time Windows approval. Not a weaker scheduler fallback."""

    def __init__(self, detail: str):
        super().__init__(
            "Windows needs permission to start Background Services when you sign in. "
            "Approve that once in Setup. Adept will not use a weaker startup method. "
            f"({detail})"
        )
        self.detail = detail
        self.needsElevation = True


def _is_privilege_denied(text: str) -> bool:
    blob = (text or "").lower()
    return any(
        token in blob
        for token in (
            "access is denied",
            "access denied",
            "unauthorizedaccess",
            "0x80070005",
        )
    )


@dataclass
class TaskStatus:
    name: str
    exists: bool
    running: bool = False
    raw: str = ""
    needsElevation: bool = False


def _run_schtasks(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["schtasks.exe", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def query_task(name: str = TASK_NAME) -> TaskStatus:
    if sys.platform != "win32":
        return TaskStatus(name=name, exists=False, running=False, raw="")
    completed = _run_schtasks(["/Query", "/TN", name, "/FO", "LIST", "/V"])
    text = (completed.stdout or "") + (completed.stderr or "")
    exists = completed.returncode == 0 and "ERROR:" not in (completed.stderr or "").upper()
    running = exists and ("Running" in (completed.stdout or ""))
    return TaskStatus(name=name, exists=exists, running=running, raw=text)


def task_exists(name: str = TASK_NAME) -> bool:
    return query_task(name).exists


def list_legacy_owners() -> list[str]:
    found: list[str] = []
    for name in LEGACY_TASK_NAMES:
        if task_exists(name):
            found.append(name)
    return found


def _serve_launch(cfg: RuntimeConfig) -> tuple[Path, Path]:
    py = cfg.service_python_path()
    if not py.is_file():
        raise RuntimeError("CONFIGURATION ERROR: servicePython is not a file — cannot register task")
    if py.suffix.lower() == ".exe" and py.name.lower() == "python.exe":
        pythonw = py.with_name("pythonw.exe")
        if pythonw.is_file():
            py = pythonw
    module_root = Path(cfg.repoRoot) / "studio-api" if cfg.repoRoot else py.resolve().parents[2]
    cwd_hint = module_root if (module_root / "runtime_supervisor").is_dir() else py.resolve().parents[2]
    return py, cwd_hint


def _tr_command(cfg: RuntimeConfig) -> str:
    py, cwd_hint = _serve_launch(cfg)
    # Working directory must be studio-api so `-m runtime_supervisor` resolves at logon.
    return f'cmd.exe /c "cd /d {cwd_hint} && {py} -m runtime_supervisor serve"'


def _register_current_user_powershell(cfg: RuntimeConfig, name: str) -> subprocess.CompletedProcess[str]:
    """Current-user AtLogOn via Task Scheduler. Same task name. Not a Startup-folder fallback."""
    py, cwd_hint = _serve_launch(cfg)
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"$action = New-ScheduledTaskAction -Execute {json.dumps(str(py))} "
        f"-Argument '-m runtime_supervisor serve' -WorkingDirectory {json.dumps(str(cwd_hint))}; "
        "$trigger = New-ScheduledTaskTrigger -AtLogOn; "
        "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited; "
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew; "
        f"Register-ScheduledTask -TaskName {json.dumps(name)} -Action $action -Trigger $trigger "
        "-Principal $principal -Settings $settings -Force | Out-Null"
    )
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )


def _elevate_and_register(cfg: RuntimeConfig, name: str) -> None:
    """One-shot UAC relaunch of install-task. Success is query_task().exists only.

    Writes a temp .ps1 to avoid nested PowerShell -Command quoting breakage on Windows.
    """
    if os.environ.get(ELEVATING_ENV) == "1":
        return
    import tempfile

    py, cwd_hint = _serve_launch(cfg)
    launcher = py
    if launcher.name.lower() == "pythonw.exe":
        alt = launcher.with_name("python.exe")
        if alt.is_file():
            launcher = alt
    # Single-quoted PowerShell literals — no nested JSON escaping.
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$env:{ELEVATING_ENV} = '1'\n"
        f"Set-Location -LiteralPath '{str(cwd_hint)}'\n"
        f"& '{str(launcher)}' -m runtime_supervisor install-task\n"
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }\n"
    )
    fd, tmp_path = tempfile.mkstemp(prefix="adept-install-task-", suffix=".ps1")
    os.close(fd)
    tmp = Path(tmp_path)
    try:
        tmp.write_text(script, encoding="utf-8")
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -WindowStyle Normal "
                f"-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',{json.dumps(str(tmp))})",
            ],
            text=True,
            timeout=180,
            check=False,
        )
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass



def register_task(
    cfg: RuntimeConfig | None = None,
    *,
    name: str = TASK_NAME,
    allow_elevate: bool = True,
) -> TaskStatus:
    config = cfg or try_load_runtime_config()
    if config is None:
        raise RuntimeError("CONFIGURATION ERROR: runtime.json missing — task not registered")
    from .canonical_config import validate_runtime_config

    errors = validate_runtime_config(config)
    if errors:
        raise RuntimeError("CONFIGURATION ERROR: " + "; ".join(errors) + " — task not registered")

    already = query_task(name)
    if already.exists:
        return already

    # Prefer current-user Task Scheduler registration (WorkingDirectory + AtLogOn).
    # If the host denies that, try one UAC elevation. Never use Startup-folder hacks.
    ps = _register_current_user_powershell(config, name)
    ps_text = ((ps.stderr or "") + "\n" + (ps.stdout or "")).strip()
    if ps.returncode == 0 and query_task(name).exists:
        return query_task(name)

    tr = _tr_command(config)
    completed = _run_schtasks(
        ["/Create", "/TN", name, "/TR", tr, "/SC", "ONLOGON", "/RL", "LIMITED", "/IT", "/F"]
    )
    text = ((completed.stderr or "") + "\n" + (completed.stdout or "")).strip()
    if completed.returncode == 0 and query_task(name).exists:
        return query_task(name)

    combined = (ps_text + "\n" + text).strip()
    elevating = os.environ.get(ELEVATING_ENV) == "1"
    if allow_elevate and not elevating and _is_privilege_denied(combined):
        _elevate_and_register(config, name)
        proven = query_task(name)
        if proven.exists:
            return proven
        raise PrivilegeRequired(
            "Windows approval was cancelled or AdeptRuntimeService is still missing."
        )
    if _is_privilege_denied(combined):
        raise PrivilegeRequired(
            next((line for line in combined.splitlines() if line.strip()), "Access is denied")
        )
    raise RuntimeError(
        "Failed to register AdeptRuntimeService: " + (combined or f"exit {completed.returncode}")
    )


def unregister_task(name: str = TASK_NAME) -> TaskStatus:
    if not task_exists(name):
        return TaskStatus(name=name, exists=False)
    completed = _run_schtasks(["/Delete", "/TN", name, "/F"])
    if completed.returncode != 0 and task_exists(name):
        raise RuntimeError(
            f"Failed to unregister {name}: {(completed.stderr or completed.stdout or '').strip()}"
        )
    return query_task(name)


def start_task(name: str = TASK_NAME) -> TaskStatus:
    if not task_exists(name):
        raise RuntimeError(f"Task {name} is not registered")
    completed = _run_schtasks(["/Run", "/TN", name])
    if completed.returncode != 0:
        raise RuntimeError(
            f"Failed to start {name}: {(completed.stderr or completed.stdout or '').strip()}"
        )
    return query_task(name)


def retire_legacy_tasks() -> list[str]:
    """Unregister competing supervisors. Call only after AdeptRuntimeService is proven."""
    if not task_exists(TASK_NAME):
        return []
    retired: list[str] = []
    for name in list_legacy_owners():
        unregister_task(name)
        retired.append(name)
    return retired
