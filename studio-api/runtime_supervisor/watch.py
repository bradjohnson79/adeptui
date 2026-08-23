"""Single watchdog. Storm protection + Comfy busy-guard + exclusive lock."""

from __future__ import annotations

import time
from pathlib import Path

from .constants import BASE_BACKOFF_SEC, BUSY_ALIVE_CYCLES, MAX_BACKOFF_SEC, SERVICES
from .env import load_beta_env
from .health import comfy_healthy, comfy_queue_running, ollama_healthy, studio_api_healthy, tunnel_process_healthy
from .identity import classify_api_port
from .paths import discover_paths
from .process import process_alive
from .services import start_comfy, start_studio_api, start_tunnel
from .state import SupervisorState


def _service_healthy(service: str, state: SupervisorState) -> bool:
    if service == "studio_api":
        return studio_api_healthy()
    if service == "comfyui":
        return comfy_healthy()
    if service == "cloudflared":
        return tunnel_process_healthy(state)
    if service == "ollama":
        rec = state.read_pid("ollama")
        if rec and rec.owned:
            return ollama_healthy()
        return True
    return True


def _should_skip_comfy(state: SupervisorState) -> str | None:
    rec = state.read_pid("comfyui")
    if rec and process_alive(rec.pid) and comfy_queue_running() > 0:
        return "queue_running — not restarting Comfy"
    return None


def watch_once(state: SupervisorState, paths, busy: dict[str, int]) -> list[str]:
    notes: list[str] = []
    for service in SERVICES:
        if _service_healthy(service, state):
            busy[service] = 0
            continue
        rec = state.read_pid(service)
        if rec and process_alive(rec.pid):
            busy[service] = busy.get(service, 0) + 1
            if busy[service] < BUSY_ALIVE_CYCLES:
                notes.append(f"{service}: process alive, health miss {busy[service]}/{BUSY_ALIVE_CYCLES}")
                continue
        if service == "comfyui":
            skip = _should_skip_comfy(state)
            if skip:
                notes.append(f"comfyui: {skip}")
                continue
        if service == "ollama":
            rec = state.read_pid("ollama")
            if not rec or not rec.owned:
                notes.append("ollama: EXTERNAL — watchdog will not start or kill")
                continue
        if state.storm_active(service):
            notes.append(f"{service}: storm protection active")
            continue
        if not state.try_lock(service):
            notes.append(f"{service}: lock held — skip")
            continue
        try:
            state.add_restart_event(service)
            if service == "studio_api":
                st = classify_api_port()
                if st.state in ("phantom", "unrelated"):
                    notes.append(f"studio_api: FAIL CLOSED ({st.state} PID {st.pid})")
                    continue
                result = start_studio_api(paths, state)
            elif service == "comfyui":
                result = start_comfy(paths, state)
            elif service == "cloudflared":
                result = start_tunnel(paths, state)
            else:
                notes.append(f"{service}: no watchdog start")
                continue
            notes.append(f"{service}: restart {'ok' if result.ok else 'fail'} — {result.message}")
        finally:
            state.clear_lock()
        failures = busy.get(service, 0)
        backoff = min(BASE_BACKOFF_SEC * (2 ** max(failures, 0)), MAX_BACKOFF_SEC)
        time.sleep(backoff)
    return notes


def watch_loop(interval_sec: int = 15, *, once: bool = False, repo_root: Path | None = None) -> None:
    paths = discover_paths(repo_root)
    load_beta_env(paths.repo_root)
    state = SupervisorState.from_env(paths.repo_root)
    busy = {s: 0 for s in SERVICES}
    while True:
        notes = watch_once(state, paths, busy)
        if notes:
            state.write_snapshot({"action": "watch", "notes": notes})
        if once:
            return
        time.sleep(interval_sec)
