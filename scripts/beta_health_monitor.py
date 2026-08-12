"""Adept UI Beta health monitor / soak recorder.

Detect + record only — NEVER restarts or repairs anything (a monitor that
heals the system would green the test instead of measuring it).

Dual-metric stability rule (release gate):
  Continuous stability requires BOTH
    - processRestartCount == 0      (no unintended listener PID changes)
    - failedHealthSampleCount == 0  (no failed web/API health samples)
  Neither metric may substitute for the other: a service can stay alive
  while returning bad responses, and a process can restart fast enough for
  health polling to barely notice.

Usage:
  python scripts/beta_health_monitor.py --duration-minutes 30 \
      --out docs/release-gate/timeline-full-audit/artifacts/beta-health-soak.json

Exit code 0 = CONTINUOUSLY HEALTHY, 1 = otherwise (see verdict in JSON).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WEB_URL = "http://127.0.0.1:8760/"
API_URL = "http://127.0.0.1:8758/api/health"
STATUS_FILE = Path("data/runtime/beta/status.json")
SUPERVISOR_LOG = Path("data/runtime/logs/beta/supervisor.log")


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


def _probe(url: str, timeout: float) -> tuple[bool, int | None, float, str | None]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            code = int(resp.status)
            resp.read()
        return 200 <= code < 400, code, (time.perf_counter() - started) * 1000.0, None
    except Exception as exc:  # noqa: BLE001 - record, never raise
        return False, None, (time.perf_counter() - started) * 1000.0, f"{type(exc).__name__}: {exc}"


def _port_pids(port: int) -> list[int]:
    if os.name != "nt":
        return []
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"], text=True, errors="ignore"
        )
    except Exception:
        return []
    pids: list[int] = []
    needle = f":{port} "
    for line in out.splitlines():
        if "LISTENING" not in line.upper() or needle not in line:
            continue
        parts = line.split()
        try:
            pid = int(parts[-1])
        except (ValueError, IndexError):
            continue
        if pid > 0:
            pids.append(pid)
    return sorted(set(pids))


def _supervisor_state() -> str | None:
    try:
        payload = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        return str(payload.get("state") or "") or None
    except Exception:
        return None


def _supervisor_restart_events(since_iso: str) -> list[str]:
    """Restart/exit lines appended to supervisor.log after `since_iso`."""
    events: list[str] = []
    try:
        for line in SUPERVISOR_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
            if line[:1] != "[":
                continue
            ts = line[1:25]
            if ts < since_iso:
                continue
            if ("exited unexpectedly" in line) or ("restarting" in line) or ("CRASH_LOOP" in line):
                events.append(line.strip())
    except Exception:
        pass
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description="Adept UI Beta health monitor")
    parser.add_argument("--duration-minutes", type=float, default=30.0)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    started_iso = _now()
    deadline = time.time() + args.duration_minutes * 60.0

    samples: list[dict] = []
    failure_windows: list[dict] = []
    open_failure: dict | None = None
    last_listener_pids: dict[str, list[int]] = {"api": [], "web": []}
    process_restarts: list[dict] = []
    failed_samples = 0

    def snapshot(final: bool = False) -> dict:
        return {
            "monitor": "beta_health_monitor",
            "startedAt": started_iso,
            "endedAt": _now() if final else None,
            "durationMinutesRequested": args.duration_minutes,
            "intervalSeconds": args.interval_seconds,
            "targets": {"web": WEB_URL, "api": API_URL},
            "counters": {
                # Independent metrics — neither may substitute for the other.
                "processRestartCount": len(process_restarts),
                "failedHealthSampleCount": failed_samples,
                "sampleCount": len(samples),
            },
            "processRestarts": process_restarts,
            "failureWindows": failure_windows,
            "supervisorRestartEvents": _supervisor_restart_events(started_iso),
            "verdict": (
                "CONTINUOUSLY HEALTHY"
                if not process_restarts and failed_samples == 0
                else "FAILED-THEN-RECOVERED"
                if process_restarts or failed_samples
                else "UNKNOWN"
            ),
            "samples": samples,
        }

    while time.time() < deadline:
        ts = _now()
        web_ok, web_code, web_ms, web_err = _probe(WEB_URL, timeout=5.0)
        api_ok, api_code, api_ms, api_err = _probe(API_URL, timeout=30.0)
        api_pids = _port_pids(8758)
        web_pids = _port_pids(8760)

        for name, pids in (("api", api_pids), ("web", web_pids)):
            prev = last_listener_pids[name]
            if prev and pids and pids != prev:
                process_restarts.append(
                    {
                        "at": ts,
                        "service": name,
                        "previousPids": prev,
                        "currentPids": pids,
                        "note": "listener PID set changed while monitor was running",
                    }
                )
            if pids:
                last_listener_pids[name] = pids

        sample_ok = web_ok and api_ok
        if not sample_ok:
            failed_samples += 1
            if open_failure is None:
                open_failure = {"startedAt": ts, "webOk": web_ok, "apiOk": api_ok}
        elif open_failure is not None:
            open_failure["endedAt"] = ts
            failure_windows.append(open_failure)
            open_failure = None

        samples.append(
            {
                "at": ts,
                "web": {"ok": web_ok, "status": web_code, "ms": round(web_ms, 1), "error": web_err},
                "api": {"ok": api_ok, "status": api_code, "ms": round(api_ms, 1), "error": api_err},
                "ports": {
                    "api": {"pids": api_pids, "listenerCount": len(api_pids)},
                    "web": {"pids": web_pids, "listenerCount": len(web_pids)},
                },
                "supervisorState": _supervisor_state(),
            }
        )
        out_path.write_text(json.dumps(snapshot(), indent=2), encoding="utf-8")
        time.sleep(args.interval_seconds)

    if open_failure is not None:
        open_failure["endedAt"] = _now()
        open_failure["note"] = "still failing at monitor stop"
        failure_windows.append(open_failure)

    final = snapshot(final=True)
    out_path.write_text(json.dumps(final, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": final["verdict"],
                "counters": final["counters"],
                "failureWindows": len(failure_windows),
                "out": str(out_path),
            },
            indent=2,
        )
    )
    return 0 if final["verdict"] == "CONTINUOUSLY HEALTHY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
