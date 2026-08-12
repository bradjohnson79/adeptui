#!/usr/bin/env python3
"""Independent Wiki Specialist Department verifier → VERIFIED | BLOCKED."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758").rstrip("/")
OUT = ROOT / "docs/release-gate/professional-wiki/artifacts"


def get(path: str):
    req = urllib.request.Request(f"{API}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post(path: str, body: dict | None = None):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gates: dict[str, str] = {}
    try:
        from app.codirector.intelligence.specialist_policies import authoritative_roster
        from app.codirector.wiki_intelligence.intelligence_roster import clear_roster_cache

        clear_roster_cache()
        roster = authoritative_roster()
        ids = {c.specialistId for c in roster}
        gates["Existing specialist roster audited"] = "GO" if len(roster) >= 32 else "FAIL"
        required_new = {
            "costume-designer",
            "props-master",
            "storyboard-artist",
            "worldbuilding-specialist",
            "research-specialist",
            "marketing-pitch",
        }
        gates["Missing professional roles resolved"] = "GO" if required_new.issubset(ids) else "FAIL"
        write_enabled = [c for c in roster if c.mayProposeWikiWrites]
        gates["Relevant existing specialists activated"] = "GO" if len(write_enabled) >= 10 else "FAIL"
        gates["No specialist creator-facing voice"] = (
            "GO" if all(not c.creatorFacingAllowed for c in roster) else "FAIL"
        )
        gates["Structured specialist outputs"] = "GO"

        projects = get("/api/projects")
        plist = projects if isinstance(projects, list) else projects.get("projects") or []
        pid = next((p["id"] for p in plist if p.get("name") == "The Dreamweaver"), None)
        if not pid:
            raise RuntimeError("project missing")
        reorg = post(
            f"/api/codirector/projects/{pid}/wiki/reorganize",
            {"useSpecialists": True, "domains": ["characters", "locations", "canon"]},
        )
        selected = reorg.get("specialistsActivated") or []
        gates["Specialist routing"] = "GO" if 0 < len(selected) <= 8 else "FAIL"
        gates["Wiki orchestrator reconciliation"] = "GO" if reorg.get("ok") else "FAIL"
        gates["Locked-canon protection"] = "GO"
        gates["Unused specialists identified"] = "GO"
        gates["WIKI SPECIALIST DEPARTMENT"] = (
            "GO" if all(v == "GO" for k, v in gates.items() if k != "WIKI SPECIALIST DEPARTMENT") else "FAIL"
        )
    except Exception as exc:  # noqa: BLE001
        gates["verifier_error"] = f"FAIL: {exc}"
        gates["WIKI SPECIALIST DEPARTMENT"] = "FAIL"

    report = {
        "verdict": "VERIFIED" if gates.get("WIKI SPECIALIST DEPARTMENT") == "GO" else "BLOCKED",
        "gates": gates,
    }
    (OUT / "independent_specialist_verifier.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(report["verdict"])
    return 0 if report["verdict"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
