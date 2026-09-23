"""CLI: start | stop | restart | status | watch | serve | ensure-api | install-task | uninstall-task | enable."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bootstrap import enable_recommended
from .env import load_beta_env
from .paths import discover_paths, repo_root_from
from .service_status import collect_runtime_view
from .services import MANAGER_UNAVAILABLE, LifecycleError, collect_status, restart_all, start_all, stop_all
from .windows_task import query_task, register_task, unregister_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runtime_supervisor", description="Adept Runtime Service")
    parser.add_argument(
        "action",
        choices=(
            "start",
            "stop",
            "restart",
            "status",
            "watch",
            "serve",
            "ensure-api",
            "install-task",
            "uninstall-task",
            "enable",
        ),
    )
    parser.add_argument("--start-ollama", action="store_true", help="Start Ollama only if it is down (default: adopt/check)")
    parser.add_argument("--no-cloudflare", action="store_true")
    parser.add_argument("--force", action="store_true", help="Stop adopted services (never kills EXTERNAL Ollama)")
    parser.add_argument("--once", action="store_true", help="Watch a single cycle")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-windows-start", action="store_true", help="enable without registering the logon task")
    args = parser.parse_args(argv)

    root = repo_root_from()
    load_beta_env(root)
    discover_paths(root)

    try:

        if args.action == "ensure-api":
            from .ensure_studio_api import ensure_studio_api_running

            result = ensure_studio_api_running()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(
                    f"ensure-api: {'OK' if result.get('ok') else 'FAIL'} "
                    f"action={result.get('action')} code={result.get('code')} "
                    f"pid={result.get('pid')} health={result.get('health')} "
                    f"— {result.get('message')}"
                )
            return 0 if result.get("ok") else 1
        if args.action == "serve":
            from .serve import serve_forever

            return serve_forever(watch_interval=args.interval)
        if args.action == "enable":
            report = enable_recommended(start_with_windows=not args.no_windows_start, repo_root=root)
            print(json.dumps(report.to_dict(), indent=2) if args.json else report.message)
            return 0 if report.ok else 1
        if args.action == "install-task":
            from .canonical_config import load_runtime_config

            status = register_task(load_runtime_config())
            print(json.dumps({"exists": status.exists, "name": status.name}) if args.json else f"task registered={status.exists}")
            return 0 if status.exists else 1
        if args.action == "uninstall-task":
            status = unregister_task()
            print(json.dumps({"exists": status.exists}) if args.json else "task unregistered")
            return 0
        if args.action == "start":
            report = start_all(start_ollama_if_down=args.start_ollama, no_cloudflare=args.no_cloudflare)
            text = "\n".join(report.lines())
            print(text)
            return 0 if report.ok else 1
        if args.action == "stop":
            results = stop_all(force=args.force)
            for rec in results:
                print(f"{rec.service}: {'OK' if rec.ok else 'FAIL'} {rec.message}")
            return 0 if all(r.ok for r in results) else 1
        if args.action == "restart":
            report = restart_all(
                start_ollama_if_down=args.start_ollama,
                no_cloudflare=args.no_cloudflare,
                force=args.force,
            )
            print("\n".join(report.lines()))
            return 0 if report.ok else 1
        if args.action == "status":
            payload = collect_status()
            view = collect_runtime_view()
            payload["adeptRuntimeService"] = view
            payload["task"] = {"name": query_task().name, "exists": query_task().exists}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("ADEPT RUNTIME SERVICE — STATUS")
                print(f"  service: {view.get('serviceState')} task={view.get('taskRegistered')}")
                print(f"  comfy: {view.get('comfyState')} pid={view.get('comfyPid')} owned={view.get('owned')}")
                print(f"  fal.ai: {view.get('falConnected')}")
                print(f"  retired_web_8760: not started")
                print(f"  state_dir: {payload['state_dir']}")
            return 0
        if args.action == "watch":
            from .control_client import control_plane_reachable

            if control_plane_reachable():
                view = collect_runtime_view()
                print(
                    json.dumps(view, indent=2)
                    if args.json
                    else (
                        "Background Services manager is running. "
                        f"Studio={view.get('studioApiHealth')} pictures={view.get('comfyState')}. "
                        "Standalone watch does not start Studio or pictures."
                    )
                )
                return 0
            print(MANAGER_UNAVAILABLE, file=sys.stderr)
            return 1
    except LifecycleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1


def repo_python() -> Path:
    root = repo_root_from()
    win = root / "studio-api" / ".venv" / "Scripts" / "python.exe"
    if win.exists():
        return win
    return root / "studio-api" / ".venv" / "bin" / "python"
