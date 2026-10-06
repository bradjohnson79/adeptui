"""Closure 4 — Route A prepare-on-Generate proof. No NETSTAT.EXE. Does not restart Comfy :8188."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.minimax_h3.service import _ensure_route_a_for_generation  # noqa: E402
from app.runtime_manager.service import _stop_route_a_sync  # noqa: E402
from runtime_supervisor.ports import port_owner_pid  # noqa: E402

OUT = ROOT / "docs" / "release-gate" / "local-video-runtime" / "evidence" / "ROUTE_A_ONDEMAND.json"
API = "http://127.0.0.1:8758"


def _nvidia() -> dict[str, Any]:
    try:
        p = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        line = (p.stdout or "").strip().splitlines()[0]
        parts = [x.strip() for x in line.split(",")]
        return {
            "name": parts[0],
            "usedMiB": int(float(parts[1])),
            "totalMiB": int(float(parts[2])),
            "utilPct": int(float(parts[3])),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def _http_json(path: str, timeout: float = 15.0) -> dict[str, Any]:
    try:
        r = httpx.get(f"{API}{path}", timeout=timeout)
        return {"http": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:400]}
    except Exception as exc:
        return {"http": 0, "error": str(exc)}


def _comfy_stats(port: int) -> dict[str, Any]:
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/system_stats", timeout=8)
        if r.status_code != 200:
            return {"http": r.status_code}
        body = r.json()
        devices = body.get("devices") or []
        vram = devices[0] if devices else {}
        return {
            "http": 200,
            "vram_free": vram.get("vram_free"),
            "vram_total": vram.get("vram_total"),
            "version": (body.get("system") or {}).get("comfyui_version"),
        }
    except Exception as exc:
        return {"http": 0, "error": str(exc)}


def snapshot(label: str) -> dict[str, Any]:
    ready = _http_json("/api/minimax-h3/readiness")
    body = ready.get("body") if isinstance(ready.get("body"), dict) else {}
    comfy_pid = port_owner_pid(8188)
    route_pid = port_owner_pid(8192)
    return {
        "label": label,
        "ts": time.time(),
        "comfyPid": comfy_pid,
        "comfyListening": _listening(8188),
        "comfyStats": _comfy_stats(8188),
        "routeAPid": route_pid,
        "routeAListening": _listening(8192),
        "routeAStats": _comfy_stats(8192),
        "readinessHttp": ready.get("http"),
        "readiness": {
            "ready": body.get("ready"),
            "onDemand": body.get("onDemand"),
            "ok": body.get("ok"),
            "creatorStatus": body.get("creatorStatus"),
            "privateLocalEnabled": body.get("privateLocalEnabled"),
        },
        "gpu": _nvidia(),
    }


def main() -> int:
    before = snapshot("before")
    t0 = time.time()
    prepared, err = _ensure_route_a_for_generation()
    first = {
        "prepared": prepared,
        "error": err,
        "elapsedSec": round(time.time() - t0, 1),
        "after": snapshot("after_first_prepare"),
    }
    stop1 = _stop_route_a_sync()
    time.sleep(3)
    after_stop = snapshot("after_first_stop")
    t1 = time.time()
    prepared2, err2 = _ensure_route_a_for_generation()
    second = {
        "prepared": prepared2,
        "error": err2,
        "elapsedSec": round(time.time() - t1, 1),
        "after": snapshot("after_second_prepare"),
    }
    stop2 = _stop_route_a_sync()
    time.sleep(3)
    after_reconcile = snapshot("after_reconcile_stop")

    comfy_before = before.get("comfyPid")
    comfy_unchanged = (
        comfy_before
        and comfy_before == first["after"].get("comfyPid") == second["after"].get("comfyPid") == after_reconcile.get("comfyPid")
    )
    on_demand_before = bool(before["readiness"].get("onDemand") and not before["readiness"].get("ready"))
    first_up = bool(first["after"].get("routeAListening") and first["prepared"])
    second_up = bool(second["after"].get("routeAListening") and second["prepared"])
    down_between = not after_stop.get("routeAListening")
    down_after = not after_reconcile.get("routeAListening")
    report = {
        "ok": bool(comfy_unchanged and on_demand_before and first_up and second_up and down_between and down_after),
        "contract": "prepare-on-Generate, not idle watchdog; no NETSTAT.EXE; no DETACHED_PROCESS",
        "netstatAvoided": True,
        "before": before,
        "firstPrepare": first,
        "stop1": stop1,
        "afterStop": after_stop,
        "secondPrepare": second,
        "stop2": stop2,
        "afterReconcile": after_reconcile,
        "comfyPidUnchanged": bool(comfy_unchanged),
        "repeatable": bool(first_up and second_up and down_between),
        "truthfulOnDemandBefore": on_demand_before,
        "handoffVramBeforeMiB": (before.get("gpu") or {}).get("usedMiB"),
        "handoffVramAfterFirstMiB": (first["after"].get("gpu") or {}).get("usedMiB"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "ok",
                    "comfyPidUnchanged",
                    "repeatable",
                    "truthfulOnDemandBefore",
                    "netstatAvoided",
                    "handoffVramBeforeMiB",
                    "handoffVramAfterFirstMiB",
                )
            },
            indent=2,
        )
    )
    print("wrote", OUT)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
