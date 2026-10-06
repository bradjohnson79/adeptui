"""Port owner detection. Windows uses IP Helper — never NETSTAT.EXE.

NETSTAT.EXE 0xc0000142 (DLL init failure) was observed on the Adept host and
pops a blocking error dialog. Do not spawn netstat from the supervisor.
"""

from __future__ import annotations

import re
import socket
import struct
import sys
import time

_LISTENING_RE = re.compile(r":(?P<port>\d+)\s+\S+\s+LISTENING\s+(?P<pid>\d+)\s*$", re.IGNORECASE)
_LISTENING_RE_ALT = re.compile(r":(?P<port>\d+).+LISTENING\s+(?P<pid>\d+)\s*$", re.IGNORECASE)

_MIB_TCP_STATE_LISTEN = 2
_AF_INET = 2
_TCP_TABLE_OWNER_PID_ALL = 5


def parse_netstat_owner(netstat_text: str, port: int) -> int | None:
    """Extract the LISTENING owner PID for a port from netstat -ano output."""
    for raw in (netstat_text or "").splitlines():
        line = raw.strip()
        if not line or "LISTENING" not in line.upper():
            continue
        match = _LISTENING_RE.search(line) or _LISTENING_RE_ALT.search(line)
        if not match:
            parts = [p for p in re.split(r"\s+", line) if p]
            if len(parts) >= 2 and parts[-2].upper() == "LISTENING":
                try:
                    if f":{port}" in line:
                        pid = int(parts[-1])
                        return pid if pid > 0 else None
                except ValueError:
                    continue
            continue
        if int(match.group("port")) == int(port):
            pid = int(match.group("pid"))
            return pid if pid > 0 else None
    return None


def _listening_pids_iphlpapi(port: int) -> list[int]:
    """Every LISTEN owner on a port. Empty when the table cannot be read."""
    import ctypes
    from ctypes import wintypes

    class _Row(ctypes.Structure):
        _fields_ = [
            ("dwState", wintypes.DWORD),
            ("dwLocalAddr", wintypes.DWORD),
            ("dwLocalPort", wintypes.DWORD),
            ("dwRemoteAddr", wintypes.DWORD),
            ("dwRemotePort", wintypes.DWORD),
            ("dwOwningPid", wintypes.DWORD),
        ]

    iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
    size = wintypes.DWORD(0)
    iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_ALL, 0)
    if size.value <= 0:
        return []
    buf = ctypes.create_string_buffer(size.value)
    status = iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_ALL, 0)
    if status != 0:
        return []
    count = struct.unpack_from("I", buf, 0)[0]
    offset = ctypes.sizeof(wintypes.DWORD)
    row_size = ctypes.sizeof(_Row)
    want = int(port)
    found: list[int] = []
    for index in range(count):
        row = _Row.from_buffer_copy(buf, offset + index * row_size)
        local_port = socket.ntohs(row.dwLocalPort & 0xFFFF)
        pid = int(row.dwOwningPid)
        if local_port != want or pid <= 0:
            continue
        if int(row.dwState) == _MIB_TCP_STATE_LISTEN and pid not in found:
            found.append(pid)
    return found


def port_owner_pid(port: int) -> int | None:
    pids = listening_pids(port)
    return pids[0] if pids else None


def listening_pids(port: int) -> list[int]:
    if sys.platform == "win32":
        try:
            return _listening_pids_iphlpapi(port)
        except (OSError, ValueError, AttributeError, BufferError):
            return []
    return []


def port_is_free(port: int) -> bool:
    return port_owner_pid(port) is None


def wait_port_released(port: int, timeout_sec: int = 15) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if port_is_free(port):
            return True
        time.sleep(1)
    return port_is_free(port)
