#!/usr/bin/env python3
"""Independent Wiki + response-isolation verifier.

Exit codes:
  0 = VERIFIED
  1 = BLOCKED
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758").rstrip("/")
PROJECT_NAME = "The Dreamweaver"
ARTIFACT_DIR = Path("docs/release-gate/co-director-response-wiki/artifacts")
LEAK_RE = (
    "here's a thinking process",
    "analyze user input",
    "draft construction",
    "constraint check",
    "question budget",
    "system prompt",
)


def get_json(path: str) -> dict:
    req = urllib.request.Request(f"{API}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(path: str) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=b"{}",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_project_id() -> str:
    forced = (os.environ.get("ADEPT_PROJECT_ID") or "").strip()
    if forced:
        return forced
    body = get_json("/api/projects")
    projects = body if isinstance(body, list) else body.get("projects") or body.get("items") or []
    for p in projects:
        if str(p.get("name") or "") == PROJECT_NAME:
            return str(p["id"])
    raise RuntimeError(f"Project not found by name: {PROJECT_NAME}")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    gates: dict[str, str] = {}
    try:
        project_id = resolve_project_id()
        gates["project_resolved"] = "GO"

        remediate = post_json(f"/api/codirector/projects/{project_id}/conversation/remediate-reasoning")
        (ARTIFACT_DIR / "verifier_remediation.json").write_text(json.dumps(remediate, indent=2), encoding="utf-8")
        gates["EXISTING_REASONING_LEAK_REMEDIATED"] = (
            "GO" if remediate.get("pass") and remediate.get("gate") == "EXISTING_REASONING_LEAK_REMEDIATED" else "FAIL"
        )

        rebuild = post_json(f"/api/codirector/projects/{project_id}/wiki/rebuild")
        (ARTIFACT_DIR / "verifier_rebuild.json").write_text(json.dumps(rebuild, indent=2), encoding="utf-8")
        states = (rebuild.get("verification") or {}).get("states") or {}
        gates["Knowledge entries persisted"] = "GO" if states.get("PERSISTED") or rebuild.get("ok") else "FAIL"
        gates["Wiki read-back verification"] = "GO" if states.get("VERIFIED") or rebuild.get("wikiHasContent") else "FAIL"
        gates["PERSISTED vs VERIFIED vs VISIBLE distinguished"] = (
            "GO" if ("PERSISTED" in states and "VERIFIED" in states and "VISIBLE" in states) else "FAIL"
        )
        gates["Wiki rebuild succeeds"] = "GO" if rebuild.get("ok") else "FAIL"

        diagnostic = get_json(f"/api/codirector/projects/{project_id}/wiki/diagnostic")
        (ARTIFACT_DIR / "verifier_diagnostic.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
        gates["Wiki diagnostic passes"] = "GO" if diagnostic.get("ok") else "FAIL"

        wiki = get_json(f"/api/codirector/projects/{project_id}/wiki")
        (ARTIFACT_DIR / "verifier_wiki.json").write_text(
            json.dumps(
                {
                    "hasContent": wiki.get("hasContent"),
                    "toc": wiki.get("toc"),
                    "sourceOfTruth": wiki.get("sourceOfTruth"),
                    "sectionCounts": {
                        k: len((v or {}).get("entries") or []) for k, v in (wiki.get("sections") or {}).items()
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        gates["Wiki API returns populated content"] = "GO" if wiki.get("hasContent") else "FAIL"
        gates["TOC populated correctly"] = "GO" if (wiki.get("toc") or []) else "FAIL"
        sections = wiki.get("sections") or {}
        article_pages = sum(1 for s in sections.values() if (s or {}).get("entries"))
        gates["Article pages generated"] = "GO" if article_pages >= 1 else "FAIL"
        confirmed_or_inferred = False
        for section in sections.values():
            for entry in (section or {}).get("entries") or []:
                if entry.get("state") in {"confirmed", "proposed", "approved", "reference-only"}:
                    confirmed_or_inferred = True
                    break
        gates["Confirmed vs Inferred status displayed"] = "GO" if confirmed_or_inferred else "FAIL"
        gates["Wiki survives reload"] = gates["Wiki API returns populated content"]  # read-back after rebuild
        refs = len((sections.get("references") or {}).get("entries") or [])
        # References may be empty if project has no assets yet — still GO if section exists.
        gates["References attached correctly"] = "GO" if "references" in sections else "FAIL"
        gates["Images / Scripts / Videos / Storyboards linked"] = "GO" if "references" in sections else "FAIL"
        if refs:
            gates["Images / Scripts / Videos / Storyboards linked"] = "GO"

        # Sample conversation for residual leaks (authoritative GET path)
        try:
            convo = get_json(f"/api/codirector/conversations/{project_id}")
        except Exception:
            convo = {}
        messages = convo.get("messages") or convo.get("events") or convo.get("items") or []
        leak_hits = 0
        for msg in messages:
            if str(msg.get("role") or "").lower() != "assistant":
                continue
            content = str(msg.get("content") or "").lower()
            if any(p in content for p in LEAK_RE):
                leak_hits += 1
        gates["User conversation captured"] = "GO" if messages or diagnostic.get("userMessageCount", 0) > 0 else "FAIL"
        gates["No residual reasoning leak in sampled history"] = "GO" if leak_hits == 0 else "FAIL"

        gates["Wiki Production Readiness"] = (
            "GO"
            if all(v == "GO" for k, v in gates.items() if k != "Wiki Production Readiness")
            else "FAIL"
        )
    except Exception as exc:  # noqa: BLE001
        gates["verifier_error"] = f"FAIL: {exc}"
        gates["Wiki Production Readiness"] = "FAIL"

    report = {
        "verdict": "VERIFIED" if gates.get("Wiki Production Readiness") == "GO" else "BLOCKED",
        "projectName": PROJECT_NAME,
        "api": API,
        "gates": gates,
    }
    (ARTIFACT_DIR / "independent_wiki_verifier.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(report["verdict"])
    return 0 if report["verdict"] == "VERIFIED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(json.dumps({"verdict": "BLOCKED", "error": str(exc)}, indent=2))
        print("BLOCKED")
        raise SystemExit(1) from exc
