"""Port owner detection via netstat. No PowerShell."""

from __future__ import annotations

import re
import subprocess
import time

_LISTENING_RE = re.compile(r":(?P<port>\d+)\s+\S+\s+LISTENING\s+(?P<pid>\d+)\s*$", re.IGNORECASE)
_LISTENING_RE_ALT = re.compile(r":(?P<port>\d+).+LISTENING\s+(?P<pid>\d+)\s*$", re.IGNORECASE)


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


def port_owner_pid(port: int) -> int | None:
    try:
        completed = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_netstat_owner(completed.stdout or "", port)


def port_is_free(port: int) -> bool:
    return port_owner_pid(port) is None


def wait_port_released(port: int, timeout_sec: int = 15) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if port_is_free(port):
            return True
        time.sleep(1)
    return port_is_free(port)
