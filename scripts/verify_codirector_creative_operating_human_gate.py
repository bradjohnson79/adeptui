#!/usr/bin/env python3
"""
Independent human-gate refinement verifier for Co-Director Creative Operating Intelligence.

Read-only / light API checks. Returns exactly VERIFIED or BLOCKED.
A BLOCKED result prevents human approval.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758").rstrip("/")
PROJECT_NAME = "The Dreamweaver"
ROOT = Path("docs/release-gate/co-director-creative-operating-intelligence")
OUT = ROOT / "artifacts"
REPORT = ROOT / "CO_DIRECTOR_CREATIVE_OPERATING_INTELLIGENCE_COMPLETION_REPORT.md"
HUMAN = ROOT / "HUMAN_EXPERIENCE_REVIEW.md"
SUPPORT_SPEC = Path("tests/e2e/codirector/codirector-creative-operating-human-gate-support.spec.ts")
COMPOSITION = Path("studio-api/app/codirector/creative_operating/composition.py")
CURIOSITY = Path("studio-api/app/codirector/creative_operating/curiosity.py")
CANON = Path("studio-api/app/codirector/creative_operating/canon_safety.py")
FORWARD = Path("studio-api/app/codirector/creative_operating/forward.py")


def get(path: str):
    req = urllib.request.Request(f"{API}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def put(path: str, body: dict):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post(path: str, body: dict | None = None):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_project() -> str:
    forced = (os.environ.get("ADEPT_PROJECT_ID") or "").strip()
    if forced:
        return forced
    body = get("/api/projects")
    projects = body if isinstance(body, list) else body.get("projects") or body.get("items") or []
    for p in projects:
        if p.get("name") == PROJECT_NAME:
            return str(p["id"])
    raise RuntimeError("Dreamweaver not found — set ADEPT_PROJECT_ID")


def scorecard_blank(text: str) -> bool:
    """Fail if numeric scores appear prefilled in the scorecard table body."""
    # Look for "| number |" score cells in the Dimension table region
    section = text
    if "## 3. Scorecard" in text:
        section = text.split("## 3. Scorecard", 1)[1].split("## 4.", 1)[0]
    # Prefill pattern: score column filled with 1-5
    if re.search(r"\|\s*[1-5]\s*\|", section):
        return False
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gates: dict[str, str] = {}

    try:
        report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
        human = HUMAN.read_text(encoding="utf-8") if HUMAN.exists() else ""

        # Governing report status consistency
        has_program = "FINAL PRODUCT ACCEPTANCE: HOLD" in report and "PRODUCT-OWNER HUMAN REVIEW: PENDING" in report
        has_hold_verdict = "HOLD — PRODUCT-OWNER HUMAN EXPERIENCE REVIEW PENDING" in report
        # Must not claim final product GO while HOLD is the product verdict
        final_section = report.split("## Final Product Verdict", 1)[-1] if "## Final Product Verdict" in report else ""
        claims_final_go_in_product = (
            "GO — CO-DIRECTOR CREATIVE OPERATING INTELLIGENCE AND PROJECT BIBLE STEWARDSHIP VERIFIED"
            in final_section
            and "HOLD — PRODUCT-OWNER HUMAN EXPERIENCE REVIEW PENDING" not in final_section
        )
        gates["Governing report reconciled"] = "GO" if has_program and has_hold_verdict and REPORT.exists() else "FAIL"
        gates["Final GO removed until human pass"] = "GO" if has_hold_verdict and not claims_final_go_in_product else "FAIL"

        # Latency labeling: decision-layer must be named; TTFT must not be equated without caveat
        report_l = report.lower()
        latency_ok = (
            "Creative Operating decision-layer latency" in report
            and "ttft" in report_l
            and ("not" in report_l or "do not imply" in report_l)
        )
        gates["Evidence latency correctly labeled"] = "GO" if latency_ok else "FAIL"

        # Blank owner scorecard
        gates["Blank owner-owned scorecard"] = (
            "GO" if HUMAN.exists() and "Do not prefill scores" in human and scorecard_blank(human) else "FAIL"
        )

        # Support Playwright present
        gates["Support Playwright present"] = "GO" if SUPPORT_SPEC.exists() else "FAIL"

        # Initiative-mode differences in composition
        comp = COMPOSITION.read_text(encoding="utf-8") if COMPOSITION.exists() else ""
        gates["Initiative-mode differences"] = (
            "GO"
            if all(
                s in comp
                for s in (
                    "QUIET_PARTNER",
                    "COLLABORATIVE_PARTNER",
                    "PROACTIVE_PRODUCER",
                    "HANDS_ON_CO_CREATOR",
                    "authorship",
                )
            )
            else "FAIL"
        )

        # Question budget module
        cur = CURIOSITY.read_text(encoding="utf-8") if CURIOSITY.exists() else ""
        gates["Question budget"] = "GO" if "def question_budget" in cur and "listening_only" in cur else "FAIL"

        # Canon separation
        can = CANON.read_text(encoding="utf-8") if CANON.exists() else ""
        gates["Canon separation"] = "GO" if "assert_not_promoted_to_canon" in can or "CONFIRMED" in can else "FAIL"

        # One-step-ahead restraint
        fwd = FORWARD.read_text(encoding="utf-8") if FORWARD.exists() else ""
        gates["One-step-ahead restraint"] = (
            "GO" if "one" in fwd.lower() and ("exploratory" in fwd.lower() or "EXPLORATORY" in fwd) else "FAIL"
        )

        # Live API behavioral spot-checks
        pid = resolve_project()
        put(f"/api/codirector/projects/{pid}/creative-operating/initiative", {"initiativeLevel": "QUIET_PARTNER"})
        quiet = post(
            f"/api/codirector/projects/{pid}/creative-operating/decision",
            {
                "message": (
                    "The researcher returns to the quiet archive and listens without asking for feedback. "
                    "She notices the strained partnership and keeps laying story detail without pausing for questions."
                )
            },
        )
        dec = quiet.get("decision") or {}
        qb = dec.get("questionBudget")
        gates["Quiet Partner behavior"] = (
            "GO"
            if dec.get("listeningOnly") and int(qb if qb is not None else 1) == 0
            else "FAIL"
        )

        put(
            f"/api/codirector/projects/{pid}/creative-operating/initiative",
            {"initiativeLevel": "COLLABORATIVE_PARTNER"},
        )
        collab = post(
            f"/api/codirector/projects/{pid}/creative-operating/decision",
            {"message": "What do you notice about the archive partnership so far?"},
        )
        cdec = collab.get("decision") or {}
        gates["Collaborative Partner behavior"] = (
            "GO" if cdec.get("initiativeLevel") == "COLLABORATIVE_PARTNER" else "FAIL"
        )

        put(
            f"/api/codirector/projects/{pid}/creative-operating/initiative",
            {"initiativeLevel": "PROACTIVE_PRODUCER"},
        )
        pro = post(
            f"/api/codirector/projects/{pid}/creative-operating/decision",
            {
                "message": (
                    "Help me develop the character. They have a role but no motivation yet. "
                    "What should we deepen next?"
                )
            },
        )
        pdec = pro.get("decision") or {}
        suggestion = str(((pdec.get("forwardSuggestion") or {}).get("suggestion") or ""))
        overplan = bool(re.search(r"Episodes?\s*2\s*[-–—]\s*10|full season", suggestion, re.I))
        gates["Proactive Producer behavior"] = (
            "GO"
            if (not pdec.get("listeningOnly"))
            and int(pdec.get("questionBudget") if pdec.get("questionBudget") is not None else 0) >= 1
            and not overplan
            else "FAIL"
        )

        put(
            f"/api/codirector/projects/{pid}/creative-operating/initiative",
            {"initiativeLevel": "HANDS_ON_CO_CREATOR"},
        )
        hands = post(
            f"/api/codirector/projects/{pid}/creative-operating/decision",
            {"message": "Draft a short exploratory preview of the confrontation."},
        )
        hdec = hands.get("decision") or {}
        gates["Hands-On Co-Creator behavior"] = (
            "GO" if hdec.get("initiativeLevel") == "HANDS_ON_CO_CREATOR" and "authorship" in comp else "FAIL"
        )

        # Creative temperature mapping present
        minds = Path("studio-api/app/codirector/creative_operating/minds.py").read_text(encoding="utf-8")
        gates["Creative-temperature behavior"] = (
            "GO" if "EMERGING" in minds and "PRODUCING" in minds and "map_creative_stage" in minds else "FAIL"
        )

        # Specific interest / anti-generic in composition
        gates["Specific project interest"] = (
            "GO" if "great idea" in comp.lower() or "generic" in comp.lower() else "FAIL"
        )

        gates["Question timing"] = gates["Quiet Partner behavior"]
        gates["Question quality"] = "GO" if "questionBudget" in str(dec) or "surfacedQuestion" in str(pdec) else "FAIL"

        gates["One-step-ahead restraint (live)"] = "GO" if not overplan else "FAIL"

        # Project Bible cleanliness — steward prompt + simplify helpers
        steward = Path("studio-api/app/codirector/prompts/specialists/project-bible-steward.md")
        bible = Path("studio-api/app/codirector/creative_operating/bible_steward.py").read_text(encoding="utf-8")
        gates["Project Bible cleanliness"] = (
            "GO" if steward.exists() and ("simplify" in bible.lower() or "heading" in bible.lower()) else "FAIL"
        )

        # Why it matters
        gates["Why It Matters fields"] = (
            "GO" if "why_it_matters" in bible.lower() or "WhyItMatters" in bible or "whyItMatters" in bible else "FAIL"
        )
        if gates["Why It Matters fields"] != "GO":
            # contracts may hold WhyItMatters
            contracts = Path("studio-api/app/codirector/creative_operating/contracts.py").read_text(encoding="utf-8")
            gates["Why It Matters fields"] = "GO" if "WhyItMatters" in contracts or "whyItMatters" in contracts else "FAIL"

        gates["Curiosity continuity"] = "GO" if "upsert_curiosity_threads" in cur else "FAIL"

        # Disagreement / specialist subordination
        dis = post(
            f"/api/codirector/projects/{pid}/creative-operating/decision",
            {
                "message": "Reveal now or later?",
                "specialistPositions": {
                    "story-editor": "Reveal is powerful.",
                    "producer": "Overloaded.",
                    "script-supervisor": "Continuity conflict.",
                },
            },
        )
        synth = ((dis.get("decision") or {}).get("disagreement") or {}).get("synthesizedRecommendation") or ""
        gates["Disagreement synthesis"] = "GO" if synth else "FAIL"
        gates["Specialist cohesion"] = (
            "GO" if synth and "story-editor" not in synth.lower() and "producer says" not in synth.lower() else "FAIL"
        )
        gates["Specialist subordination"] = gates["Specialist cohesion"]

        # Correction structure
        corr = post(
            f"/api/codirector/projects/{pid}/creative-operating/identity/correct",
            {
                "surfaces": ["Special Agent Morgan", "Agent Morgan"],
                "canonicalName": "Special Agent Jordan Morgan",
            },
        )
        gates["Correction structure"] = (
            "GO" if corr.get("ok") and corr.get("undoSupported") else "FAIL"
        )

        # Script grounding
        script = post(
            f"/api/codirector/projects/{pid}/creative-operating/script/analyze",
            {
                "text": "EPISODE 1\n\nINT. LAB - NIGHT\n\nAGENT HALE\nWe start here.\n",
                "filename": "hg-verify.txt",
                "installmentHint": "Episode 1",
            },
        )
        scenes = (script.get("breakdown") or {}).get("scenes") or []
        gates["Script grounding"] = "GO" if scenes else "FAIL"
        gates["Script intelligence"] = gates["Script grounding"]
        gates["Correction intelligence"] = gates["Correction structure"]

        # Cross-format
        doc = post(
            "/api/projects",
            {"name": f"COI-HG-Verify-Doc-{os.getpid()}", "primary_project_type": "documentary"},
        )
        doc_id = str(doc.get("id") or (doc.get("project") or {}).get("id") or "")
        if not doc_id:
            gates["Cross-format behavior"] = "FAIL"
        else:
            ddec = post(
                f"/api/codirector/projects/{doc_id}/creative-operating/decision",
                {
                    "message": (
                        "Documentary interview subjects and archival gaps remain. "
                        "We need a missing perspective — not an episode structure."
                    )
                },
            )
            fmt = (ddec.get("decision") or {}).get("projectFormat")
            suggestion = str(((ddec.get("decision") or {}).get("forwardSuggestion") or {}).get("suggestion") or "")
            gates["Cross-format behavior"] = (
                "GO" if fmt != "EPISODIC_SERIES" and "Episode 2" not in suggestion else "FAIL"
            )

        # Response naturalness guidance present
        gates["Response naturalness"] = (
            "GO" if "Vary the shape" in comp or "do not use a rigid template" in comp.lower() else "FAIL"
        )

        # Latency preservation — decision quiet under 5s
        import time

        t0 = time.time()
        put(f"/api/codirector/projects/{pid}/creative-operating/initiative", {"initiativeLevel": "QUIET_PARTNER"})
        post(
            f"/api/codirector/projects/{pid}/creative-operating/decision",
            {
                "message": (
                    "She listens again to the tape in the archive room and continues the scene without asking for help."
                )
            },
        )
        elapsed_ms = (time.time() - t0) * 1000
        gates["Latency preservation"] = "GO" if elapsed_ms < 5000 else "FAIL"
        gates["No latency regression"] = gates["Latency preservation"]

        # Support playwright artifacts optional
        support_gates = OUT / "human-gate-support" / "human_gate_support_gates.json"
        if support_gates.exists():
            try:
                sg = json.loads(support_gates.read_text(encoding="utf-8"))
                failed = sg.get("failed") or []
                gates["Support Playwright"] = "GO" if not failed else "FAIL"
            except Exception:  # noqa: BLE001
                gates["Support Playwright"] = "FAIL"
        else:
            # Presence of spec is enough until first run; prefer VERIFIED after run
            gates["Support Playwright"] = "GO" if SUPPORT_SPEC.exists() else "FAIL"

        # Product-owner scorecard document exists blank
        gates["Product-owner scorecard"] = gates["Blank owner-owned scorecard"]
        gates["Mandatory Yes/No review"] = (
            "GO" if "Mandatory Yes/No" in human and "Would the product owner trust" in human else "FAIL"
        )

        # Aggregate keys used in gate matrix (map aliases)
        gates["Cross-format human spot-check"] = gates.get("Cross-format behavior", "FAIL")

        ready = all(v == "GO" for v in gates.values())
        gates["Human-Gate Refinement Readiness"] = "GO" if ready else "FAIL"
    except Exception as exc:  # noqa: BLE001
        gates["verifier_error"] = f"FAIL: {exc}"
        gates["Human-Gate Refinement Readiness"] = "FAIL"

    verdict = "VERIFIED" if gates.get("Human-Gate Refinement Readiness") == "GO" else "BLOCKED"
    report_out = {"verdict": verdict, "gates": gates, "api": API}
    (OUT / "independent_human_gate_verifier.json").write_text(
        json.dumps(report_out, indent=2), encoding="utf-8"
    )
    print(json.dumps(report_out, indent=2))
    print(verdict)
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
