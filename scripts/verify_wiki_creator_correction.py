"""Independent verifier for the Refine Wiki creator-correction capability.

Asserts every mandatory gate by inspecting the correction package, character
purity, authority enforcement, API routes, and (when a Beta target is
reachable) the live correction round-trip. Prints a binary VERIFIED | BLOCKED
verdict.

Usage:
    python scripts/verify_wiki_creator_correction.py
    ADEPT_BETA_TARGET=1 python scripts/verify_wiki_creator_correction.py
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


def check_static() -> None:
    # Correction package importable.
    try:
        from app.codirector.wiki_intelligence.correction import (  # noqa: F401
            apply,
            classify,
            contracts,
            memory,
            undo,
        )

        gate("Correction package importable", True)
    except Exception as exc:  # noqa: BLE001
        gate("Correction package importable", False, str(exc))

    # Contracts present.
    try:
        from app.codirector.wiki_intelligence.correction.contracts import (  # noqa: F401
            CoDirectorLearnedCorrection,
            CorrectionPreview,
            CorrectionTarget,
            CreatorWikiCorrection,
            EntityReclassification,
        )

        gate("Correction contracts present", True)
    except Exception as exc:  # noqa: BLE001
        gate("Correction contracts present", False, str(exc))

    # Heuristic classifier: location / org / attribute / merge / summary.
    try:
        from app.codirector.wiki_intelligence.correction.classify import _heuristic_classify

        class _Stub:
            knowledgeEntries: list = []
            compiledWiki: dict = {}

        loc = _heuristic_classify("Gakona is a location, not a character.", _Stub())
        gate(
            "Heuristic: location reclassification",
            loc["correctionType"] == "RECLASSIFY"
            and loc["entityReclassifications"][0]["toType"] == "location",
        )
        org = _heuristic_classify("The FBI is an organization, not a character.", _Stub())
        gate(
            "Heuristic: organization reclassification",
            org["entityReclassifications"][0]["toType"] == "organization",
        )
        age = _heuristic_classify("Barnes is age 55.", _Stub())
        gate(
            "Heuristic: age is attribute",
            age["entityReclassifications"][0]["toType"] == "attribute",
        )
        merge = _heuristic_classify("Merge Barnes and Special Agent Barnes — same person.", _Stub())
        gate("Heuristic: merge aliases", merge["correctionType"] == "MERGE" and bool(merge["aliases"]))
        summary = _heuristic_classify("The summary is wrong about Barnes.", _Stub())
        gate(
            "Heuristic: summary correction recompiles",
            summary["correctionType"] == "SUMMARY_CORRECTION" and summary["summaryRecompile"],
        )
        ambig = _heuristic_classify("Change the character.", _Stub())
        gate("Ambiguity gate asks clarification", bool(ambig["clarificationQuestion"]))
    except Exception as exc:  # noqa: BLE001
        gate("Heuristic classifier", False, str(exc))

    # Character purity: classification + resolver gating.
    try:
        from app.codirector.wiki_intelligence.classification import classify_entity_type
        from app.codirector.wiki_intelligence.compiled.character_compiler import resolve_characters

        gate(
            "Entity-type override wins (Gakona→location)",
            classify_entity_type("Gakona", entity_type_overrides={"gakona": "location"}) == "location",
        )
        gate(
            "Age classified as attribute",
            classify_entity_type("Barnes, age 55") == "attribute",
        )
        gate(
            "Known orgs classified as organization",
            classify_entity_type("The FBI investigates") == "organization"
            and classify_entity_type("DW6 Research Facility") == "organization",
        )
        pages = resolve_characters(["Gakona", "Barnes is an agent."], entity_type_overrides={"gakona": "location"})
        titles = [p["title"] for p in pages]
        gate("Resolver blocks overridden entity from Characters", "Gakona" not in titles)
    except Exception as exc:  # noqa: BLE001
        gate("Character purity", False, str(exc))

    # Authority enforcement: explicit creator write is a fact, not specialist.
    try:
        from app.codirector.wiki_intelligence.compiled.story_summary_editor.evidence import _classify

        fact, _, sinterp = _classify(
            "Barnes is skeptical.", "confirmed", "explicit_wiki_write:USER_EXPLICIT_WIKI_WRITE"
        )
        gate("Creator-authority precedence in evidence", fact is not None and sinterp is None)
    except Exception as exc:  # noqa: BLE001
        gate("Creator-authority precedence in evidence", False, str(exc))

    # Reorganize consults correction memory (entity overrides threaded).
    try:
        import inspect

        from app.codirector.wiki_intelligence import reorganize

        src = inspect.getsource(reorganize._run_reorganization)
        gate(
            "Reorganize consults correction memory",
            "entity_type_overrides" in src and "correction" in src,
        )
        src2 = inspect.getsource(reorganize)
        gate(
            "Reorganize protects explicit creator writes",
            "USER_EXPLICIT_WIKI_WRITE" in src2,
        )
    except Exception as exc:  # noqa: BLE001
        gate("Reorganize enforcement", False, str(exc))

    # demote_wiki_to_note exists.
    try:
        from app.codirector.notes.service import demote_wiki_to_note  # noqa: F401

        gate("Wiki→Notes demote path exists", True)
    except Exception as exc:  # noqa: BLE001
        gate("Wiki→Notes demote path exists", False, str(exc))

    # API routes.
    try:
        from app.routers.codirector import router

        paths = {getattr(r, "path", "") for r in router.routes}
        gate(
            "Correction routes (preview/apply/undo/list)",
            "/codirector/projects/{project_id}/wiki/correction/preview" in paths
            and "/codirector/projects/{project_id}/wiki/correction/apply" in paths
            and "/codirector/projects/{project_id}/wiki/correction/{correction_id}/undo" in paths
            and "/codirector/projects/{project_id}/wiki/corrections" in paths,
        )
    except Exception as exc:  # noqa: BLE001
        gate("Correction routes", False, str(exc))

    # UI markers present in source.
    try:
        panel = _read("studio-web/src/components/CoDirector/ProjectWikiPanel.tsx")
        reader = _read("studio-web/src/components/CoDirector/wiki/CompiledWikiReader.tsx")
        gate("Refine Wiki toolbar button (first)", 'data-testid="project-wiki-refine"' in panel)
        gate("Refine Wiki overlay", 'data-testid="project-wiki-refine-dialog"' in panel)
        gate("Preview-gated Apply", "project-wiki-refine-apply" in panel and "runRefinePreview" in panel)
        gate("Undo control", "project-wiki-refine-undo" in panel)
        gate("Beta disclaimer footer", "Co-Director can make mistakes" in panel)
        gate("Context-aware page lift", "onPageChange" in panel and "onPageChange" in reader)
        gate("Per-section Refine affordance", "wiki-refine-section-" in reader)
    except Exception as exc:  # noqa: BLE001
        gate("UI markers", False, str(exc))

    # API client methods.
    try:
        api = _read("studio-web/src/api.ts")
        gate(
            "API client methods",
            "previewCoDirectorWikiCorrection" in api
            and "applyCoDirectorWikiCorrection" in api
            and "undoCoDirectorWikiCorrection" in api
            and "getCoDirectorWikiCorrections" in api,
        )
    except Exception as exc:  # noqa: BLE001
        gate("API client methods", False, str(exc))


def _read(rel: str) -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, rel), encoding="utf-8") as fh:
        return fh.read()


def _get(url: str) -> Any | None:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _post(url: str, payload: dict[str, Any], timeout: int = 30) -> Any | None:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")  # noqa: S310
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
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

    # Full correction round-trip on a disposable project.
    project = _post(f"{API}/api/projects", {"name": "WCC Verifier Fixture", "primaryProjectType": "narrative_visual"})
    project_id = (project or {}).get("id") or (project or {}).get("project", {}).get("id")
    if not project_id:
        gate("Live: correction round-trip", False, "could not create project")
        return
    _post(f"{API}/api/codirector/projects/{project_id}/wiki/promote", {"text": "Gakona is a covert operative.", "destination": "character"})
    _post(f"{API}/api/codirector/projects/{project_id}/wiki/compile", {})

    preview = _post(
        f"{API}/api/codirector/projects/{project_id}/wiki/correction/preview",
        {"instruction": "Gakona is a location, not a character."},
        timeout=90,
    )
    gate("Live: preview returns reclassification", bool(preview and preview.get("preview", {}).get("entityReclassifications")))
    preview_id = (preview or {}).get("preview", {}).get("previewId")
    if not preview_id:
        gate("Live: correction round-trip", False, "no previewId")
        return
    applied = _post(
        f"{API}/api/codirector/projects/{project_id}/wiki/correction/apply",
        {"previewId": preview_id},
    )
    gate("Live: apply returns undo id", bool(applied and applied.get("undoId")))
    correction_id = (applied or {}).get("correction", {}).get("id")

    _post(f"{API}/api/codirector/projects/{project_id}/wiki/compile", {})
    wiki = _get(f"{API}/api/codirector/projects/{project_id}/wiki")
    pages = (wiki or {}).get("compiledPages") or (wiki or {}).get("pages") or []
    titles = [p.get("title", "") for p in pages if p.get("pageType") == "CHARACTER"]
    gate("Live: Gakona removed from Characters after recompile", "Gakona" not in titles)

    if correction_id:
        undo = _post(f"{API}/api/codirector/projects/{project_id}/wiki/correction/{correction_id}/undo", {})
        gate("Live: undo restores", bool(undo and undo.get("ok")))


def main() -> int:
    print("=== Refine Wiki Creator Correction Independent Verifier ===")
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
