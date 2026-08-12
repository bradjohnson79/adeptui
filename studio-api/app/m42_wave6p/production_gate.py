"""M42 Wave 6P production gate — binary wave6pGo requiring sceneReferenceAddendumGo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.scene_references.production_gate import evaluate_m42_w6p_scene_reference_gate

_REPO = Path(__file__).resolve().parents[3]
_ART = _REPO / "artifacts" / "m42" / "w6p"
_DOCS = _REPO / "docs" / "release-gate" / "m42"
_FINAL = _DOCS / "M42_W6P_FINAL_CERTIFICATION.md"

_ARTIFACT_NAMES = [
    "prerequisites.json",
    "product_matrix.json",
    "runtime_matrix.json",
    "workflow_matrix.json",
    "playwright_results.json",
    "manual_beta_results.json",
    "performance_results.json",
    "release_gate_results.json",
    "wave6p_gate_results.json",
]

_REPORT_NAMES = [
    "M42_W6P_FOUNDATION_AUDIT.md",
    "M42_W6P_PRODUCT_CERTIFICATION.md",
    "M42_W6P_RUNTIME_CERTIFICATION.md",
    "M42_W6P_FILMMAKER_WORKFLOWS.md",
    "M42_W6P_PLAYWRIGHT_REPORT.md",
    "M42_W6P_MANUAL_BETA_REPORT.md",
    "M42_W6P_RELEASE_READINESS.md",
    "M42_W6P_FINAL_CERTIFICATION.md",
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


def _prior_waves() -> dict[str, bool]:
    mapping = {
        "wave1Go": (_ART.parent / "w1" / "image_runtime_gate.json", "wave1Go"),
        "wave2Go": (_ART.parent / "w2" / "wave2_gate_results.json", "wave2Go"),
        "wave3Go": (_ART.parent / "w3" / "wave3_gate_results.json", "wave3Go"),
        "wave4Go": (_ART.parent / "w4" / "wave4_gate_results.json", "wave4Go"),
        "wave4bGo": (_ART.parent / "w4b" / "wave4b_gate_results.json", "wave4bGo"),
        "wave4cGo": (_ART.parent / "w4c" / "wave4c_gate_results.json", "wave4cGo"),
        "wave5Go": (_ART.parent / "w5" / "wave5_gate_results.json", "wave5Go"),
    }
    out: dict[str, bool] = {}
    for key, (path, field) in mapping.items():
        try:
            d = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            out[key] = bool(isinstance(d, dict) and d.get(field))
        except Exception:
            out[key] = False
    return out


def evaluate_m42_wave6p_gate() -> dict[str, Any]:
    prereq = _load("prerequisites.json")
    priors = _prior_waves()
    all_prereq = all(priors.values()) and bool(prereq.get("Wave6pMayBegin", False))

    scene_gate = evaluate_m42_w6p_scene_reference_gate()
    scene_go = bool(scene_gate.get("sceneReferenceAddendumGo"))

    manual = _load("manual_beta_results.json")
    manual_passed = bool(manual.get("manualBetaPassed")) and int(manual.get("failCount", 1)) == 0

    flags = {
        "allPrerequisiteWavesPassed": all_prereq,
        "allProductsCertified": bool(_load("product_matrix.json").get("allCertified", _passed("product_matrix.json"))),
        "allRuntimePathsCanonical": bool(_load("runtime_matrix.json").get("allCanonical", _passed("runtime_matrix.json"))),
        "allIntegrationsOperational": bool(_load("release_gate_results.json").get("integrationsOperational", True)),
        "allPlaywrightSuitesPassed": bool(_load("playwright_results.json").get("passed", False)),
        "manualBetaPassed": manual_passed,
        "filmmakerWorkflowCertificationPassed": bool(
            _load("workflow_matrix.json").get("passed", _passed("workflow_matrix.json"))
        ),
        "noRuntimeBypasses": bool(_load("release_gate_results.json").get("noRuntimeBypasses", True)),
        "noFakeData": bool(_load("release_gate_results.json").get("noFakeData", True)),
        "noDuplicateAuthorities": bool(_load("release_gate_results.json").get("noDuplicateAuthorities", True)),
        "productionDocumentationComplete": all((_DOCS / n).is_file() for n in _REPORT_NAMES),
        "releaseArtifactsComplete": all(_art(n) for n in _ARTIFACT_NAMES),
        "sceneReferenceAddendumGo": scene_go,
        "sceneReferencePaneOperational": bool(scene_gate.get("flags", {}).get("paneOperational")),
        "textToVideoReferencesOperational": bool(scene_gate.get("flags", {}).get("textToVideoRefs")),
        "oneFrameReferencesOperational": bool(scene_gate.get("flags", {}).get("oneFrameRefs")),
        "threeFrameReferencesOperational": bool(scene_gate.get("flags", {}).get("threeFrameRefs")),
        "timelineReferencesOperational": bool(scene_gate.get("flags", {}).get("timelineRefs")),
        "referenceScopeInheritanceOperational": bool(scene_gate.get("flags", {}).get("inheritanceOverride")),
        "referenceWorkflowCapabilityHonest": bool(scene_gate.get("flags", {}).get("capabilityHonesty")),
        "referenceLimitSelectionExplainable": bool(scene_gate.get("flags", {}).get("limitExplainability")),
        "referenceProvenanceOperational": bool(scene_gate.get("flags", {}).get("provenanceOperational")),
        "referenceReadinessOperational": bool(scene_gate.get("flags", {}).get("readinessOperational")),
        "referenceDragDropOperational": bool(_load("product_matrix.json").get("referenceDragDropOperational", True)),
        "referenceRevocationRespected": bool(scene_gate.get("flags", {}).get("revokedRejectedExcluded")),
        "legacyDirectorLabelsRemoved": bool(scene_gate.get("flags", {}).get("legacyDirectorLabelsRemoved")),
    }

    wave6p_go = all(flags.values()) and _final_go() and scene_go

    return {
        "phase": "M42-W6P",
        "wave6pGo": wave6p_go,
        "sceneReferenceAddendumGo": scene_go,
        "flags": flags,
        "priorWaves": priors,
        "artifactsPresent": {n: _art(n) for n in _ARTIFACT_NAMES},
        "reportsPresent": {n: (_DOCS / n).is_file() for n in _REPORT_NAMES},
        "finalCertificationGo": _final_go(),
        "conjunction": "sceneReferenceAddendumGo ∧ all Wave6P flags ∧ final GO → wave6pGo",
        "binaryOnly": True,
        "conditionalGoForbidden": True,
    }
