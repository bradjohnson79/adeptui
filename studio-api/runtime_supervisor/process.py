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


def _win32_process_basic(pid: int):
    """NtQueryInformationProcess — parent PID + PEB. WMIC is removed on current Windows."""
    import ctypes
    from ctypes import wintypes

    class PROCESS_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("ExitStatus", ctypes.c_void_p),
            ("PebBaseAddress", ctypes.c_void_p),
            ("AffinityMask", ctypes.c_void_p),
            ("BasePriority", ctypes.c_void_p),
            ("UniqueProcessId", ctypes.c_void_p),
            ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ]

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid))
    if not handle:
        return None
    try:
        info = PROCESS_BASIC_INFORMATION()
        status = ctypes.windll.ntdll.NtQueryInformationProcess(
            handle, 0, ctypes.byref(info), ctypes.sizeof(info), None
        )
        if status != 0:
            ctypes.windll.kernel32.CloseHandle(handle)
            return None
        return handle, info
    except OSError:
        ctypes.windll.kernel32.CloseHandle(handle)
        return None


def _win32_read_memory(handle, address: int, size: int) -> bytes:
    import ctypes

    if not address or size <= 0:
        return b""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t(0)
    ok = ctypes.windll.kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(address), buf, size, ctypes.byref(read)
    )
    return buf.raw[: read.value] if ok else b""


def process_parent_pid(pid: int) -> int | None:
    """Best-effort parent PID. NtQuery on Windows, /proc on POSIX. Never PowerShell."""
    if not pid or pid <= 0:
        return None
    if sys.platform == "win32":
        opened = _win32_process_basic(pid)
        if not opened:
            return None
        handle, info = opened
        try:
            parent = int(info.InheritedFromUniqueProcessId or 0)
            return parent or None
        finally:
            import ctypes

            ctypes.windll.kernel32.CloseHandle(handle)
    if sys.platform == "darwin":
        try:
            parent = int(_ps_field(pid, "ppid=") or "0")
        except ValueError:
            return None
        return parent or None
    try:
        text = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        return int(text.split()[3])
    except (OSError, IndexError, ValueError):
        return None


def _ps_field(pid: int, field: str) -> str:
    if not pid or pid <= 0:
        return ""
    completed = subprocess.run(
        ["ps", "-p", str(int(pid)), "-o", field],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return (completed.stdout or "").strip()


def process_command_line(pid: int) -> str:
    """Best-effort command line. PEB read on Windows (WMIC is gone), /proc on Linux, ps on macOS."""
    if sys.platform == "win32":
        opened = _win32_process_basic(pid)
        if opened:
            handle, info = opened
            try:
                peb = int(info.PebBaseAddress or 0)
                params_raw = _win32_read_memory(handle, peb + 0x20, 8)
                if len(params_raw) == 8:
                    params = int.from_bytes(params_raw, "little")
                    # RTL_USER_PROCESS_PARAMETERS.CommandLine UNICODE_STRING at 0x70
                    us = _win32_read_memory(handle, params + 0x70, 16)
                    if len(us) >= 16:
                        length = int.from_bytes(us[0:2], "little")
                        buffer = int.from_bytes(us[8:16], "little")
                        if length and buffer:
                            raw = _win32_read_memory(handle, buffer, length)
                            if raw:
                                return raw.decode("utf-16-le", "replace")
            finally:
                import ctypes

                ctypes.windll.kernel32.CloseHandle(handle)
        return process_image_name(pid)
    if sys.platform == "darwin":
        return _ps_field(pid, "args=")
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
    if is_route_a_command(cmd):
        return False
    return "main.py" in lower and "comfy" in lower


def is_route_a_command(cmd: str) -> bool:
    lower = (cmd or "").lower()
    return "main.py" in lower and "comfy" in lower and ("8192" in lower or "minimax-h3" in lower)


def is_cloudflared_command(cmd: str) -> bool:
    return "cloudflared" in (cmd or "").lower()


def is_ollama_command(cmd: str) -> bool:
    return "ollama" in (cmd or "").lower()
