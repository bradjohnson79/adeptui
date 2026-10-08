"""Long-lived Adept Background Services manager.

Owns Studio API :8758 and headless Comfy :8188 as independent children.
Does not own MiniMax :8192.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

from .canonical_config import ConfigurationError, load_runtime_config, validate_runtime_config
from .control_plane import ControlPlaneError, start_control_plane, stop_control_plane, ControlPlane
from .control_token import ensure_token
from .env import load_beta_env
from .headless_comfy.service import request_start, request_stop
from .paths import discover_paths
from .qwen_residency import request_qwen
from .service_status import collect_runtime_view
from .state import SupervisorState
from .studio_api_child import (
    child_view as studio_api_view,
    restart_studio_api_child,
    start_studio_api_child,
    stop_studio_api_child,
)
from .services import start_ollama, stop_owned_service
from .watch import watch_once


def _payload(ok: bool, **extra: Any) -> dict[str, Any]:
    body = collect_runtime_view()
    body["ok"] = ok
    body.update(extra)
    return body


def _comfy_result_payload(result: Any) -> dict[str, Any]:
    return {
        "ok": bool(result.ok),
        "message": result.message,
        "pid": result.pid,
        "ownership": result.ownership,
    }


def serve_forever(*, watch_interval: int = 15) -> int:
    # Windows headless robustness: Node's `spawn(detached:true)` gives this supervisor
    # its own (hidden) console, which receives stray CTRL_C/CTRL_BREAK events from the
    # spawning console and kills it with STATUS_CONTROL_C_EXIT (0xC000013A) during boot.
    # Detach from any console so no console control events can reach this long-lived
    # headless lifecycle owner (headless/no-console-dependency principle, cf. ComfyUI
    # Protection Law item 6). This is a no-op if there is no console attached.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.FreeConsole()
        except OSError:
            pass

    try:
        cfg = load_runtime_config()
        errors = validate_runtime_config(cfg)
        if errors:
            print("CONFIGURATION ERROR: " + "; ".join(errors), file=sys.stderr)
            return 2
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    ensure_token()
    paths = discover_paths(Path(cfg.repoRoot) if cfg.repoRoot else None)
    if cfg.repoRoot:
        load_beta_env(paths.repo_root)
    state = SupervisorState.from_env(paths.repo_root)
    state.write_pid("runtime_service", os.getpid(), "runtime_supervisor.serve", owned=True)
    api_enabled = bool(cfg.studioApi.enabled)

    def on_status(_body: dict[str, Any]) -> dict[str, Any]:
        return _payload(True, servicePid=os.getpid(), managerPid=os.getpid(), studioApi=studio_api_view(state))

    def on_start_api(_body: dict[str, Any]) -> dict[str, Any]:
        result = start_studio_api_child(paths, state, spawn=True, allow_migrate=True)
        return _payload(
            result.ok,
            message=result.message,
            ownership=result.ownership,
            studioApi=_comfy_result_payload(result),
            studioApiPid=result.pid,
        )

    def on_stop_api(_body: dict[str, Any]) -> dict[str, Any]:
        result = stop_studio_api_child(state, force=False, allow_migrate=False)
        return _payload(result.ok, message=result.message, ownership=result.ownership, studioApi=_comfy_result_payload(result))

    def on_restart_api(_body: dict[str, Any]) -> dict[str, Any]:
        recycled = restart_studio_api_child(paths, state, spawn=True, allow_migrate=True)
        return _payload(
            bool(recycled.get("ok")),
            message=str(recycled.get("message") or "restart-api"),
            oldPid=recycled.get("oldPid"),
            newPid=recycled.get("newPid"),
            comfyPid=recycled.get("comfyPid"),
            comfyPidUnchanged=recycled.get("comfyPidUnchanged"),
            studioApiPid=recycled.get("newPid"),
        )

    def on_start_comfy(_body: dict[str, Any]) -> dict[str, Any]:
        result = request_start(paths, state, spawn=True)
        return _payload(result.ok, message=result.message, ownership=result.ownership, comfy=_comfy_result_payload(result))

    def on_stop_comfy(_body: dict[str, Any]) -> dict[str, Any]:
        result = request_stop(state, force=False)
        return _payload(result.ok, message=result.message, ownership=result.ownership, comfy=_comfy_result_payload(result))

    def on_restart_comfy(_body: dict[str, Any]) -> dict[str, Any]:
        api_before = studio_api_view(state).get("pid")
        stopped = request_stop(state, force=False)
        if not stopped.ok and "queue_running" in (stopped.message or ""):
            return _payload(False, message=stopped.message, studioApiPid=api_before)
        started = request_start(paths, state, spawn=True)
        api_after = studio_api_view(state).get("pid")
        return _payload(
            started.ok,
            message=started.message,
            ownership=started.ownership,
            comfy=_comfy_result_payload(started),
            studioApiPid=api_after,
            studioApiPidUnchanged=api_before == api_after,
        )

    def on_start_route_a(_body: dict[str, Any]) -> dict[str, Any]:
        # Unified Runtime Fabric: Route A (MiniMax H3 :8192) is ON DEMAND. Started when
        # an H3 generation is requested, with GPU handoff from canonical Comfy :8188 (/free,
        # never kill). This makes Route A first-class in the supervisor instead of
        # operator-only PowerShell.
        from .services import start_route_a_on_demand

        result = start_route_a_on_demand(paths, state, spawn=True)
        return _payload(result.ok, message=result.message, ownership=result.ownership, routeA={"pid": result.pid, "ok": result.ok})

    def on_stop_route_a(_body: dict[str, Any]) -> dict[str, Any]:
        from .services import stop_route_a

        result = stop_route_a(state, force=False)
        return _payload(result.ok, message=result.message, ownership=result.ownership, routeA={"pid": result.pid, "ok": result.ok})

    def on_restart_route_a(_body: dict[str, Any]) -> dict[str, Any]:
        from .services import stop_route_a, start_route_a_on_demand

        stopped = stop_route_a(state, force=False)
        if not stopped.ok:
            return _payload(False, message=stopped.message, routeA={"pid": stopped.pid, "ok": False})
        started = start_route_a_on_demand(paths, state, spawn=True)
        return _payload(started.ok, message=started.message, ownership=started.ownership, routeA={"pid": started.pid, "ok": started.ok})

    def on_start_ollama(_body: dict[str, Any]) -> dict[str, Any]:
        result = start_ollama(paths, state, start_if_down=True, spawn=True)
        return _payload(
            result.ok,
            message=result.message,
            ownership=result.ownership,
            ollama=_comfy_result_payload(result),
            logicalId="runtime.local_llm",
        )

    def on_stop_ollama(_body: dict[str, Any]) -> dict[str, Any]:
        result = stop_owned_service(state, "ollama", force=False, allow_external=False)
        return _payload(
            result.ok,
            message=result.message,
            ownership=result.ownership,
            ollama=_comfy_result_payload(result),
            logicalId="runtime.local_llm",
        )

    def on_restart_ollama(_body: dict[str, Any]) -> dict[str, Any]:
        stopped = stop_owned_service(state, "ollama", force=False, allow_external=False)
        if not stopped.ok:
            return _payload(False, message=stopped.message, ollama=_comfy_result_payload(stopped))
        started = start_ollama(paths, state, start_if_down=True, spawn=True)
        return _payload(
            started.ok,
            message=started.message,
            ownership=started.ownership,
            ollama=_comfy_result_payload(started),
            logicalId="runtime.local_llm",
        )

    def on_start(_body: dict[str, Any]) -> dict[str, Any]:
        api = (
            start_studio_api_child(paths, state, spawn=True, allow_migrate=True)
            if api_enabled
            else type("R", (), {"ok": True, "message": "Studio API disabled", "pid": None, "ownership": "external"})()
        )
        comfy = request_start(paths, state, spawn=True)
        ollama = start_ollama(paths, state, start_if_down=True, spawn=True)
        return _payload(
            bool(api.ok and comfy.ok),
            message=f"api={api.message}; comfy={comfy.message}; local_ai={ollama.message}",
            ollama=_comfy_result_payload(ollama),
            studioApi=_comfy_result_payload(api),
            comfy=_comfy_result_payload(comfy),
            studioApiPid=api.pid,
        )

    def on_stop(_body: dict[str, Any]) -> dict[str, Any]:
        api = stop_studio_api_child(state, force=False, allow_migrate=False) if api_enabled else type(
            "R", (), {"ok": True, "message": "Studio API disabled", "pid": None, "ownership": "external"}
        )()
        comfy = request_stop(state, force=False)
        ollama = stop_owned_service(state, "ollama", force=False, allow_external=False)
        return _payload(
            bool(api.ok and comfy.ok),
            message=f"api={api.message}; comfy={comfy.message}; local_ai={ollama.message}",
            studioApi=_comfy_result_payload(api),
            comfy=_comfy_result_payload(comfy),
            ollama=_comfy_result_payload(ollama),
        )

    def on_restart(_body: dict[str, Any]) -> dict[str, Any]:
        # /restart stays Comfy-only. API recycle is /restart-api.
        return on_restart_comfy(_body)

    def on_request_qwen(_body: dict[str, Any]) -> dict[str, Any]:
        result = dict(request_qwen())
        ok = bool(result.pop("ok", False))
        return _payload(ok, **result)

    def on_repair(_body: dict[str, Any]) -> dict[str, Any]:
        from .bootstrap import repair_services

        report = repair_services(repo_root=paths.repo_root)
        # EnableReport.to_dict() already carries "ok" and "message". Merge it over the
        # runtime view directly instead of _payload(ok, **to_dict()) which collides.
        body = collect_runtime_view()
        body.update(report.to_dict())
        body["ok"] = report.ok
        return body

    plane = ControlPlane(
        host="127.0.0.1",
        port=int(cfg.controlPort),
        on_status=on_status,
        on_start=on_start,
        on_stop=on_stop,
        on_restart=on_restart,
        on_request_qwen=on_request_qwen,
        on_start_api=on_start_api,
        on_stop_api=on_stop_api,
        on_restart_api=on_restart_api,
        on_start_comfy=on_start_comfy,
        on_stop_comfy=on_stop_comfy,
        on_restart_comfy=on_restart_comfy,
        on_start_route_a=on_start_route_a,
        on_stop_route_a=on_stop_route_a,
        on_restart_route_a=on_restart_route_a,
        on_start_ollama=on_start_ollama,
        on_stop_ollama=on_stop_ollama,
        on_restart_ollama=on_restart_ollama,
        on_repair=on_repair,
    )
    try:
        start_control_plane(plane)
    except (ControlPlaneError, OSError) as exc:
        print(f"CONFIGURATION ERROR: control plane failed: {exc}", file=sys.stderr)
        return 2

    # Install signal handlers BEFORE starting any service. request_start (Comfy
    # cold-start) can block for up to 180s; without handlers installed first, a
    # stray console CTRL_C/CTRL_BREAK during that window killed this headless
    # supervisor with STATUS_CONTROL_C_EXIT (0xC000013A), breaking auto boot.
    stop = {"flag": False}

    def _stop(_signum=None, _frame=None):
        stop["flag"] = True

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _stop)
    # Windows: stray CTRL_BREAK events from the spawning console (Node/Vite/Electron,
    # Cursor shells) must not kill this long-lived headless supervisor. The supervisor
    # is detached/headless by design and must not die from console control events
    # (headless/no-console-dependency principle, cf. ComfyUI Protection Law item 6).
    # Ignore SIGBREAK so the canonical lifecycle owner survives stray console
    # signals; clean stop is via the control plane / SIGTERM.
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)

    api_started = None
    if api_enabled:
        from .ensure_studio_api import ensure_studio_api_running

        # Single ensure path after control plane binds — Background Services brings :8758 without Cursor.
        ensured = ensure_studio_api_running(allow_start_task=False, allow_migrate=True)
        api_started = type(
            "R",
            (),
            {
                "ok": bool(ensured.get("ok")),
                "message": str(ensured.get("message") or ensured.get("code") or "ensure-api"),
                "pid": ensured.get("pid"),
                "ownership": "owned" if ensured.get("ok") else "external",
            },
        )()
    try:
        comfy_started = request_start(paths, state, spawn=True)
    except Exception as exc:  # noqa: BLE001 — missing Comfy must not take the manager down
        comfy_started = type(
            "R",
            (),
            {"ok": False, "message": f"Comfy setup required: {exc}", "pid": None, "ownership": "external"},
        )()
    # Local AI Runtime is part of the unified fabric. Failure must not abort serve.
    try:
        ollama_started = start_ollama(paths, state, start_if_down=True, spawn=True)
    except Exception as exc:  # noqa: BLE001 — boot continues without Local AI
        ollama_started = type(
            "R",
            (),
            {"ok": False, "message": f"Local AI Runtime start failed: {exc}", "pid": None, "ownership": "external"},
        )()
    try:
        state.write_snapshot(
            {
                "action": "serve",
                "servicePid": os.getpid(),
                "studio_api": {
                    "ok": bool(api_started.ok) if api_started else False,
                    "message": api_started.message if api_started else "disabled",
                    "pid": api_started.pid if api_started else None,
                },
                "comfy": {"ok": comfy_started.ok, "message": comfy_started.message, "pid": comfy_started.pid},
                "ollama": {
                    "ok": bool(ollama_started.ok),
                    "message": ollama_started.message,
                    "pid": ollama_started.pid,
                    "ownership": getattr(ollama_started, "ownership", "external"),
                    "logicalId": "runtime.local_llm",
                },
            }
        )
    except Exception as exc:  # noqa: BLE001 — the control plane is already up
        print(f"serve snapshot failed: {exc}", file=sys.stderr)

    watched = ("studio_api", "comfyui", "ollama") if api_enabled else ("comfyui", "ollama")
    busy = {name: 0 for name in watched}
    while not stop["flag"]:
        try:
            notes = watch_once(state, paths, busy, services=watched)
        except Exception as exc:  # noqa: BLE001 — a service failure must not close the control plane
            print(f"serve watch failed: {exc}", file=sys.stderr)
            notes = []
        if notes:
            try:
                state.write_snapshot({"action": "serve-watch", "notes": notes, "servicePid": os.getpid()})
            except Exception as exc:  # noqa: BLE001
                print(f"serve watch snapshot failed: {exc}", file=sys.stderr)
        deadline = time.time() + max(3, int(watch_interval))
        while time.time() < deadline and not stop["flag"]:
            time.sleep(0.5)

    stop_control_plane(plane)
    return 0
