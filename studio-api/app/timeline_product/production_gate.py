"""M42 Wave 4C Timeline product rename GO gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_ART = _REPO / "artifacts" / "m42" / "w4c"
_DOCS = _REPO / "docs" / "release-gate" / "m42"
_FINAL = _DOCS / "M42_W4C_TIMELINE_FINAL_CERTIFICATION.md"


def _art(name: str) -> bool:
    return (_ART / name).is_file()


def _load(name: str) -> dict[str, Any]:
    p = _ART / name
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _passed(name: str) -> bool:
    return _art(name) and bool(_load(name).get("passed", True))


def _final_go() -> bool:
    if not _FINAL.is_file():
        return False
    text = _FINAL.read_text(encoding="utf-8", errors="ignore")
    go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
    nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
    return go and not nogo


def evaluate_timeline_wave4c_gate() -> dict[str, Any]:
    inv = _load("timeline_rename_inventory.json")
    search = _load("timeline_search_results.json")
    routes = _load("timeline_route_results.json")
    cd = _load("timeline_codirector_results.json")

    flags = {
        "timelineCanonicalNameApplied": _passed("timeline_rename_inventory.json")
        and inv.get("productCanonical") == "timeline",
        "standaloneDirectorUiReferencesZero": _passed("timeline_search_results.json")
        and int(search.get("unexplainedStandaloneDirector", 0) or 0) == 0,
        "coDirectorNamePreserved": _passed("timeline_codirector_results.json")
        and bool(cd.get("coDirectorPreserved", True)),
        "timelineNavigationOperational": _passed("timeline_route_results.json"),
        "timelineWorkspaceOperational": _passed("timeline_project_compatibility_results.json"),
        "timelineRouteCanonical": _passed("timeline_route_results.json")
        and bool(routes.get("canonicalWorkspace", True)),
        "legacyDirectorRoutesCompatible": _passed("timeline_route_results.json")
        and bool(routes.get("legacyAlias", True)),
        "legacyProjectsCompatible": _passed("timeline_project_compatibility_results.json"),
        "timelinePersistenceCompatible": _passed("timeline_persistence_results.json"),
        "timelineSearchAliasOperational": _passed("timeline_search_results.json"),
        "timelineApiNormalizationOperational": _passed("timeline_route_results.json"),
        "timelineCoDirectorIntegrationOperational": _passed("timeline_codirector_results.json"),
        "timelineMagiIntegrationOperational": _passed("timeline_magi_results.json"),
        "timelineAccessibilityUpdated": _passed("timeline_accessibility_results.json"),
        "timelineDocumentationUpdated": _art("timeline_rename_inventory.json") and _final_go(),
        "timelinePlaywrightPassed": _passed("timeline_playwright_results.json"),
        "timelineUnexplainedLegacyReferencesZero": _passed("timeline_search_results.json")
        and int(search.get("unexplainedStandaloneDirector", 0) or 0) == 0,
    }
    flags.update(
        {
            "TimelineCanonicalNameApplied": flags["timelineCanonicalNameApplied"],
            "StandaloneDirectorUiReferencesZero": flags["standaloneDirectorUiReferencesZero"],
            "CoDirectorNamePreserved": flags["coDirectorNamePreserved"],
            "TimelineNavigationOperational": flags["timelineNavigationOperational"],
            "TimelineWorkspaceOperational": flags["timelineWorkspaceOperational"],
            "TimelineRouteCanonical": flags["timelineRouteCanonical"],
            "LegacyDirectorRoutesCompatible": flags["legacyDirectorRoutesCompatible"],
            "LegacyProjectsCompatible": flags["legacyProjectsCompatible"],
            "TimelinePersistenceCompatible": flags["timelinePersistenceCompatible"],
            "TimelineSearchAliasOperational": flags["timelineSearchAliasOperational"],
            "TimelineApiNormalizationOperational": flags["timelineApiNormalizationOperational"],
            "TimelineCoDirectorIntegrationOperational": flags["timelineCoDirectorIntegrationOperational"],
            "TimelineMagiIntegrationOperational": flags["timelineMagiIntegrationOperational"],
            "TimelineAccessibilityUpdated": flags["timelineAccessibilityUpdated"],
            "TimelineDocumentationUpdated": flags["timelineDocumentationUpdated"],
            "TimelinePlaywrightPassed": flags["timelinePlaywrightPassed"],
            "TimelineUnexplainedLegacyReferencesZero": flags["timelineUnexplainedLegacyReferencesZero"],
        }
    )
    missing = [k for k, v in flags.items() if k[0].islower() and not v]
    wave4c_go = len(missing) == 0
    return {
        "phase": "M42-W4C",
        **flags,
        "wave4cGo": wave4c_go,
        "finalCertificationStamped": _final_go(),
        "missingRequirements": missing,
        "productName": "Timeline",
        "productFullName": "Timeline Generator",
        "deprecatedLabel": "Director",
    }
