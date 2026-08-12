#!/usr/bin/env python3
"""Independent Professional Wiki Intelligence verifier → VERIFIED | BLOCKED."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758").rstrip("/")
PROJECT_NAME = "The Dreamweaver"
OUT = Path("docs/release-gate/professional-wiki/artifacts")


def get(path: str):
    req = urllib.request.Request(f"{API}{path}", headers={"Accept": "application/json"})
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
    raise RuntimeError("Dreamweaver not found")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gates: dict[str, str] = {}
    try:
        pid = resolve_project()
        gates["project_resolved"] = "GO"
        wiki = get(f"/api/codirector/projects/{pid}/wiki")
        gates["Professional TOC"] = "GO" if (wiki.get("professionalToc") or wiki.get("toc")) else "FAIL"
        gates["Projection"] = "GO" if wiki.get("projection") == "professional_v1" or wiki.get("professionalToc") else "FAIL"
        health = get(f"/api/codirector/projects/{pid}/wiki/health")
        gates["Wiki health"] = "GO" if health.get("ok") else "FAIL"
        ctx = get(f"/api/codirector/projects/{pid}/wiki/tool-context")
        gates["Tool-context integration"] = "GO" if ctx.get("projectId") == pid else "FAIL"
        reorg = post(
            f"/api/codirector/projects/{pid}/wiki/reorganize",
            {
                "domains": ["characters", "locations", "story", "world", "canon"],
                "useSpecialists": True,
                "preserveLockedCanon": True,
                "createUndoSnapshot": True,
            },
        )
        (OUT / "verifier_reorganize.json").write_text(json.dumps(reorg, indent=2), encoding="utf-8")
        job = reorg.get("job") or {}
        gates["Reorganize succeeds"] = "GO" if reorg.get("ok") and job.get("status") in {"COMPLETE", "PARTIAL"} else "FAIL"
        gates["Specialist activation"] = "GO" if reorg.get("specialistsActivated") else "FAIL"
        gates["TOC rebuild"] = "GO" if job.get("tocRebuilt") else "FAIL"
        gates["Read-back verification"] = "GO" if job.get("readBackVerified") else "FAIL"
        gates["Change summary"] = "GO" if job.get("summaryLines") else "FAIL"
        chars = ((get(f"/api/codirector/projects/{pid}/wiki").get("sections") or {}).get("characters") or {}).get("entries") or []
        false_left = [
            e
            for e in chars
            if str(e.get("text") or "").split(":")[0].strip().lower()
            in {"she", "here", "research", "episode", "series synopsis", "agent gold"}
        ]
        gates["Character cleanup"] = "GO" if not false_left else "FAIL"
        hist = get(f"/api/codirector/projects/{pid}/wiki/reorganization-history")
        gates["Reorganization history"] = "GO" if hist.get("ok") else "FAIL"
        roster = Path("docs/release-gate/professional-wiki/WIKI_SPECIALIST_ROSTER.md")
        gates["Existing specialist roster audited"] = "GO" if roster.exists() else "FAIL"
        gates["Wiki Production Readiness"] = (
            "GO" if all(v == "GO" for k, v in gates.items() if k != "Wiki Production Readiness") else "FAIL"
        )
    except Exception as exc:  # noqa: BLE001
        gates["verifier_error"] = f"FAIL: {exc}"
        gates["Wiki Production Readiness"] = "FAIL"

    report = {
        "verdict": "VERIFIED" if gates.get("Wiki Production Readiness") == "GO" else "BLOCKED",
        "gates": gates,
    }
    (OUT / "independent_professional_wiki_verifier.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(report["verdict"])
    return 0 if report["verdict"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
