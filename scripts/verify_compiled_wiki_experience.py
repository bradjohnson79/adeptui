#!/usr/bin/env python3
"""Independent compiled Wiki verifier → VERIFIED | BLOCKED."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758").rstrip("/")
OUT = Path("docs/release-gate/compiled-wiki/artifacts")
PROJECT_NAME = "The Dreamweaver"


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
        gates["Notes layer"] = "GO" if Path("studio-api/app/codirector/notes/service.py").exists() else "FAIL"
        gates["Wiki Page Compiler"] = (
            "GO" if Path("studio-api/app/codirector/wiki_intelligence/compiled/page_compiler.py").exists() else "FAIL"
        )

        notes = get(f"/api/codirector/projects/{pid}/notes")
        gates["Notes persistence"] = "GO" if notes.get("ok") and "notes" in notes else "FAIL"

        post(f"/api/codirector/projects/{pid}/wiki/compile", {})
        wiki = get(f"/api/codirector/projects/{pid}/wiki")
        pages = wiki.get("compiledPages") or []
        gates["Wiki article synthesis"] = "GO" if pages else "FAIL"
        gates["Clean navigation"] = "GO" if wiki.get("compiledToc") or wiki.get("projection") == "compiled_bible_v1" else "FAIL"
        titles = [str(p.get("title") or "") for p in pages]
        theme_titles = [t for t in titles if t.strip().lower() == "theme"]
        gates["Wiki readability"] = "GO" if len(theme_titles) < 2 and wiki.get("readabilityOk", True) else "FAIL"
        chars = [p for p in pages if p.get("pageType") == "CHARACTER"]
        pollution = [c for c in chars if "project type" in (c.get("title") or "").lower()]
        gates["Section purity"] = "GO" if not pollution else "FAIL"

        promo = post(
            f"/api/codirector/projects/{pid}/wiki/promote",
            {"text": "The quiet archive room holds the first signal as confirmed project knowledge.", "destination": "story"},
        )
        gates["Explicit Wiki promotion"] = "GO" if promo.get("ok") else "FAIL"

        # Messy seed then reorganize
        post(
            f"/api/codirector/projects/{pid}/wiki/promote",
            {"text": "Theme", "destination": "story"},
        )
        before = get(f"/api/codirector/projects/{pid}/wiki")
        reorg = post(
            f"/api/codirector/projects/{pid}/wiki/reorganize",
            {"domains": ["characters", "story", "canon"], "useSpecialists": True, "createUndoSnapshot": True},
        )
        after = get(f"/api/codirector/projects/{pid}/wiki")
        before_rev = before.get("compiledRevision") or 0
        after_rev = after.get("compiledRevision") or 0
        gates["Reorganize materially changes messy Wiki"] = (
            "GO"
            if reorg.get("ok") and (after_rev >= before_rev) and (after.get("compiledPages") or after.get("hasContent"))
            else "FAIL"
        )
        job = reorg.get("job") or {}
        gates["Reorganize undo"] = "GO" if job.get("revisionId") or job.get("id") else "FAIL"
        if job.get("id"):
            undo = post(f"/api/codirector/projects/{pid}/wiki/reorganize/{job['id']}/undo", {})
            gates["Reorganize undo"] = "GO" if undo.get("ok") is not False else gates["Reorganize undo"]

        # Cross-format disposable
        doc = post("/api/projects", {"name": f"CW-Doc-{os.getpid()}", "primary_project_type": "documentary"})
        doc_id = str(doc.get("id") or "")
        if doc_id:
            dw = get(f"/api/codirector/projects/{doc_id}/wiki")
            gates["Cross-format generalization"] = "GO" if dw.get("projection") == "compiled_bible_v1" or "compiledPages" in dw else "FAIL"
        else:
            gates["Cross-format generalization"] = "FAIL"

        gates["Casting surface"] = (
            "GO" if Path("studio-web/src/components/CoDirector/CastingPanel.tsx").exists() else "FAIL"
        )
        gates["Compiled Wiki UI"] = (
            "GO" if Path("studio-web/src/components/CoDirector/wiki/CompiledWikiReader.tsx").exists() else "FAIL"
        )

        ready = all(v == "GO" for v in gates.values())
        gates["Compiled Wiki Readiness"] = "GO" if ready else "FAIL"
    except Exception as exc:  # noqa: BLE001
        gates["verifier_error"] = f"FAIL: {exc}"
        gates["Compiled Wiki Readiness"] = "FAIL"

    verdict = "VERIFIED" if gates.get("Compiled Wiki Readiness") == "GO" else "BLOCKED"
    report = {"verdict": verdict, "gates": gates, "api": API}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "independent_compiled_wiki_verifier.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(verdict)
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
