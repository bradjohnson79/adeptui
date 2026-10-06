"""python -m runtime_supervisor.headless_comfy start|stop|status"""

from __future__ import annotations

import argparse
import json
import sys

from ..env import load_beta_env
from ..paths import discover_paths, repo_root_from
from ..state import SupervisorState
from .service import request_start, request_stop, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adept-headless-comfy")
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root_from()
    load_beta_env(root)
    paths = discover_paths(root)
    state = SupervisorState.from_env(root)
    if args.action == "start":
        result = request_start(paths, state, spawn=True)
        print(f"{'OK' if result.ok else 'FAIL'} ({result.ownership}) {result.message}")
        return 0 if result.ok else 1
    if args.action == "stop":
        result = request_stop(state, force=False)
        print(f"{'OK' if result.ok else 'FAIL'} ({result.ownership}) {result.message}")
        return 0 if result.ok else 1
    payload = status(paths, state)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"healthy={payload['healthy']} ownership={payload['ownership']} "
            f"pid={payload['pid']} yaml={payload['yaml']}"
        )
    return 0 if payload.get("ownership") != "external" or not payload.get("healthy") else 2


if __name__ == "__main__":
    sys.exit(main())
