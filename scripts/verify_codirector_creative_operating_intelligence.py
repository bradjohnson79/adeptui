#!/usr/bin/env python3
"""Independent Creative Operating Intelligence verifier → VERIFIED | BLOCKED."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758").rstrip("/")
PROJECT_NAME = "The Dreamweaver"
OUT = Path("docs/release-gate/co-director-creative-operating-intelligence/artifacts")


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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gates: dict[str, str] = {}
    try:
        pid = resolve_project()
        gates["project_resolved"] = "GO"

        # Specialist prompt present
        steward_prompt = Path("studio-api/app/codirector/prompts/specialists/project-bible-steward.md")
        gates["Project Bible Steward prompt"] = "GO" if steward_prompt.exists() else "FAIL"

        # Package contracts
        pkg = Path("studio-api/app/codirector/creative_operating/contracts.py")
        gates["Creative decision contracts"] = "GO" if pkg.exists() else "FAIL"

        # Initiative dial
        put_body = put(
            f"/api/codirector/projects/{pid}/creative-operating/initiative",
            {"initiativeLevel": "QUIET_PARTNER"},
        )
        gates["Initiative dial"] = "GO" if put_body.get("initiativeLevel") == "QUIET_PARTNER" else "FAIL"

        state = get(f"/api/codirector/projects/{pid}/creative-operating")
        gates["Creative operating persistence"] = "GO" if state.get("projectId") == pid else "FAIL"

        # Listening / question budget
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
        gates["Listening mode"] = "GO" if dec.get("listeningOnly") else "FAIL"
        gates["Question budget"] = "GO" if dec.get("questionBudget") == 0 else "FAIL"
        gates["Five minds"] = "GO" if (dec.get("mindNotes") or {}).get("companion") else "FAIL"
        gates["Decision loop"] = "GO" if len(dec.get("loopCompleted") or []) >= 8 else "FAIL"

        # Proactive
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
        gates["Proactive producer budget"] = (
            "GO"
            if int(pdec.get("questionBudget") if pdec.get("questionBudget") is not None else 0) >= 1
            and not pdec.get("listeningOnly")
            else "FAIL"
        )

        # Canon safety — speculative not CONFIRMED
        bad = [
            k
            for k in (pdec.get("importantNewKnowledge") or [])
            if k.get("kind") in {"INTERPRETATION", "POSSIBILITY"} and k.get("canonState") in {"CONFIRMED", "LOCKED"}
        ]
        gates["Canon safety"] = "GO" if not bad else "FAIL"

        # Script intelligence
        script = post(
            f"/api/codirector/projects/{pid}/creative-operating/script/analyze",
            {
                "text": "EPISODE 1\n\nINT. LAB - NIGHT\n\nAGENT HALE\nWe start here.\n",
                "filename": "ep1.txt",
                "installmentHint": "Episode 1",
            },
        )
        gates["Script intelligence"] = "GO" if (script.get("breakdown") or {}).get("scenes") else "FAIL"

        # Disagreement synthesis
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
        gates["Specialists not creator-facing"] = (
            "GO" if "story-editor" not in synth.lower() else "FAIL"
        )

        # Format awareness — documentary disposable
        doc = post(
            "/api/projects",
            {
                "name": f"COI-Verify-Doc-{os.getpid()}",
                "primary_project_type": "documentary",
            },
        )
        doc_id = str(doc.get("id") or (doc.get("project") or {}).get("id") or "")
        if not doc_id:
            gates["Format awareness"] = "FAIL"
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
            gates["Format awareness"] = (
                "GO" if fmt != "EPISODIC_SERIES" and "Episode 2" not in suggestion else "FAIL"
            )

        # creatorFacingAllowed hard rule via roster artifact
        sys.path.insert(0, str(Path("studio-api").resolve()))
        try:
            from app.codirector.intelligence.specialist_policies import authoritative_roster

            roster = authoritative_roster()
            steward = next((c for c in roster if c.specialistId == "project-bible-steward"), None)
            gates["Steward registered"] = "GO" if steward else "FAIL"
            gates["creatorFacingAllowed=false"] = (
                "GO" if steward and steward.creatorFacingAllowed is False else "FAIL"
            )
            if any(getattr(c, "creatorFacingAllowed", False) for c in roster):
                gates["creatorFacingAllowed=false"] = "FAIL"
        except Exception as exc:  # noqa: BLE001
            gates["Steward registered"] = f"FAIL: {exc}"
            gates["creatorFacingAllowed=false"] = "FAIL"

        # Playwright artifact optional signal
        cert_gates = OUT / "cert_gates.json"
        if cert_gates.exists():
            try:
                cg = json.loads(cert_gates.read_text(encoding="utf-8"))
                failed = cg.get("failed") or []
                gates["Playwright cert artifacts"] = "GO" if not failed else "FAIL"
            except Exception:  # noqa: BLE001
                gates["Playwright cert artifacts"] = "FAIL"
        else:
            gates["Playwright cert artifacts"] = "FAIL"

        gates["Creative Operating Readiness"] = (
            "GO" if all(v == "GO" for k, v in gates.items() if k != "Creative Operating Readiness") else "FAIL"
        )
    except Exception as exc:  # noqa: BLE001
        gates["verifier_error"] = f"FAIL: {exc}"
        gates["Creative Operating Readiness"] = "FAIL"

    report = {
        "verdict": "VERIFIED" if gates.get("Creative Operating Readiness") == "GO" else "BLOCKED",
        "gates": gates,
        "api": API,
    }
    (OUT / "independent_creative_operating_verifier.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    print(report["verdict"])
    return 0 if report["verdict"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
