#!/usr/bin/env python3
"""Recovery soak: health → chat revision → PA → controlled API kill → reconnect → repeat."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("STUDIO_API_BASE", "http://127.0.0.1:8758")
WEB = os.environ.get("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:8760")
PROJECT_ID = os.environ.get("ADEPT_PROJECT_ID", "ae57714e-d43e-4cec-9bd9-0af2780fa185")
ROUNDS = int(os.environ.get("ADEPT_RECOVERY_SOAK_ROUNDS", "3"))
STATUS = ROOT / "data" / "runtime" / "beta" / "status.json"
OUT_DIR = ROOT / "docs" / "release-gate" / "studio-api-runtime-recovery" / "artifacts"
RUN_ID = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ") + "-soak"


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 30.0):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(raw) if raw else {}


def wait_health(timeout: float = 120.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            st, _ = http_json(f"{API}/api/health", timeout=10.0)
            if st == 200:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def api_pid() -> int | None:
    if not STATUS.is_file():
        return None
    try:
        data = json.loads(STATUS.read_text(encoding="utf-8"))
        pid = (data.get("services") or {}).get("api", {}).get("pid")
        return int(pid) if pid else None
    except Exception:
        return None


def kill_api() -> int | None:
    pid = api_pid()
    if not pid:
        return None
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    return pid


def main() -> int:
    out = OUT_DIR / RUN_ID
    out.mkdir(parents=True, exist_ok=True)
    report = {"runId": RUN_ID, "startedAt": _now(), "rounds": [], "pass": True}

    if not wait_health():
        report["pass"] = False
        report["error"] = "initial health failed"
        (out / "soak.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("NO-GO initial health", file=sys.stderr)
        return 1

    for i in range(1, ROUNDS + 1):
        round_rec: dict = {"round": i, "startedAt": _now()}
        try:
            st, rev = http_json(f"{API}/api/codirector/conversations/{PROJECT_ID}/revision")
            round_rec["revision"] = {"status": st, "body": rev}
            st, pa = http_json(
                f"{API}/api/codirector/status/check",
                method="POST",
                body={"projectId": PROJECT_ID, "mode": "standard"},
                timeout=120.0,
            )
            round_rec["pa"] = {"status": st, "summary": (pa or {}).get("summary")}
            killed = kill_api()
            round_rec["killedPid"] = killed
            time.sleep(2)
            # Proxy should return classified offline (or connection error while web also bouncing).
            try:
                st, body = http_json(f"{WEB}/api/health", timeout=5.0)
                round_rec["proxyWhileDown"] = {"status": st, "body": body}
            except Exception as exc:
                round_rec["proxyWhileDown"] = {"error": str(exc)}
            recovered = wait_health(120.0)
            round_rec["recovered"] = recovered
            if not recovered:
                report["pass"] = False
                round_rec["ok"] = False
            else:
                st, rev2 = http_json(f"{API}/api/codirector/conversations/{PROJECT_ID}/revision")
                round_rec["revisionAfter"] = {"status": st, "body": rev2}
                round_rec["ok"] = st == 200
                if not round_rec["ok"]:
                    report["pass"] = False
        except Exception as exc:
            report["pass"] = False
            round_rec["ok"] = False
            round_rec["error"] = str(exc)
        report["rounds"].append(round_rec)
        print(f"round {i}: ok={round_rec.get('ok')} recovered={round_rec.get('recovered')}")

    report["completedAt"] = _now()
    (out / "soak.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "artifact": str(out / "soak.json")}, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
