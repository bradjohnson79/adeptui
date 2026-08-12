"""Independent verifier for the Story Summary Editor capability.

Asserts every mandatory gate by inspecting the package, contracts, laws,
specialist registration, and (when a Beta target is reachable) the live
compiled Wiki. Prints a binary VERIFIED | BLOCKED verdict.

Usage:
    python scripts/verify_story_summary_editor.py
    ADEPT_BETA_TARGET=1 python scripts/verify_story_summary_editor.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any

API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758")
BETA = os.environ.get("ADEPT_BETA_TARGET", "0") == "1"

GATES: dict[str, str] = {}


def gate(name: str, ok: bool, detail: str = "") -> None:
    GATES[name] = "GO" if ok else "NO-GO"
    if detail:
        print(f"[{'GO' if ok else 'NO-GO'}] {name}: {detail}")
    else:
        print(f"[{'GO' if ok else 'NO-GO'}] {name}")


# --- Static (no Beta required) checks -----------------------------------------


def check_static() -> None:
    try:
        from app.codirector.intelligence.contracts import CONTRACTS

        gate(
            "Story Summary Editor registered",
            "story-summary-editor" in CONTRACTS,
        )
    except Exception as exc:  # noqa: BLE001
        gate("Story Summary Editor registered", False, str(exc))

    try:
        from app.codirector.prompts.loader import get_prompt_library

        library = get_prompt_library()
        record = library.get("story-summary-editor")
        gate("Specialist prompt file loaded", record is not None)
        if record:
            body = record.body.lower()
            gate(
                "Editorial doctrine present",
                "editorial" in body and "no technical language" in body,
            )
            gate(
                "Hard laws enumerated in prompt",
                "summary_depth_must_not_exceed_project_knowledge" in body
                and "no_technical_language_in_story_summaries" in body,
            )
            gate(
                "Pitch/marketing voice forbidden",
                "promotional" in body and "pitch" in body,
            )
    except Exception as exc:  # noqa: BLE001
        gate("Specialist prompt file loaded", False, str(exc))

    try:
        from app.codirector.wiki_intelligence.compiled.story_summary_editor import (  # noqa: F401
            CompiledStorySummary,
            StorySummarySource,
            edit_story_summary,
            conservative_fallback,
            validate,
            normalize_themes,
            logline_readiness,
            long_summary_readiness,
            short_summary_readiness,
            should_render,
        )

        gate("story_summary_editor package importable", True)
    except Exception as exc:  # noqa: BLE001
        gate("story_summary_editor package importable", False, str(exc))

    try:
        from app.codirector.wiki_intelligence.compiled.story_summary_editor import (
            CompiledStorySummary,
            StorySummarySource,
            validate,
        )

        src = StorySummarySource(projectId="t", confirmedFacts=["Barnes enters DW6."], confirmedCharacterRoles=["Barnes"])
        bad = CompiledStorySummary(shortSummary="2 scenes parsed; 3 characters identified.")
        violations = validate(bad, src)
        gate("No technical jargon validator", any("NO_TECHNICAL_LANGUAGE" in v for v in violations))
    except Exception as exc:  # noqa: BLE001
        gate("No technical jargon validator", False, str(exc))

    try:
        from app.codirector.wiki_intelligence.compiled.story_summary_editor import (
            CompiledStorySummary,
            StorySummarySource,
            validate,
        )

        src = StorySummarySource(projectId="t", confirmedFacts=["Barnes enters DW6."], confirmedCharacterRoles=["Barnes"])
        bad = CompiledStorySummary(longSummary="This gripping journey follows Barnes.")
        violations = validate(bad, src)
        gate("Editorial-not-promotional validator", any("EDITORIAL_NOT_PROMOTIONAL" in v for v in violations))
    except Exception as exc:  # noqa: BLE001
        gate("Editorial-not-promotional validator", False, str(exc))

    try:
        from app.codirector.wiki_intelligence.compiled.story_summary_editor import (
            CompiledStorySummary,
            StorySummarySource,
            validate,
        )

        src = StorySummarySource(projectId="t", confirmedFacts=["Barnes enters DW6."], confirmedCharacterRoles=["Barnes"])
        bad = CompiledStorySummary(longSummary="Barnes confronts the villain Voss.")
        violations = validate(bad, src)
        gate("Evidence-grounded (no invention) validator", any("SUMMARY_DEPTH_MUST_NOT_EXCEED" in v for v in violations))
    except Exception as exc:  # noqa: BLE001
        gate("Evidence-grounded (no invention) validator", False, str(exc))

    try:
        from app.codirector.wiki_intelligence.compiled.story_summary_editor import normalize_themes

        out = normalize_themes(
            ["Theme: consciousness: Thematic thread present in the narration: consciousness.", "consciousness", "Trust"]
        )
        gate("Theme deduplication", out == ["Consciousness", "Trust"])
    except Exception as exc:  # noqa: BLE001
        gate("Theme deduplication", False, str(exc))

    try:
        from app.codirector.wiki_intelligence.compiled.story_summary_editor import (
            StorySummarySource,
            conservative_fallback,
        )

        src = StorySummarySource(projectId="t", confirmedFacts=["A single sparse fact."])
        out = conservative_fallback(src)
        gate("Conservative fallback prefers omission", out.longSummary == "" and out.editorMode == "deterministic")
    except Exception as exc:  # noqa: BLE001
        gate("Conservative fallback prefers omission", False, str(exc))

    try:
        from app.codirector.wiki_intelligence.compiled.story_summary_editor import (
            StorySummarySource,
            logline_readiness,
            long_summary_readiness,
            should_render,
        )

        sparse = StorySummarySource(projectId="t", confirmedFacts=["A fact."])
        gate(
            "Per-section independent readiness",
            should_render(logline_readiness(sparse)) is False
            and should_render(long_summary_readiness(sparse)) is False,
        )
    except Exception as exc:  # noqa: BLE001
        gate("Per-section independent readiness", False, str(exc))

    try:
        from app.codirector.wiki_intelligence.compiled.page_compiler import compile_wiki_bundle_async

        gate("Async compile path wired", compile_wiki_bundle_async is not None)
    except Exception as exc:  # noqa: BLE001
        gate("Async compile path wired", False, str(exc))

    try:
        from app.routers.codirector import router

        paths = {getattr(r, "path", "") for r in router.routes}
        gate(
            "Creator controls (refine + correct) routes",
            "/codirector/projects/{project_id}/wiki/story-summary/refine" in paths
            and "/codirector/projects/{project_id}/wiki/story-summary/correct" in paths,
        )
    except Exception as exc:  # noqa: BLE001
        gate("Creator controls (refine + correct) routes", False, str(exc))


# --- Live Beta checks ---------------------------------------------------------


def _get(url: str) -> Any | None:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def check_live() -> None:
    if not BETA:
        print("(Skipping live Beta checks: ADEPT_BETA_TARGET not set)")
        return
    health = _get(f"{API}/api/health")
    if not health:
        print(f"(Beta API not reachable at {API}; skipping live checks)")
        return
    gate("Beta API reachable", True)

    projects = _get(f"{API}/api/projects")
    if not projects:
        gate("Live compiled summary reachable", False, "no projects")
        return
    items = projects if isinstance(projects, list) else projects.get("projects", [])
    if not items:
        gate("Live compiled summary reachable", False, "empty projects")
        return
    project_id = (items[0].get("id") if isinstance(items[0], dict) else None) or ""
    if not project_id:
        gate("Live compiled summary reachable", False, "no project id")
        return

    wiki = _get(f"{API}/api/codirector/projects/{project_id}/wiki")
    if not wiki:
        gate("Live compiled summary reachable", False, "no wiki")
        return
    summary = wiki.get("compiledStorySummary") or wiki.get("storySummary") or {}
    gate("Live compiled summary reachable", bool(summary))
    if summary:
        blob = f"{summary.get('logline','')} {summary.get('shortSummary','')} {summary.get('longSummary','')}".lower()
        gate("Live: no technical jargon", not any(t in blob for t in ("scenes parsed", "characters identified", "pipeline")))
        gate("Live: no promotional style", not any(p in blob for p in ("gripping journey", "captivating tale")))
        gate("Live: editorMode recorded", summary.get("editorMode") in {"llm", "deterministic"})


def main() -> int:
    print("=== Story Summary Editor Independent Verifier ===")
    check_static()
    check_live()
    print("\n=== Gate summary ===")
    for name, status in GATES.items():
        print(f"  {status}: {name}")
    all_go = all(v == "GO" for v in GATES.values())
    print(f"\nVerdict: {'VERIFIED' if all_go else 'BLOCKED'}")
    return 0 if all_go else 1


if __name__ == "__main__":
    sys.exit(main())
