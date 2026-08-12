#!/usr/bin/env python3
"""Long-project Dreamweaver path: cache + momentum resume evidence."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:8758"
PROJECT_ID = "cd40c8e5-8bae-4c42-9795-90dc60fa2875"


def stream(content: str) -> dict:
    body = json.dumps(
        {"messages": [{"role": "user", "content": content}], "project_id": PROJECT_ID, "mode": "chat"}
    ).encode()
    req = urllib.request.Request(
        f"{API}/api/codirector/chat/stream",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    t0 = time.perf_counter()
    ttft = None
    momentum = None
    resume = None
    cache_hit = None
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                ev = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "token" and ttft is None:
                ttft = time.perf_counter()
            if ev.get("type") == "momentum_resume":
                resume = ev.get("resume")
            if ev.get("type") == "creative_momentum":
                momentum = ev.get("momentum")
            if ev.get("type") == "conversation_timings":
                ledger = (ev.get("timings") or {}).get("ledger") or {}
                cache_hit = ledger.get("cacheHit")
            if ev.get("type") == "completed":
                break
    return {
        "ttftMs": round(((ttft or time.perf_counter()) - t0) * 1000, 1),
        "cacheHit": cache_hit,
        "resume": resume,
        "momentum": bool(momentum),
    }


def main() -> int:
    run_id = (
        ROOT / "docs/release-gate/co-director-final-optimization/artifacts/CURRENT_RUN_ID.txt"
    ).read_text(encoding="utf-8").strip()
    out = ROOT / "docs/release-gate/co-director-final-optimization/artifacts" / run_id
    out.mkdir(parents=True, exist_ok=True)
    # Seed momentum then simulate return
    seed = stream(
        "Korri is fighting to keep her past true in a world where memory is court evidence. "
        "I'm excited about the quiet first encounter with the Dreamweaver."
    )
    ret = stream("Remind me where we left off creatively — I want to pick that thread back up.")
    summary = {
        "path": "long_project_dreamweaver",
        "projectId": PROJECT_ID,
        "seed": seed,
        "return": ret,
        "momentumResumeObserved": bool(ret.get("resume") or ret.get("momentum") or seed.get("momentum")),
        "cacheHitOnReturn": ret.get("cacheHit"),
    }
    (out / "long_project_path.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["momentumResumeObserved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
