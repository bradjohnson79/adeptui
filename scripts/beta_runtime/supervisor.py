"""Adept UI V1.1 Beta runtime supervisor / watchdog."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

from beta_runtime.api_identity import perception_contract_ok, should_adopt_studio_api  # noqa: E402
from beta_runtime.envutil import RUNTIME_TAG, load_beta_env, repo_root, runtime_dirs  # noqa: E402

# Canonical supervisor states. READY maps to HEALTHY for operator diagnostics;
# FAILED with exhausted restart budget maps to CRASH_LOOP.
STATES = (
    "STARTING",
    "HEALTHY",
    "READY",  # alias retained for launchers; write_status prefers HEALTHY when green
    "SLOW",
    "DEGRADED",
    "OFFLINE",
    "RESTARTING",
    "CRASH_LOOP",
    "FAILED",
    "STOPPING",
    "STOPPED",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= int(resp.status) < 500
    except Exception:
        return False


def _http_json(url: str, timeout: float = 2.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}


def _repo_revision(root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            text=True,
            timeout=2,
            stderr=subprocess.DEVNULL,
        )
        return (out or "").strip()
    except Exception:
        return ""


def _port_pids(port: int) -> list[int]:
    if os.name != "nt":
        return []
    try:
        # PowerShell-free: netstat
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            errors="ignore",
        )
    except Exception:
        return []
    pids: list[int] = []
    needle = f":{port} "
    for line in out.splitlines():
        if "LISTENING" not in line.upper() or needle not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0:
            pids.append(pid)
    return sorted(set(pids))


def _win_process_rows() -> list[dict[str, object]]:
    if os.name != "nt":
        return []
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Select-Object ProcessId,ParentProcessId,CommandLine | "
                    "ConvertTo-Json -Compress"
                ),
            ],
            text=True,
            errors="ignore",
        )
    except Exception:
        return []
    text = (out or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _pid_files(dirs: dict[str, Path]) -> list[int]:
    pids: list[int] = []
    for path in dirs["pids"].glob("*.pid"):
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        if pid > 0:
            pids.append(pid)
    return sorted(set(pids))


def _live_beta_pids(root: Path, *, api_port: int, web_port: int) -> list[int]:
    normalized_root = str(root).replace("/", "\\").lower()
    rows = _win_process_rows()
    seeds: set[int] = set(_port_pids(api_port))
    seeds.update(_port_pids(web_port))
    parent_to_children: dict[int, set[int]] = {}
    for row in rows:
        try:
            pid = int(row.get("ProcessId") or 0)
            parent = int(row.get("ParentProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        parent_to_children.setdefault(parent, set()).add(pid)
        cmd = str(row.get("CommandLine") or "")
        normalized = cmd.replace("/", "\\").lower()
        if normalized_root and normalized_root not in normalized:
            continue
        if (
            "scripts\\beta_runtime\\supervisor.py" in normalized
            or "scripts\\beta_runtime\\web_server.py" in normalized
            or ("app.main:app" in normalized and f"--port {api_port}" in normalized)
        ):
            seeds.add(pid)
    live = set(seeds)
    stack = list(seeds)
    while stack:
        current = stack.pop()
        for child in parent_to_children.get(current, set()):
            if child in live:
                continue
            live.add(child)
            stack.append(child)
    return sorted(live)


def _candidate_beta_pids(root: Path, *, api_port: int, web_port: int, dirs: dict[str, Path]) -> list[int]:
    return sorted(set(_pid_files(dirs) + _live_beta_pids(root, api_port=api_port, web_port=web_port)))


def _orphan_worker_pids(port_pids: list[int]) -> list[int]:
    """Multiprocessing children that outlive a vanished listener PID."""
    seeds = {int(pid) for pid in port_pids if int(pid) > 0}
    if not seeds:
        return []
    extra: list[int] = []
    for row in _win_process_rows():
        try:
            pid = int(row.get("ProcessId") or 0)
            parent = int(row.get("ParentProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        cmd = str(row.get("CommandLine") or "")
        compact = cmd.replace(" ", "").lower()
        if parent in seeds:
            extra.append(pid)
            continue
        if any(f"parent_pid={seed}" in compact for seed in seeds):
            extra.append(pid)
    return sorted(set(extra))


def _recycle_api_listeners(api_pids: list[int]) -> None:
    targets = sorted(set(api_pids + _orphan_worker_pids(api_pids)))
    for pid in targets:
        _taskkill(pid)


def _taskkill(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def _clear_pid_files(dirs: dict[str, Path]) -> None:
    for path in dirs["pids"].glob("*.pid"):
        path.unlink(missing_ok=True)


class RotatingLog:
    def __init__(self, path: Path, max_bytes: int = 5_000_000, backups: int = 2):
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)

    def write(self, data: bytes | str) -> None:
        if isinstance(data, bytes):
            text = data.decode("utf-8", errors="replace")
        else:
            text = data
        self._fh.write(text)
        self._fh.flush()
        try:
            if self.path.stat().st_size > self.max_bytes:
                self._rotate()
        except OSError:
            pass

    def _rotate(self) -> None:
        self._fh.close()
        for i in range(self.backups, 0, -1):
            src = Path(f"{self.path}.{i - 1}") if i > 1 else self.path
            dst = Path(f"{self.path}.{i}")
            if src.exists():
                if dst.exists():
                    dst.unlink(missing_ok=True)
                src.rename(dst)
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


class ServiceProc:
    def __init__(self, name: str, popen: subprocess.Popen | None, log: RotatingLog):
        self.name = name
        self.popen = popen
        self.log = log
        self.restarts: deque[float] = deque()
        self.last_exit: int | None = None


class Supervisor:
    def __init__(self):
        load_beta_env()
        self.root = repo_root()
        self.dirs = runtime_dirs(self.root)
        self.state = "STARTING"
        self.intentional_stop = False
        self.services: dict[str, ServiceProc] = {}
        self.lock = threading.Lock()
        self.sup_log = RotatingLog(self.dirs["logs"] / "supervisor.log")
        self.api_restart_max = int(os.environ.get("ADEPT_BETA_API_RESTART_MAX", "3"))
        self.web_restart_max = int(os.environ.get("ADEPT_BETA_WEB_RESTART_MAX", "3"))
        self.restart_window = float(os.environ.get("ADEPT_BETA_RESTART_WINDOW_SEC", "600"))
        self.restart_backoff_sec = float(os.environ.get("ADEPT_BETA_RESTART_BACKOFF_SEC", "2"))
        self.restart_backoff_max_sec = float(os.environ.get("ADEPT_BETA_RESTART_BACKOFF_MAX_SEC", "30"))
        self.health_timeout = float(os.environ.get("ADEPT_BETA_HEALTH_TIMEOUT_SEC", "120"))
        self.health_slow_ms = float(os.environ.get("ADEPT_BETA_HEALTH_SLOW_MS", "5000"))
        self.min_free_gb = float(os.environ.get("ADEPT_BETA_MIN_FREE_GB", "10"))
        self.api_host = os.environ.get("STUDIO_API_HOST", "127.0.0.1")
        self.api_port = int(os.environ.get("STUDIO_API_PORT", "8758"))
        self.web_host = os.environ.get("STUDIO_WEB_HOST", "127.0.0.1")
        self.web_port = int(os.environ.get("STUDIO_WEB_PORT", "8760"))
        self.comfy_url = os.environ.get("STUDIO_COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
        self._api_health_fail_streak = 0
        self._last_api_health_ms: float | None = None

    def log(self, msg: str) -> None:
        line = f"[{_now()}] {msg}\n"
        self.sup_log.write(line)
        print(line, end="", flush=True)

    def _probe_api_health(self) -> tuple[bool, float | None]:
        url = f"http://{self.api_host}:{self.api_port}/api/health"
        started = time.perf_counter()
        ok = _http_ok(url, timeout=30.0)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return ok, elapsed_ms if ok else None

    def write_status(self) -> None:
        comfy_ok = _http_ok(f"{self.comfy_url}/system_stats", timeout=2.0)
        api_ok, api_ms = self._probe_api_health()
        web_ok = _http_ok(f"http://{self.web_host}:{self.web_port}/__beta_web_health", timeout=5.0)
        overall = self.state
        # Normalize READY → HEALTHY for the public status contract.
        if overall == "READY":
            overall = "HEALTHY"
        if overall in ("HEALTHY", "READY", "SLOW") and not comfy_ok:
            overall = "DEGRADED"
        if overall in ("HEALTHY", "READY") and api_ok and api_ms is not None and api_ms >= self.health_slow_ms:
            overall = "SLOW"
        if overall not in ("FAILED", "CRASH_LOOP", "STOPPING", "STOPPED", "RESTARTING", "STARTING"):
            if not api_ok and web_ok:
                overall = "OFFLINE"
            elif not api_ok and not web_ok:
                overall = "OFFLINE"
        payload = {
            "state": overall,
            "updatedAt": _now(),
            "runtimeTag": RUNTIME_TAG,
            "ports": {"web": self.web_port, "api": self.api_port, "comfy": 8188},
            "health": {
                "apiOk": api_ok,
                "apiLatencyMs": api_ms,
                "webOk": web_ok,
                "comfyOk": comfy_ok,
                "apiFailStreak": self._api_health_fail_streak,
            },
            "services": {
                "api": {
                    "ok": api_ok,
                    "pid": self._pid("api"),
                    "role": "studio-api + in-process queue worker",
                    "adopted": bool(getattr(self, "adopt_api", False)),
                },
                "worker": {
                    "ok": api_ok,
                    "pid": self._pid("api"),
                    "role": "in-process (JobQueue + Production Executive)",
                    "adopted": bool(getattr(self, "adopt_api", False)),
                },
                "web": {"ok": web_ok, "pid": self._pid("web"), "role": "production static+proxy"},
                "comfy": {
                    "ok": comfy_ok,
                    "pid": self._pid("comfy"),
                    "role": "external ComfyUI",
                    "url": self.comfy_url,
                },
            },
            "uiUrl": f"http://{self.web_host}:{self.web_port}/",
            "apiUrl": f"http://{self.api_host}:{self.api_port}/api/health",
            "logsDir": str(self.dirs["logs"]),
        }
        self.dirs["status"].write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _pid(self, name: str) -> int | None:
        svc = self.services.get(name)
        if svc and svc.popen and svc.popen.poll() is None:
            return svc.popen.pid
        pid_file = self.dirs["pids"] / f"{name}.pid"
        if pid_file.is_file():
            try:
                return int(pid_file.read_text(encoding="utf-8").strip())
            except ValueError:
                return None
        return None

    def _write_pid(self, name: str, pid: int) -> None:
        (self.dirs["pids"] / f"{name}.pid").write_text(str(pid), encoding="utf-8")

    def _clear_pid(self, name: str) -> None:
        p = self.dirs["pids"] / f"{name}.pid"
        if p.exists():
            p.unlink(missing_ok=True)

    def preflight(self) -> None:
        if not (self.root / "studio-api").is_dir() or not (self.root / "studio-web").is_dir():
            raise SystemExit(f"Repo root marker missing under {self.root}")
        py = self.dirs["venv_python"]
        if not py.is_file():
            raise SystemExit(f"Missing studio-api venv python: {py}. Run npm run install:all")
        data = self.dirs["data"]
        data.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(str(data))
        free_gb = usage.free / (1024**3)
        if free_gb < self.min_free_gb:
            raise SystemExit(
                f"Insufficient free disk on {data}: {free_gb:.1f} GB < {self.min_free_gb} GB"
            )
        self.adopt_api = False
        api_pids = _port_pids(self.api_port)
        if api_pids:
            healthy = _http_ok(f"http://{self.api_host}:{self.api_port}/api/health")
            current = self._health_revision_current() if healthy else False
            perception_ok = self._perception_contract_current() if healthy else False
            identity = (
                self._is_studio_api_identity()
                or self._is_our_listener(self.api_port)
                or self._adept_health_identity()
            )
            if should_adopt_studio_api(
                healthy=healthy,
                revision_current=current,
                perception_ok=perception_ok,
            ):
                self.adopt_api = True
                self.log(
                    f"preflight: adopting current Studio API already on :{self.api_port} (pids={api_pids})"
                )
            elif identity or (healthy and not (current and perception_ok)):
                self.log(
                    f"preflight: recycling Studio API on :{self.api_port} "
                    f"(healthy={healthy} current={current} perception={perception_ok} pids={api_pids})"
                )
                _recycle_api_listeners(api_pids)
                deadline = time.time() + 20
                while time.time() < deadline and _port_pids(self.api_port):
                    leftover_now = _port_pids(self.api_port)
                    _recycle_api_listeners(leftover_now)
                    time.sleep(0.5)
                leftover = _port_pids(self.api_port)
                if leftover:
                    raise SystemExit(
                        f"Port {self.api_port} still held by {leftover} after stale-API recycle."
                    )
                self.adopt_api = False
            else:
                raise SystemExit(
                    f"Port {self.api_port} (API) is occupied by unmanaged process(es) {api_pids} "
                    f"that do not answer current /api/health. Stop them; Beta does not pick random ports."
                )
        web_pids = _port_pids(self.web_port)
        if web_pids:
            if self._is_our_listener(self.web_port):
                self.log(f"preflight: :{self.web_port} already owned by Beta web â€” will restart")
            else:
                raise SystemExit(
                    f"Port {self.web_port} (Web) is occupied by unmanaged process(es) {web_pids}. "
                    f"Stop them; Beta does not pick random ports."
                )

    def _health_revision_current(self) -> bool:
        payload = _http_json(f"http://{self.api_host}:{self.api_port}/api/health")
        remote = str(payload.get("apiRevision") or "").strip()
        if not remote:
            return False
        local = _repo_revision(self.root)
        if not local:
            return True
        return remote == local

    def _perception_contract_current(self) -> bool:
        payload = _http_json(f"http://{self.api_host}:{self.api_port}/api/perception/capability")
        return perception_contract_ok(payload)

    def _adept_health_identity(self) -> bool:
        """HTTP HealthOut is enough to recycle when the listen PID is already gone."""
        payload = _http_json(f"http://{self.api_host}:{self.api_port}/api/health")
        if not payload.get("ok"):
            return False
        return bool(payload.get("apiRevision") or payload.get("routeContract") or payload.get("apiStartedAt"))

    def _is_studio_api_identity(self) -> bool:
        root = str(self.root).replace("/", "\\").lower()
        port = str(self.api_port)
        for pid in _port_pids(self.api_port):
            try:
                out = subprocess.check_output(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine",
                    ],
                    text=True,
                    errors="ignore",
                )
            except Exception:
                continue
            normalized = (out or "").replace("/", "\\").lower()
            if "comfyui" in normalized and "main.py" in normalized:
                continue
            if "app.main" in normalized or "start_api.py" in normalized:
                if (not root) or root in normalized or "uvicorn" in normalized:
                    return True
            if "uvicorn" in normalized and port in normalized:
                return True
        return False

    def _is_our_listener(self, port: int) -> bool:
        for pid in _port_pids(port):
            try:
                if os.name == "nt":
                    out = subprocess.check_output(
                        [
                            "powershell",
                            "-NoProfile",
                            "-Command",
                            f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine",
                        ],
                        text=True,
                        errors="ignore",
                    )
                    if RUNTIME_TAG in out or "beta_runtime" in out or "ADEPT_UI_BETA" in out:
                        return True
            except Exception:
                continue
        return False

    def ensure_web_build(self) -> None:
        dist_index = self.dirs["dist"] / "index.html"
        src_dir = self.root / "studio-web" / "src"
        need = not dist_index.is_file()
        if not need and src_dir.is_dir():
            try:
                newest_src = max((p.stat().st_mtime for p in src_dir.rglob("*") if p.is_file()), default=0)
                need = newest_src > dist_index.stat().st_mtime
            except OSError:
                need = False
        if not need:
            self.log("web build: dist up to date")
            return
        self.log("web build: running npm --prefix studio-web run build")
        r = subprocess.run(
            ["npm", "--prefix", str(self.root / "studio-web"), "run", "build"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            shell=(os.name == "nt"),
        )
        (self.dirs["logs"] / "launcher.log").open("a", encoding="utf-8").write(
            f"[{_now()}] npm build exit={r.returncode}\n{r.stdout}\n{r.stderr}\n"
        )
        if r.returncode != 0 or not dist_index.is_file():
            raise SystemExit(f"studio-web production build failed (exit {r.returncode})")

    def _child_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env[RUNTIME_TAG] = "1"
        env["STUDIO_DATA_DIR"] = str(self.dirs["data"])
        env["STUDIO_E2E"] = "0"
        env.pop("ADEPT_M29_FIXTURE_MODE", None)
        env.pop("ADEPT_M28_FIXTURE_MODE", None)
        return env

    def _pump(self, proc: subprocess.Popen, log: RotatingLog) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            # Stamp every service line so failures can be correlated with
            # supervisor/monitor timelines (uvicorn access logs have none).
            text = line if isinstance(line, str) else str(line)
            if text.strip() and not text.lstrip().startswith("["):
                text = f"[{_now()}] {text}"
            log.write(text)

    def start_api(self) -> None:
        log = RotatingLog(self.dirs["logs"] / "api.log")
        # Mirror worker log (in-process)
        RotatingLog(self.dirs["logs"] / "worker.log").write(
            f"[{_now()}] Worker runs in-process with Studio API (JobQueue + Production Executive).\n"
        )
        py = str(self.dirs["venv_python"])
        cmd = [
            py,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            self.api_host,
            "--port",
            str(self.api_port),
            "--workers",
            "1" if os.name == "nt" else "2",
        ]
        leftover = _port_pids(self.api_port)
        if leftover:
            self.log(f"clearing leftover API listeners before spawn: {leftover}")
            _recycle_api_listeners(leftover)
        self.log(f"starting API: {' '.join(cmd)}")
        popen = subprocess.Popen(
            cmd,
            cwd=str(self.dirs["api_dir"]),
            env=self._child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._pump, args=(popen, log), daemon=True).start()
        self.services["api"] = ServiceProc("api", popen, log)
        self._write_pid("api", popen.pid)
        # --workers 2 spawns child processes; popen.pid is the parent uvicorn.
        self._write_pid("supervisor", os.getpid())

    def start_web(self) -> None:
        log = RotatingLog(self.dirs["logs"] / "web.log")
        py = str(self.dirs["venv_python"])
        script = str(self.root / "scripts" / "beta_runtime" / "web_server.py")
        cmd = [py, script, "--host", self.web_host, "--port", str(self.web_port)]
        self.log(f"starting Web: {' '.join(cmd)}")
        popen = subprocess.Popen(
            cmd,
            cwd=str(self.root),
            env=self._child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._pump, args=(popen, log), daemon=True).start()
        self.services["web"] = ServiceProc("web", popen, log)
        self._write_pid("web", popen.pid)

    def ensure_comfy(self) -> None:
        log = RotatingLog(self.dirs["logs"] / "comfy.log")
        if _http_ok(f"{self.comfy_url}/system_stats"):
            log.write(f"[{_now()}] ComfyUI already healthy at {self.comfy_url}\n")
            self.log("ComfyUI healthy")
            return
        launch = (os.environ.get("ADEPT_COMFY_LAUNCH") or "").strip()
        if not launch:
            log.write(
                f"[{_now()}] ComfyUI not healthy; ADEPT_COMFY_LAUNCH unset â€” runtime DEGRADED\n"
            )
            self.log("ComfyUI unavailable (no ADEPT_COMFY_LAUNCH) â€” DEGRADED")
            return
        self.log(f"starting ComfyUI via ADEPT_COMFY_LAUNCH")
        # Windows: support quoted exe + args via shell
        popen = subprocess.Popen(
            launch,
            cwd=str(self.root),
            env=self._child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
        )
        threading.Thread(target=self._pump, args=(popen, log), daemon=True).start()
        self.services["comfy"] = ServiceProc("comfy", popen, log)
        self._write_pid("comfy", popen.pid)
        deadline = time.time() + min(self.health_timeout, 180)
        while time.time() < deadline:
            if _http_ok(f"{self.comfy_url}/system_stats"):
                self.log("ComfyUI became healthy")
                return
            time.sleep(2)
        self.log("ComfyUI still unhealthy after launch wait â€” DEGRADED")

    def wait_ready(self) -> bool:
        deadline = time.time() + self.health_timeout
        while time.time() < deadline:
            if self.intentional_stop:
                return False
            # /api/health probes Comfy; when Comfy is down the response can take >10s.
            # A 2s probe falsely marks API dead and leaves the runtime FAILED while UI is up.
            api_ok = _http_ok(f"http://{self.api_host}:{self.api_port}/api/health", timeout=30.0)
            web_ok = _http_ok(f"http://{self.web_host}:{self.web_port}/__beta_web_health", timeout=5.0)
            if api_ok and web_ok:
                return True
            time.sleep(1)
        return False

    def _can_restart(self, svc: ServiceProc, limit: int) -> bool:
        now = time.time()
        while svc.restarts and now - svc.restarts[0] > self.restart_window:
            svc.restarts.popleft()
        return len(svc.restarts) < limit

    def _restart(self, name: str) -> None:
        if self.intentional_stop or self.dirs["shutdown"].exists():
            return
        svc = self.services.get(name)
        if not svc:
            return
        limit = self.api_restart_max if name == "api" else self.web_restart_max
        if not self._can_restart(svc, limit):
            self.state = "CRASH_LOOP"
            self.log(f"{name} exceeded restart budget — CRASH_LOOP")
            self.write_status()
            return
        self.state = "RESTARTING"
        svc.restarts.append(time.time())
        attempt = len(svc.restarts)
        backoff = min(self.restart_backoff_max_sec, self.restart_backoff_sec * (2 ** max(0, attempt - 1)))
        self.log(
            f"restarting {name} (reason=unexpected_exit code={svc.last_exit} "
            f"attempt={attempt} backoffSec={backoff:.1f})"
        )
        self.write_status()
        if backoff > 0:
            time.sleep(backoff)
        try:
            if svc.popen and svc.popen.poll() is None:
                svc.popen.terminate()
                try:
                    svc.popen.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    svc.popen.kill()
        except Exception:
            pass
        # The venv python is a shim that re-executes the base interpreter, so
        # the pid we spawned is a parent of the real listener. If the shim is
        # gone but the child kept the port bound, the respawn would fail to
        # bind and crash-loop — clear any lingering listener first.
        port = self.api_port if name == "api" else self.web_port
        for listener in _port_pids(port):
            self.log(f"clearing lingering {name} listener pid={listener} on :{port} before restart")
            _taskkill(listener)
        if name == "api":
            self.start_api()
        elif name == "web":
            self.start_web()

    def watch_loop(self) -> None:
        tick = 0
        while not self.intentional_stop and not self.dirs["shutdown"].exists():
            tick += 1
            if tick % 30 == 0:
                # Keep pid files pointed at the real port listeners (venv shim
                # parenting can drift after restarts).
                self._reconcile_listener_pids()
            for name in ("api", "web"):
                if name == "api" and getattr(self, "adopt_api", False):
                    # Do not restart an adopted external API process
                    continue
                svc = self.services.get(name)
                if not svc or not svc.popen:
                    continue
                code = svc.popen.poll()
                if code is None:
                    continue
                svc.last_exit = code
                self.log(
                    f"{name} exited unexpectedly with code {code} "
                    f"(pid={svc.popen.pid})"
                )
                self._restart(name)
            comfy_ok = _http_ok(f"{self.comfy_url}/system_stats", timeout=2.0)
            api_ok, api_ms = self._probe_api_health()
            web_ok = _http_ok(f"http://{self.web_host}:{self.web_port}/__beta_web_health", timeout=5.0)
            self._last_api_health_ms = api_ms
            if api_ok:
                self._api_health_fail_streak = 0
            else:
                self._api_health_fail_streak += 1
            if self.state not in ("FAILED", "CRASH_LOOP", "STOPPING", "STOPPED"):
                if api_ok and web_ok:
                    if api_ms is not None and api_ms >= self.health_slow_ms:
                        self.state = "SLOW"
                    else:
                        self.state = "HEALTHY" if comfy_ok else "DEGRADED"
                elif self.state == "STARTING":
                    pass
                elif not api_ok:
                    self.state = "OFFLINE"
                    # Process alive but health dead for several ticks → restart (not adopted).
                    svc = self.services.get("api")
                    if (
                        not getattr(self, "adopt_api", False)
                        and svc
                        and svc.popen
                        and svc.popen.poll() is None
                        and self._api_health_fail_streak >= 5
                    ):
                        self.log(
                            f"api health fail streak={self._api_health_fail_streak} "
                            "while process alive — restarting hung API"
                        )
                        try:
                            svc.popen.terminate()
                            svc.popen.wait(timeout=8)
                        except Exception:
                            try:
                                svc.popen.kill()
                            except Exception:
                                pass
                        svc.last_exit = -9
                        self._restart("api")
                elif api_ok or web_ok:
                    self.state = "DEGRADED"
            self.write_status()
            time.sleep(2)

    def stop(self) -> None:
        self.intentional_stop = True
        self.state = "STOPPING"
        self.dirs["shutdown"].write_text(_now(), encoding="utf-8")
        self.write_status()
        self.log("intentional shutdown")
        # Stop web then API we spawned; never kill an adopted pre-existing API
        for name in ("web", "api"):
            if name == "api" and getattr(self, "adopt_api", False):
                self.log("leaving adopted Studio API running (not started by Beta supervisor)")
                self._clear_pid(name)
                continue
            svc = self.services.get(name)
            if not svc or not svc.popen:
                self._clear_pid(name)
                continue
            try:
                if svc.popen.poll() is None:
                    svc.popen.terminate()
                    try:
                        svc.popen.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        svc.popen.kill()
            except Exception as exc:
                self.log(f"stop {name}: {exc}")
            self._clear_pid(name)
        if "comfy" in self.services:
            svc = self.services["comfy"]
            if svc.popen and svc.popen.poll() is None:
                self.log("leaving ComfyUI running (external desktop app) unless we own it â€” sending terminate to launched child only")
                try:
                    svc.popen.terminate()
                except Exception:
                    pass
            self._clear_pid("comfy")
        self._clear_pid("worker")
        self._clear_pid("supervisor")
        self.state = "STOPPED"
        self.write_status()
        self.log("STOPPED")

    def run(self) -> int:
        (self.dirs["pids"] / "supervisor.pid").write_text(str(os.getpid()), encoding="utf-8")
        if self.dirs["shutdown"].exists():
            self.dirs["shutdown"].unlink(missing_ok=True)
        self.preflight()
        self.ensure_web_build()
        self.state = "STARTING"
        self.write_status()

        # If previous Beta API/web still listening, stop our tagged ones first via pids
        self._stop_stale_owned()

        self.ensure_comfy()
        if getattr(self, "adopt_api", False):
            self.log("skipping API spawn â€” using adopted Studio API on configured port")
            RotatingLog(self.dirs["logs"] / "api.log").write(
                f"[{_now()}] Adopted existing Studio API on :{self.api_port} (not spawned by supervisor).\n"
            )
            RotatingLog(self.dirs["logs"] / "worker.log").write(
                f"[{_now()}] Worker in-process inside adopted API.\n"
            )
            pids = _port_pids(self.api_port)
            if pids:
                self._write_pid("api", pids[0])
                self._write_pid("worker", pids[0])
        else:
            self.start_api()
        self.start_web()
        ok = self.wait_ready()
        if not ok:
            self.state = "FAILED"
            self.write_status()
            self.log("FAILED â€” health timeout")
            return 1
        comfy_ok = _http_ok(f"{self.comfy_url}/system_stats")
        self.state = "HEALTHY" if comfy_ok else "DEGRADED"
        self._reconcile_listener_pids()
        self.write_status()
        self.log(f"{self.state} — UI http://{self.web_host}:{self.web_port}/")

        def _sig(_s, _f):
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)
        self.watch_loop()
        self.stop()
        return 0

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            try:
                out = subprocess.check_output(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    text=True,
                    errors="ignore",
                )
                return str(pid) in out and "No tasks" not in out
            except Exception:
                return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _stop_stale_owned(self) -> None:
        for name in ("api", "web"):
            if name == "api" and getattr(self, "adopt_api", False):
                continue  # adopted pre-existing API is intentional — never kill it
            pid_file = self.dirs["pids"] / f"{name}.pid"
            if not pid_file.is_file():
                continue
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
            except ValueError:
                pid_file.unlink(missing_ok=True)
                continue
            if not self._pid_alive(pid):
                pid_file.unlink(missing_ok=True)
                continue
            # A live pid file at startup means a previous supervisor died
            # without cleanup. Kill the stale tree (venv shim + orphaned real
            # listener) so this instance does not hit port-bind crash loops.
            self.log(f"stopping stale owned {name} pid={pid} from previous supervisor")
            _taskkill(pid)
            port = self.api_port if name == "api" else self.web_port
            for listener in _port_pids(port):
                if listener != pid:
                    self.log(f"stopping orphaned {name} listener pid={listener} on :{port}")
                    _taskkill(listener)
            pid_file.unlink(missing_ok=True)

    def _reconcile_listener_pids(self) -> None:
        # The venv python shim re-executes the base interpreter: the spawned
        # pid is a parent of the process that actually binds the port. Point
        # pid files at the real listeners so status/stop/observers track the
        # process that matters.
        if not getattr(self, "adopt_api", False):
            api_listeners = _port_pids(self.api_port)
            if api_listeners:
                self._write_pid("api", api_listeners[0])
                self._write_pid("worker", api_listeners[0])
        web_listeners = _port_pids(self.web_port)
        if web_listeners:
            self._write_pid("web", web_listeners[0])


def main() -> int:
    parser = argparse.ArgumentParser(description="Adept UI Beta supervisor")
    parser.add_argument("action", choices=["run", "stop", "status"], default="run", nargs="?")
    args = parser.parse_args()
    load_beta_env()
    dirs = runtime_dirs()
    if args.action == "status":
        if dirs["status"].is_file():
            print(dirs["status"].read_text(encoding="utf-8"))
            return 0
        print("{}")
        return 1
    if args.action == "stop":
        dirs["shutdown"].write_text(_now(), encoding="utf-8")
        api_port = int(os.environ.get("STUDIO_API_PORT", "8758"))
        web_port = int(os.environ.get("STUDIO_WEB_PORT", "8760"))
        root = repo_root()
        graceful_deadline = time.time() + 15
        while time.time() < graceful_deadline:
            if not _live_beta_pids(root, api_port=api_port, web_port=web_port):
                break
            time.sleep(1.5)
        remaining = _candidate_beta_pids(root, api_port=api_port, web_port=web_port, dirs=dirs)
        for pid in sorted(remaining, reverse=True):
            _taskkill(pid)
        _recycle_api_listeners(_port_pids(api_port))
        forced_deadline = time.time() + 20
        while time.time() < forced_deadline:
            remaining = _live_beta_pids(root, api_port=api_port, web_port=web_port)
            leftover = _port_pids(api_port)
            if not remaining and not leftover:
                break
            for pid in sorted(set(remaining + leftover + _orphan_worker_pids(leftover)), reverse=True):
                _taskkill(pid)
            time.sleep(1.5)
        _clear_pid_files(dirs)
        status = {
            "state": "STOPPED",
            "updatedAt": _now(),
            "runtimeTag": RUNTIME_TAG,
        }
        dirs["status"].write_text(json.dumps(status, indent=2), encoding="utf-8")
        print("STOPPED")
        return 0 if not _live_beta_pids(root, api_port=api_port, web_port=web_port) else 1

    return Supervisor().run()


if __name__ == "__main__":
    raise SystemExit(main())

