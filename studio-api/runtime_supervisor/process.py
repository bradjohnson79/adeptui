"""Process identity and tree kill. No powershell.exe WMI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def process_image_name(pid: int) -> str:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(32768)
            ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
            return buf.value if ok else ""
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        return os.readlink(f"/proc/{int(pid)}/exe")
    except OSError:
        return ""


def process_command_line(pid: int) -> str:
    """Best-effort command line. Uses WMIC (not PowerShell) on Windows, /proc on POSIX."""
    if sys.platform == "win32":
        try:
            completed = subprocess.run(
                [
                    "wmic",
                    "process",
                    "where",
                    f"ProcessId={int(pid)}",
                    "get",
                    "CommandLine",
                    "/format:list",
                ],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            for line in (completed.stdout or "").splitlines():
                if line.startswith("CommandLine="):
                    return line.split("=", 1)[1].strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
        return process_image_name(pid)
    try:
        return Path(f"/proc/{int(pid)}/cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
    except OSError:
        return ""


def kill_process_tree(pid: int) -> bool:
    """Kill the process tree. Windows: taskkill /F /T. Never kill pid<=0."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        completed = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(int(pid))],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return completed.returncode == 0 or not process_alive(pid)
    try:
        os.kill(int(pid), 9)
        return True
    except OSError:
        return not process_alive(pid)


def is_studio_api_command(cmd: str) -> bool:
    lower = (cmd or "").lower()
    return "uvicorn" in lower and "app.main" in lower


def is_comfy_command(cmd: str) -> bool:
    lower = (cmd or "").lower()
    return "main.py" in lower and "comfy" in lower


def is_cloudflared_command(cmd: str) -> bool:
    return "cloudflared" in (cmd or "").lower()


def is_ollama_command(cmd: str) -> bool:
    return "ollama" in (cmd or "").lower()
