"""CLI: start | stop | restart | status | watch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .env import load_beta_env
from .paths import discover_paths, repo_root_from
from .services import LifecycleError, collect_status, restart_all, start_all, stop_all
from .watch import watch_loop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runtime_supervisor", description="Adept UI Runtime Supervisor")
    parser.add_argument(
        "action",
        choices=("start", "stop", "restart", "status", "watch"),
    )
    parser.add_argument("--start-ollama", action="store_true", help="Start Ollama only if it is down (default: adopt/check)")
    parser.add_argument("--no-cloudflare", action="store_true")
    parser.add_argument("--force", action="store_true", help="Stop adopted services (never kills EXTERNAL Ollama)")
    parser.add_argument("--once", action="store_true", help="Watch a single cycle")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = repo_root_from()
    load_beta_env(root)
    discover_paths(root)  # validate discovery

    try:
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
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("ADEPT UI RUNTIME SUPERVISOR — STATUS")
                for name in ("studio_api", "comfyui", "cloudflared", "ollama"):
                    row = payload[name]
                    print(f"  {name}: {'UP' if row.get('running') else 'DOWN'} ownership={row.get('ownership')} pid={row.get('pid')}")
                print(f"  retired_web_8760: not started")
                print(f"  state_dir: {payload['state_dir']}")
            return 0
        if args.action == "watch":
            watch_loop(interval_sec=args.interval, once=args.once)
            return 0
    except LifecycleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1


def repo_python() -> Path:
    root = repo_root_from()
    win = root / "studio-api" / ".venv" / "Scripts" / "python.exe"
    if win.exists():
        return win
    return root / "studio-api" / ".venv" / "bin" / "python"
