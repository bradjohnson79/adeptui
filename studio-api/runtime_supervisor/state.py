"""Single supervisor state store: PIDs, exclusive lock, restart history."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import MAX_RESTARTS, STORM_WINDOW_SEC
from .process import process_alive


@dataclass
class PidRecord:
    pid: int
    cmd: str
    owned: bool
    written_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "cmd": self.cmd,
            "owned": self.owned,
            "written_at": self.written_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PidRecord":
        return cls(
            pid=int(data.get("pid") or 0),
            cmd=str(data.get("cmd") or ""),
            owned=bool(data.get("owned")),
            written_at=str(data.get("written_at") or ""),
        )


class SupervisorState:
    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.pid_dir = self.state_dir / "pids"
        self.lock_path = self.state_dir / "restart.lock"
        self.history_path = self.state_dir / "restart_history.json"
        self.state_path = self.state_dir / "state.json"
        self.ensure()

    @classmethod
    def from_env(cls, repo_root: Path) -> "SupervisorState":
        override = os.environ.get("ADEPT_SUPERVISOR_STATE_DIR", "").strip()
        if override:
            return cls(Path(override))
        return cls(repo_root / ".runtime" / "supervisor")

    def ensure(self) -> None:
        self.pid_dir.mkdir(parents=True, exist_ok=True)

    def pid_path(self, service: str) -> Path:
        return self.pid_dir / f"{service}.pid"

    def write_pid(self, service: str, pid: int, cmd: str, owned: bool) -> PidRecord:
        rec = PidRecord(
            pid=int(pid),
            cmd=cmd,
            owned=bool(owned),
            written_at=datetime.now(timezone.utc).isoformat(),
        )
        self.pid_path(service).write_text(json.dumps(rec.to_dict(), indent=2), encoding="utf-8")
        return rec

    def read_pid(self, service: str) -> PidRecord | None:
        path = self.pid_path(service)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return PidRecord.from_dict(data)
            # Legacy bare integer PID files from Runtime Manager
            return PidRecord(pid=int(data), cmd="", owned=True, written_at="")
        except (OSError, ValueError, json.JSONDecodeError):
            try:
                raw = path.read_text(encoding="utf-8").strip()
                return PidRecord(pid=int(raw), cmd="", owned=True, written_at="")
            except (OSError, ValueError):
                return None

    def remove_pid(self, service: str) -> None:
        path = self.pid_path(service)
        if path.exists():
            path.unlink()

    def pid_alive(self, service: str) -> bool:
        rec = self.read_pid(service)
        return bool(rec and process_alive(rec.pid))

    def write_snapshot(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def read_history(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            parsed = json.loads(self.history_path.read_text(encoding="utf-8"))
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
            return []
        except (OSError, json.JSONDecodeError):
            return []

    def write_history(self, history: list[dict[str, Any]]) -> None:
        self.history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

    def add_restart_event(self, service: str) -> list[dict[str, Any]]:
        now = int(time.time())
        history = [e for e in self.read_history() if int(e.get("timestamp") or 0) >= now - 3600]
        history.append({"service": service, "timestamp": now})
        self.write_history(history)
        return history

    def storm_active(
        self,
        service: str,
        max_restarts: int = MAX_RESTARTS,
        window_sec: int = STORM_WINDOW_SEC,
    ) -> bool:
        now = int(time.time())
        cutoff = now - window_sec
        recent = [
            e
            for e in self.read_history()
            if e.get("service") == service and int(e.get("timestamp") or 0) >= cutoff
        ]
        return len(recent) >= max_restarts

    def try_lock(self, service: str, holder_pid: int | None = None) -> bool:
        holder = int(holder_pid or os.getpid())
        if self.lock_path.exists():
            try:
                data = json.loads(self.lock_path.read_text(encoding="utf-8"))
                existing = int((data or {}).get("holderPid") or 0)
                if existing and process_alive(existing):
                    return False
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        self.lock_path.write_text(
            json.dumps(
                {
                    "service": service,
                    "holderPid": holder,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            encoding="utf-8",
        )
        return True

    def lock_held(self) -> bool:
        if not self.lock_path.exists():
            return False
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
            existing = int((data or {}).get("holderPid") or 0)
            return bool(existing and process_alive(existing))
        except (OSError, ValueError, json.JSONDecodeError):
            return False

    def clear_lock(self) -> None:
        if self.lock_path.exists():
            self.lock_path.unlink()
