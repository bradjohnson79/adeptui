#!/usr/bin/env python3
"""Sequential soak (≥50 turns) for final Co-Director optimization."""

from __future__ import annotations

import json
import statistics
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:8758"
PROJECT_ID = "cd40c8e5-8bae-4c42-9795-90dc60fa2875"

MESSAGES = [
    "Call me Brad.",
    "Korri waits while clerks stamp memories as evidence.",
    "What stands out about that anteroom beat?",
    "I'm excited about the first quiet encounter with the Dreamweaver.",
    "Keep listening — the harbor lantern returns in flashback three.",
    "She refuses to sign the redacted transcript.",
    "Help me tighten Korri's dialogue when she realizes the rewrite.",
    "The world rule is that testimony frames flashbacks.",
    "I love intimate conversations more than large action.",
    "Let's explore how Kyung reacts after the encounter.",
] * 5 + [
    "Who is actually communicating with Kyung?",
    "Draft a short working treatment section — ask ownership first.",
    "What feels original in this premise so far?",
    "Stay with discovery; no production yet.",
    "Compare the memory-as-evidence idea to similar works only if research is allowed — otherwise stay offline.",
    "Remind me where we left off creatively.",
    "Korri's emotional wound is trust in her own perception.",
    "A quieter scene in the archive basement feels strongest.",
    "Skip marketing — this is still personal.",
    "Continue the story from the lantern return.",
]


def stream_once(content: str) -> dict:
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
    tokens = 0
    next_steps = 0
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
            et = ev.get("type")
            if et == "token":
                if ttft is None:
                    ttft = time.perf_counter()
                tokens += 1
            elif et == "next_step_options":
                next_steps = len(ev.get("options") or [])
            elif et == "conversation_timings":
                ledger = (ev.get("timings") or {}).get("ledger") or ev.get("timings") or {}
                if isinstance(ledger, dict) and "cacheHit" in ledger:
                    cache_hit = ledger.get("cacheHit")
            elif et == "completed":
                break
    return {
        "ttftMs": round(((ttft or time.perf_counter()) - t0) * 1000, 1),
        "tokens": tokens,
        "nextSteps": next_steps,
        "cacheHit": cache_hit,
    }


def main() -> int:
    run_id = (
        ROOT / "docs/release-gate/co-director-final-optimization/artifacts/CURRENT_RUN_ID.txt"
    ).read_text(encoding="utf-8").strip()
    out_dir = ROOT / "docs/release-gate/co-director-final-optimization/artifacts" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    # Warm selected model so cold-load is not counted as ordinary TTFT.
    warm = stream_once("Warm the creative session — short ack only.")
    print({"warmup": warm}, flush=True)
    rows = []
    for i, msg in enumerate(MESSAGES, 1):
        row = {"turn": i, "message": msg[:80], **stream_once(msg)}
        rows.append(row)
        print(row, flush=True)
    ttfts = [r["ttftMs"] for r in rows]
    ttfts_sorted = sorted(ttfts)
    p50 = statistics.median(ttfts_sorted)
    p95 = ttfts_sorted[max(0, int(len(ttfts_sorted) * 0.95) - 1)]
    summary = {
        "soak": "sequential_50",
        "turns": len(rows),
        "p50TtftMs": p50,
        "p95TtftMs": p95,
        "maxTtftMs": max(ttfts),
        "meanTtftMs": round(statistics.mean(ttfts), 1),
        "gates": {
            "p50Under8s": p50 < 8000,
            "p95Under20s": p95 < 20000,
            "maxUnder30s": max(ttfts) < 30000,
        },
        "rows": rows,
    }
    path = out_dir / "soak_sequential_50.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2), flush=True)
    return 0 if summary["gates"]["maxUnder30s"] and summary["gates"]["p95Under20s"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
