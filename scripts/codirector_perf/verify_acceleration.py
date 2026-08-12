#!/usr/bin/env python3
"""Independent read-only verifier for Co-Director response acceleration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "docs/release-gate/co-director-performance/artifacts"
RUN_ID = (ART / "CURRENT_RUN_ID.txt").read_text(encoding="utf-8").strip()
DIR = ART / RUN_ID


def main() -> int:
    blockers: list[str] = []
    evidence: dict = {"runId": RUN_ID, "checks": []}

    post = DIR / "isolation_matrix.json"
    if not post.exists():
        blockers.append("missing isolation_matrix.json")
    else:
        matrix = json.loads(post.read_text(encoding="utf-8"))
        rows = {r.get("path"): r for r in matrix.get("rows") or []}
        e = rows.get("E_full_orchestration") or {}
        ttft = e.get("ttftMs")
        tokens = e.get("tokens") or 0
        evidence["checks"].append({"name": "E_ttft", "ttftMs": ttft, "tokens": tokens})
        if ttft is None or ttft > 30000:
            blockers.append(f"E TTFT hard fail: {ttft}")
        elif ttft > 20000:
            blockers.append(f"E TTFT soft fail >20s: {ttft}")
        if tokens < 20:
            blockers.append(f"token count suggests fake stream: {tokens}")

    summary_path = DIR / "acceleration_cert_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        evidence["checks"].append({"name": "playwright_summary", **summary})
        if summary.get("verdictCandidate") != "PASS_GATES":
            blockers.append(f"playwright verdictCandidate={summary.get('verdictCandidate')}")
        if (summary.get("nextStepCount") or 0) < 1:
            blockers.append("nextStepCount < 1")
    else:
        blockers.append("missing acceleration_cert_summary.json")

    next_path = DIR / "stage_n_next_steps.json"
    if next_path.exists():
        nxt = json.loads(next_path.read_text(encoding="utf-8"))
        opts = nxt.get("options") or []
        evidence["checks"].append({"name": "next_steps", "count": len(opts)})
        if not any(o.get("type") == "CONTINUE_STORY" for o in opts):
            blockers.append("CONTINUE_STORY missing from next steps")
    else:
        blockers.append("missing stage_n_next_steps.json")

    verdict = "VERIFIED" if not blockers else "BLOCKED"
    out = {"verdict": verdict, "blockers": blockers, "evidence": evidence}
    out_path = DIR / "independent_verifier.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
