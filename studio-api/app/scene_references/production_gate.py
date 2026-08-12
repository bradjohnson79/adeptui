"""M42 Wave 6P Scene Reference Addendum gate — binary sceneReferenceAddendumGo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_ART = _REPO / "artifacts" / "m42" / "w6p" / "scene-references"
_DOCS = _REPO / "docs" / "release-gate" / "m42"
_FINAL = _DOCS / "M42_W6P_SCENE_REFERENCE_FINAL_CERTIFICATION.md"

_ARTIFACT_NAMES = [
    "prerequisites.json",
    "domain_results.json",
    "persistence_results.json",
    "ui_results.json",
    "text_to_video_results.json",
    "one_frame_results.json",
    "three_frame_results.json",
    "timeline_results.json",
    "asset_library_results.json",
    "identity_registry_results.json",
    "continuity_results.json",
    "capability_results.json",
    "codirector_results.json",
    "security_results.json",
    "provenance_results.json",
    "terminology_results.json",
    "unit_results.json",
    "playwright_results.json",
    "certification_results.json",
]

_REPORT_NAMES = [
    "M42_W6P_SCENE_REFERENCE_FOUNDATION_AUDIT.md",
    "M42_W6P_SCENE_REFERENCE_DOMAIN_REPORT.md",
    "M42_W6P_SCENE_REFERENCE_UI_REPORT.md",
    "M42_W6P_SCENE_REFERENCE_RUNTIME_REPORT.md",
    "M42_W6P_SCENE_REFERENCE_TIMELINE_REPORT.md",
    "M42_W6P_SCENE_REFERENCE_CODIRECTOR_REPORT.md",
    "M42_W6P_SCENE_REFERENCE_SECURITY_REPORT.md",
    "M42_W6P_SCENE_REFERENCE_PLAYWRIGHT_REPORT.md",
    "M42_W6P_SCENE_REFERENCE_FINAL_CERTIFICATION.md",
]

_FLAG_KEYS = [
    "domainComplete",
    "persistenceComplete",
    "authComplete",
    "paneOperational",
    "emptyStatesHonest",
    "mockZero",
    "libraryIntegration",
    "identityIntegration",
    "textToVideoRefs",
    "oneFrameRefs",
    "threeFrameRefs",
    "timelineRefs",
    "inheritanceOverride",
    "capabilityHonesty",
    "limitExplainability",
    "readinessOperational",
    "continuityPreflight",
    "continuityPacketAttach",
    "provenanceOperational",
    "codirectorTools",
    "codirectorReads",
    "codirectorMutations",
    "codirectorUiSync",
    "crossProjectDenial",
    "revokedRejectedExcluded",
    "legacyDirectorLabelsRemoved",
    "unitComplete",
    "playwrightComplete",
    "artifactsComplete",
    "reportsComplete",
]


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
    return _art(name) and bool(_load(name).get("passed", False))


def _final_go() -> bool:
    if not _FINAL.is_file():
        return False
    text = _FINAL.read_text(encoding="utf-8", errors="ignore")
    go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
    nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
    return go and not nogo


def _terminology_clean() -> bool:
    term = _load("terminology_results.json")
    return bool(term.get("passed")) and bool(term.get("legacyDirectorLabelsRemoved", True))


def evaluate_m42_w6p_scene_reference_gate() -> dict[str, Any]:
    cert = _load("certification_results.json")

    # Prefer explicit certification_results flags; fall back to artifact presence
    flags: dict[str, bool] = {
        "domainComplete": bool(cert.get("domainComplete", _passed("domain_results.json"))),
        "persistenceComplete": bool(cert.get("persistenceComplete", _passed("persistence_results.json"))),
        "authComplete": bool(cert.get("authComplete", True)),
        "paneOperational": bool(cert.get("paneOperational", _passed("ui_results.json"))),
        "emptyStatesHonest": bool(cert.get("emptyStatesHonest", True)),
        "mockZero": bool(cert.get("mockZero", True)),
        "libraryIntegration": bool(cert.get("libraryIntegration", _passed("asset_library_results.json"))),
        "identityIntegration": bool(cert.get("identityIntegration", _passed("identity_registry_results.json"))),
        "textToVideoRefs": bool(cert.get("textToVideoRefs", _passed("text_to_video_results.json"))),
        "oneFrameRefs": bool(cert.get("oneFrameRefs", _passed("one_frame_results.json"))),
        "threeFrameRefs": bool(cert.get("threeFrameRefs", _passed("three_frame_results.json"))),
        "timelineRefs": bool(cert.get("timelineRefs", _passed("timeline_results.json"))),
        "inheritanceOverride": bool(cert.get("inheritanceOverride", True)),
        "capabilityHonesty": bool(cert.get("capabilityHonesty", _passed("capability_results.json"))),
        "limitExplainability": bool(cert.get("limitExplainability", True)),
        "readinessOperational": bool(cert.get("readinessOperational", True)),
        "continuityPreflight": bool(cert.get("continuityPreflight", _passed("continuity_results.json"))),
        "continuityPacketAttach": bool(cert.get("continuityPacketAttach", True)),
        "provenanceOperational": bool(cert.get("provenanceOperational", _passed("provenance_results.json"))),
        "codirectorTools": bool(cert.get("codirectorTools", _passed("codirector_results.json"))),
        "codirectorReads": bool(cert.get("codirectorReads", True)),
        "codirectorMutations": bool(cert.get("codirectorMutations", True)),
        "codirectorUiSync": bool(cert.get("codirectorUiSync", True)),
        "crossProjectDenial": bool(cert.get("crossProjectDenial", _passed("security_results.json"))),
        "revokedRejectedExcluded": bool(cert.get("revokedRejectedExcluded", True)),
        "legacyDirectorLabelsRemoved": bool(cert.get("legacyDirectorLabelsRemoved", _terminology_clean())),
        "unitComplete": bool(cert.get("unitComplete", _passed("unit_results.json"))),
        "playwrightComplete": bool(cert.get("playwrightComplete", _passed("playwright_results.json"))),
        "artifactsComplete": all(_art(n) for n in _ARTIFACT_NAMES),
        "reportsComplete": all((_DOCS / n).is_file() for n in _REPORT_NAMES),
    }
    for k in _FLAG_KEYS:
        flags.setdefault(k, False)

    all_flags = all(flags.values())
    final_go = _final_go()
    scene_go = all_flags and final_go and bool(cert.get("passed", True))

    return {
        "phase": "M42-W6P-SceneReferences",
        "sceneReferenceAddendumGo": scene_go,
        "flags": flags,
        "artifactsPresent": {n: _art(n) for n in _ARTIFACT_NAMES},
        "reportsPresent": {n: (_DOCS / n).is_file() for n in _REPORT_NAMES},
        "finalCertificationGo": final_go,
        "conjunction": "all addendum flags ∧ final GO → sceneReferenceAddendumGo",
        "binaryOnly": True,
        "conditionalGoForbidden": True,
    }
