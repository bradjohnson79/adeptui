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
    started_at: str = ""
    last_exit: str = ""
    restart_count: int = 0
    last_restart_reason: str = ""
    executable: str = ""
    cwd: str = ""
    log_path: str = ""
    health: str = ""
    state: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "cmd": self.cmd,
            "owned": self.owned,
            "written_at": self.written_at,
            "started_at": self.started_at,
            "last_exit": self.last_exit,
            "restart_count": self.restart_count,
            "last_restart_reason": self.last_restart_reason,
            "executable": self.executable,
            "cwd": self.cwd,
            "log_path": self.log_path,
            "health": self.health,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PidRecord":
        return cls(
            pid=int(data.get("pid") or 0),
            cmd=str(data.get("cmd") or ""),
            owned=bool(data.get("owned")),
            written_at=str(data.get("written_at") or ""),
            started_at=str(data.get("started_at") or data.get("written_at") or ""),
            last_exit=str(data.get("last_exit") or ""),
            restart_count=int(data.get("restart_count") or 0),
            last_restart_reason=str(data.get("last_restart_reason") or ""),
            executable=str(data.get("executable") or ""),
            cwd=str(data.get("cwd") or ""),
            log_path=str(data.get("log_path") or ""),
            health=str(data.get("health") or ""),
            state=str(data.get("state") or ""),
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
        try:
            from .canonical_config import default_state_dir, try_load_runtime_config

            cfg = try_load_runtime_config()
            if cfg and cfg.stateDir:
                return cls(Path(cfg.stateDir))
            return cls(default_state_dir())
        except Exception:
            return cls(repo_root / ".runtime" / "supervisor")

    def ensure(self) -> None:
        self.pid_dir.mkdir(parents=True, exist_ok=True)

    def pid_path(self, service: str) -> Path:
        return self.pid_dir / f"{service}.pid"

    def write_pid(self, service: str, pid: int, cmd: str, owned: bool, **extra: Any) -> PidRecord:
        now = datetime.now(timezone.utc).isoformat()
        rec = PidRecord(
            pid=int(pid),
            cmd=cmd,
            owned=bool(owned),
            written_at=now,
            started_at=str(extra.get("started_at") or now),
            last_exit=str(extra.get("last_exit") or ""),
            restart_count=int(extra.get("restart_count") or 0),
            last_restart_reason=str(extra.get("last_restart_reason") or ""),
            executable=str(extra.get("executable") or ""),
            cwd=str(extra.get("cwd") or ""),
            log_path=str(extra.get("log_path") or ""),
            health=str(extra.get("health") or ""),
            state=str(extra.get("state") or ""),
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
