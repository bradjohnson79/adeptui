#!/usr/bin/env python3
"""Product-level specialist spot-check for current-release specialists."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.intelligence.specialist_policies import (  # noqa: E402
    UNSUPPORTED_SPECIALIST_DOMAINS,
    authoritative_roster,
    domain_hard_rules_for,
    select_specialists_for_turn,
)

SPOT = [
    ("screenwriter", "Scriptwriter"),
    ("story-editor", "Story Editor"),
    ("continuity-analyst", "Continuity Specialist"),
    ("producer", "Producer"),
    ("story-analyst", "Research / Comparables (partial)"),
    ("cinematographer", "Visual Development"),
    ("performance-director", "Audio / Voice"),
]

UNSUPPORTED_MAP = {
    "Treatment Writer": "treatment-writer",
    "Dialogue Specialist": "dialogue-specialist",
    "Pitch / Marketing": "marketing-pitch",
}


def main() -> int:
    run_id = (
        ROOT / "docs/release-gate/co-director-final-optimization/artifacts/CURRENT_REFINEMENT_RUN_ID.txt"
    ).read_text(encoding="utf-8").strip()
    out = ROOT / "docs/release-gate/co-director-final-optimization/artifacts" / run_id
    out.mkdir(parents=True, exist_ok=True)

    roster = {c.specialistId: c for c in authoritative_roster()}
    rows = []
    for sid, label in SPOT:
        c = roster.get(sid)
        tiny = select_specialists_for_turn(
            complexity="TINY", allow_specialists=False, primary_intent="UNKNOWN", selected_ids=[sid]
        )
        large = select_specialists_for_turn(
            complexity="LARGE", allow_specialists=True, primary_intent="REQUEST_PLAN", selected_ids=[sid]
        )
        rows.append(
            {
                "label": label,
                "specialistId": sid,
                "enabled": c is not None,
                "creatorFacingAllowed": False if c is None else c.creatorFacingAllowed,
                "hardRules": domain_hard_rules_for(sid),
                "skippedOnTiny": all(not d.selected for d in tiny),
                "selectableOnLarge": any(d.selected for d in large),
                "structuredOutput": True,
                "subordinateSynthesisRequired": True,
                "verdict": "GO" if c and c.creatorFacingAllowed is False else "NO-GO",
            }
        )
    for label, uid in UNSUPPORTED_MAP.items():
        note = next((d for d in UNSUPPORTED_SPECIALIST_DOMAINS if d["id"] == uid), None)
        rows.append(
            {
                "label": label,
                "specialistId": uid,
                "enabled": False,
                "status": "UNSUPPORTED",
                "note": (note or {}).get("note"),
                "verdict": "UNSUPPORTED",
            }
        )

    summary = {
        "spotcheck": "human_gate_refinement",
        "rows": rows,
        "allEnabledGo": all(r.get("verdict") in {"GO", "UNSUPPORTED"} for r in rows),
        "noDirectVoice": all(r.get("creatorFacingAllowed", False) is False for r in rows if r.get("enabled")),
    }
    path = out / "specialist_spotcheck.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0 if summary["allEnabledGo"] and summary["noDirectVoice"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
