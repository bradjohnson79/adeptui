#!/usr/bin/env python3
"""Independent read-only verifier for final Co-Director optimization."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "docs/release-gate/co-director-final-optimization/artifacts"
RUN_ID = (ART / "CURRENT_RUN_ID.txt").read_text(encoding="utf-8").strip()
DIR = ART / RUN_ID


def main() -> int:
    blockers: list[str] = []
    evidence: dict = {"runId": RUN_ID, "checks": []}

    # Pipeline manifest exists in code
    manifest_path = ROOT / "studio-api/app/codirector/conversation/pipeline_manifest.py"
    if not manifest_path.exists():
        blockers.append("missing pipeline_manifest.py")
    else:
        evidence["checks"].append({"name": "pipeline_manifest", "ok": True})

    roster_path = DIR / "specialist_roster.json"
    if roster_path.exists():
        roster = json.loads(roster_path.read_text(encoding="utf-8"))
        evidence["checks"].append({"name": "specialist_roster", "count": roster.get("count")})
        if roster.get("creatorFacingAllowed") is not False:
            blockers.append("specialists must set creatorFacingAllowed false")
        if int(roster.get("count") or 0) < 1:
            blockers.append("empty specialist roster")
    else:
        blockers.append("missing specialist_roster.json")

    summary_path = DIR / "final_cert_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        evidence["checks"].append({"name": "playwright", **summary})
        if summary.get("verdictCandidate") != "PASS_GATES":
            blockers.append(f"playwright={summary.get('verdictCandidate')}")
        if not summary.get("momentum"):
            blockers.append("momentum missing from cert")
        if not summary.get("streamed"):
            blockers.append("streamed flag missing")
        if not summary.get("deferEnrichment"):
            blockers.append("deferEnrichment missing")
    else:
        blockers.append("missing final_cert_summary.json")

    soak_path = DIR / "soak_sequential_50.json"
    if soak_path.exists():
        soak = json.loads(soak_path.read_text(encoding="utf-8"))
        evidence["checks"].append(
            {
                "name": "soak50",
                "p50": soak.get("p50TtftMs"),
                "p95": soak.get("p95TtftMs"),
                "max": soak.get("maxTtftMs"),
                "gates": soak.get("gates"),
            }
        )
        gates = soak.get("gates") or {}
        if not gates.get("p95Under20s"):
            blockers.append(f"soak P95 fail: {soak.get('p95TtftMs')}")
        if not gates.get("maxUnder30s"):
            blockers.append(f"soak max fail: {soak.get('maxTtftMs')}")
        # P50 < 8s is the target; record soft fail if missed but still allow VERIFIED only if hard gates pass
        if not gates.get("p50Under8s"):
            evidence["checks"].append({"name": "p50_soft", "note": f"P50={soak.get('p50TtftMs')} not under 8s"})
            blockers.append(f"soak P50 fail: {soak.get('p50TtftMs')}")
    else:
        blockers.append("missing soak_sequential_50.json")

    for name in ("momentum.py", "creative_confidence.py", "request_timing.py"):
        if not (ROOT / "studio-api/app/codirector/conversation" / name).exists():
            blockers.append(f"missing {name}")

    verdict = "VERIFIED" if not blockers else "BLOCKED"
    out = {"verdict": verdict, "blockers": blockers, "evidence": evidence}
    (DIR / "independent_verifier.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
