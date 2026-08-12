#!/usr/bin/env python3
"""Independent read-only verifier for human-gate refinement."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "docs/release-gate/co-director-final-optimization/artifacts"
RUN_ID = (ART / "CURRENT_REFINEMENT_RUN_ID.txt").read_text(encoding="utf-8").strip()
DIR = ART / RUN_ID
AUDIT = ROOT / "docs/release-gate/co-director-final-optimization/CO_DIRECTOR_END_TO_END_OPTIMIZATION_AUDIT.md"


def main() -> int:
    blockers: list[str] = []
    evidence: dict = {"runId": RUN_ID, "checks": []}

    # Law present in code
    wiki_v = ROOT / "studio-api/app/codirector/conversation/wiki_verification.py"
    if not wiki_v.exists():
        blockers.append("missing wiki_verification.py")
    else:
        text = wiki_v.read_text(encoding="utf-8")
        if "WIKI_VERIFICATION_NEVER_BLOCKS_TTFT" not in text:
            blockers.append("missing WIKI_VERIFICATION_NEVER_BLOCKS_TTFT law")
        if "persistenceState" not in text or "presentationState" not in text:
            blockers.append("missing persistence/presentation split")
        else:
            evidence["checks"].append({"name": "wiki_verification_contract", "ok": True})

    deferred = (ROOT / "studio-api/app/codirector/conversation/deferred_enrichment.py").read_text(
        encoding="utf-8"
    )
    if "issubset" not in deferred and "set(persisted_ids)" not in deferred:
        blockers.append("full read-back not enforced in deferred_enrichment")
    else:
        evidence["checks"].append({"name": "full_readback_deferred_only", "ok": True})

    summary_path = DIR / "final_cert_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        evidence["checks"].append({"name": "playwright", **summary})
        if summary.get("verdictCandidate") != "PASS_GATES":
            blockers.append("playwright not PASS_GATES")
        if summary.get("wikiNeverBlockedTtft") is False:
            blockers.append("wiki blocked TTFT")
    else:
        blockers.append("missing final_cert_summary.json")

    for name in ("wiki_write_trace.json", "next_steps.json", "concurrent_valid_routes.json"):
        if not (DIR / name).exists():
            blockers.append(f"missing {name}")

    concurrent = DIR / "concurrent_valid_routes.json"
    if concurrent.exists():
        c = json.loads(concurrent.read_text(encoding="utf-8"))
        if c.get("gates"):
            for k, v in (c.get("gates") or {}).items():
                if not v:
                    blockers.append(f"concurrent gate fail: {k}")
            evidence["checks"].append({"name": "concurrent", "gates": c.get("gates")})
        else:
            # Playwright-written status codes
            for k in ("wiki", "library", "paRegistry"):
                st = c.get(k)
                if st not in (200, None) and st != 200:
                    if isinstance(st, int) and st >= 400:
                        blockers.append(f"concurrent route bad: {k}={st}")

    spot = DIR / "specialist_spotcheck.json"
    if spot.exists():
        s = json.loads(spot.read_text(encoding="utf-8"))
        if not s.get("noDirectVoice"):
            blockers.append("specialist direct voice risk")
        evidence["checks"].append({"name": "specialist_spotcheck", "ok": s.get("allEnabledGo")})
    else:
        blockers.append("missing specialist_spotcheck.json")

    audit_text = AUDIT.read_text(encoding="utf-8") if AUDIT.exists() else ""
    if "UNCOMPLETE" in audit_text:
        blockers.append("audit still contains UNCOMPLETE")
    if "average ≥ 4" in audit_text and "4.25" not in audit_text:
        blockers.append("weak human threshold still present")
    if "4.25" not in audit_text:
        blockers.append("strict 4.25 threshold missing from audit")
    evidence["checks"].append({"name": "audit_wording", "incompleteOk": "UNCOMPLETE" not in audit_text})

    scorecard = DIR / "human_scorecard.md"
    if not scorecard.exists():
        blockers.append("missing human_scorecard.md")
    else:
        sc = scorecard.read_text(encoding="utf-8")
        if "AWAITING_PRODUCT_OWNER" not in sc and "awaiting" not in sc.lower():
            blockers.append("scorecard must remain awaiting product owner")
        if "4.25" not in sc:
            blockers.append("scorecard missing 4.25 threshold")

    verdict = "VERIFIED" if not blockers else "BLOCKED"
    out = {"verdict": verdict, "blockers": blockers, "evidence": evidence}
    (DIR / "independent_refinement_verifier.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
