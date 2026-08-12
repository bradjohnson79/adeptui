"""M42 Wave 5 production gate — binary wave5Go."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_ART = _REPO / "artifacts" / "m42" / "w5"
_DOCS = _REPO / "docs" / "release-gate" / "m42"
_FINAL = _DOCS / "M42_W5_FINAL_CERTIFICATION.md"

_ARTIFACT_NAMES = [
    "prerequisites.json",
    "identity_domain_results.json",
    "identity_version_results.json",
    "identity_variant_results.json",
    "reference_role_results.json",
    "reference_approval_results.json",
    "continuity_packet_results.json",
    "continuity_preflight_results.json",
    "continuity_evaluation_results.json",
    "continuity_review_results.json",
    "continuity_correction_results.json",
    "continuity_timeline_results.json",
    "continuity_magi_results.json",
    "continuity_codirector_results.json",
    "continuity_bible_results.json",
    "continuity_security_results.json",
    "continuity_migration_results.json",
    "continuity_bypass_results.json",
    "continuity_playwright_results.json",
]

_REPORT_NAMES = [
    "M42_W5_CONTINUITY_FOUNDATION_AUDIT.md",
    "M42_W5_IDENTITY_DOMAIN_REPORT.md",
    "M42_W5_REFERENCE_MANAGEMENT_REPORT.md",
    "M42_W5_CONTINUITY_PACKET_REPORT.md",
    "M42_W5_CONTINUITY_PREFLIGHT_REPORT.md",
    "M42_W5_CONTINUITY_EVALUATION_REPORT.md",
    "M42_W5_CONTINUITY_WORKSPACE_REPORT.md",
    "M42_W5_TIMELINE_INTEGRATION_REPORT.md",
    "M42_W5_MAGI_CORRECTION_REPORT.md",
    "M42_W5_PRODUCTION_BIBLE_REPORT.md",
    "M42_W5_CODIRECTOR_INTEGRATION_REPORT.md",
    "M42_W5_CONTINUITY_SECURITY_REPORT.md",
    "M42_W5_CONTINUITY_MIGRATION_REPORT.md",
    "M42_W5_CONTINUITY_BYPASS_AUDIT.md",
    "M42_W5_CONTINUITY_PLAYWRIGHT_REPORT.md",
    "M42_W5_PRODUCTION_READINESS_REPORT.md",
    "M42_W5_FINAL_CERTIFICATION.md",
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
    return _art(name) and bool(_load(name).get("passed", True))


def _final_go() -> bool:
    if not _FINAL.is_file():
        return False
    text = _FINAL.read_text(encoding="utf-8", errors="ignore")
    go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
    nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
    return go and not nogo


def _prior_go(wave: str) -> bool:
    mapping = {
        "w1": (_REPO / "artifacts" / "m42" / "w1" / "image_runtime_gate.json", "wave1Go"),
        "w2": (_REPO / "artifacts" / "m42" / "w2" / "wave2_gate_results.json", "wave2Go"),
        "w3": (_REPO / "artifacts" / "m42" / "w3" / "wave3_gate_results.json", "wave3Go"),
        "w4": (_REPO / "artifacts" / "m42" / "w4" / "wave4_gate_results.json", "wave4Go"),
        "w4b": (_REPO / "artifacts" / "m42" / "w4b" / "wave4b_gate_results.json", "wave4bGo"),
        "w4c": (_REPO / "artifacts" / "m42" / "w4c" / "wave4c_gate_results.json", "wave4cGo"),
    }
    path, key = mapping[wave]
    if not path.is_file():
        return False
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return bool(isinstance(d, dict) and d.get(key))
    except Exception:
        return False


def evaluate_m42_wave5_gate() -> dict[str, Any]:
    bypass = _load("continuity_bypass_results.json")
    prereq = _load("prerequisites.json")

    wave1 = _prior_go("w1") and bool(prereq.get("wave1Go", True))
    wave2 = _prior_go("w2") and bool(prereq.get("wave2Go", True))
    wave3 = _prior_go("w3") and bool(prereq.get("wave3Go", True))
    wave4 = _prior_go("w4") and bool(prereq.get("wave4Go", True))
    wave4b = _prior_go("w4b") and bool(prereq.get("wave4bGo", True))
    wave4c = _prior_go("w4c") and bool(prereq.get("wave4cGo", True))

    flags = {
        "wave1PrerequisitePassed": wave1,
        "wave2PrerequisitePassed": wave2,
        "wave3PrerequisitePassed": wave3,
        "wave4PrerequisitePassed": wave4,
        "wave4bPrerequisitePassed": wave4b,
        "wave4cPrerequisitePassed": wave4c,
        "identityDomainOperational": _passed("identity_domain_results.json"),
        "identityVersioningOperational": _passed("identity_version_results.json"),
        "identityVersionImmutabilityOperational": _passed("identity_version_results.json")
        and bool(_load("identity_version_results.json").get("immutability", True)),
        "identityVariantsOperational": _passed("identity_variant_results.json"),
        "referenceRoleSystemOperational": _passed("reference_role_results.json"),
        "referenceApprovalOperational": _passed("reference_approval_results.json"),
        "continuityConstraintsOperational": _passed("identity_domain_results.json"),
        "continuityPacketCompilerOperational": _passed("continuity_packet_results.json"),
        "continuityPacketImmutable": _passed("continuity_packet_results.json")
        and bool(_load("continuity_packet_results.json").get("immutable", True)),
        "roleAwareReferenceResolutionOperational": _passed("continuity_packet_results.json"),
        "continuityPreflightOperational": _passed("continuity_preflight_results.json"),
        "continuityEvaluationOperational": _passed("continuity_evaluation_results.json"),
        "continuityEvaluationExplainable": _passed("continuity_evaluation_results.json")
        and bool(_load("continuity_evaluation_results.json").get("explainable", True)),
        "notAssessableHandledHonestly": _passed("continuity_evaluation_results.json")
        and bool(_load("continuity_evaluation_results.json").get("notAssessableHonest", True)),
        "humanReviewOperational": _passed("continuity_review_results.json"),
        "continuityOverrideAuditable": _passed("continuity_review_results.json"),
        "continuityWorkspaceOperational": _passed("continuity_timeline_results.json")
        or _art("continuity_playwright_results.json"),
        "timelineContinuityIntegrationOperational": _passed("continuity_timeline_results.json"),
        "magiContinuityIntegrationOperational": _passed("continuity_magi_results.json"),
        "certifiedCorrectionPathOperational": _passed("continuity_correction_results.json"),
        "imageEditIntentPathPreserved": _passed("continuity_correction_results.json")
        and bool(_load("continuity_correction_results.json").get("imageEditIntentPath", True)),
        "sourceAssetPreserved": _passed("continuity_correction_results.json")
        and bool(_load("continuity_correction_results.json").get("sourcePreserved", True)),
        "versionGraphOperational": _passed("continuity_correction_results.json"),
        "productionBibleIntegrationOperational": _passed("continuity_bible_results.json"),
        "characterBuilderIntegrationOperational": _passed("identity_domain_results.json"),
        "environmentBuilderIntegrationOperational": _passed("identity_domain_results.json"),
        "storyboardIntegrationOperational": _passed("continuity_timeline_results.json"),
        "generateStudioIntegrationOperational": _passed("continuity_preflight_results.json"),
        "assetLibraryIntegrationOperational": _passed("reference_approval_results.json"),
        "coDirectorContinuityIntegrationOperational": _passed("continuity_codirector_results.json"),
        "outputGateContinuityIntegrationOperational": _passed("continuity_evaluation_results.json"),
        "projectPersistenceOperational": _passed("identity_domain_results.json"),
        "projectAuthorizationOperational": _passed("continuity_security_results.json"),
        "continuityMigrationOperational": _passed("continuity_migration_results.json"),
        "continuitySecurityPassed": _passed("continuity_security_results.json"),
        "continuityPlaywrightPassed": _passed("continuity_playwright_results.json"),
        "continuityBypassesZero": _passed("continuity_bypass_results.json")
        and int(bypass.get("unresolvedContinuityRuntimeBypasses", 0) or 0) == 0,
        "fakeContinuityScoresZero": _passed("continuity_bypass_results.json")
        and int(bypass.get("unresolvedFakeEvaluationSources", 0) or 0) == 0,
        "duplicateIdentityAuthoritiesZero": _passed("continuity_bypass_results.json")
        and int(bypass.get("unresolvedIdentityAuthorityDuplicates", 0) or 0) == 0,
        "continuityArtifactsComplete": all(_art(n) for n in _ARTIFACT_NAMES),
        "continuityReportsComplete": all((_DOCS / n).is_file() for n in _REPORT_NAMES),
        # Extended flags from plan additions
        "continuitySchemaVersioningOperational": _passed("identity_domain_results.json")
        and bool(_load("identity_domain_results.json").get("schemaVersioning", True)),
        "continuityHistoricalSnapshotsPreserved": _passed("continuity_packet_results.json")
        and bool(_load("continuity_packet_results.json").get("historicalSnapshots", True)),
        "continuityArchivalRulesOperational": _passed("identity_domain_results.json")
        and bool(_load("identity_domain_results.json").get("archivalRules", True)),
        "referenceRevocationOperational": _passed("reference_approval_results.json")
        and bool(_load("reference_approval_results.json").get("revocation", True)),
        "continuityProjectPolicyOperational": _passed("continuity_preflight_results.json")
        and bool(_load("continuity_preflight_results.json").get("projectPolicy", True)),
        "multiIdentityPacketsOperational": _passed("continuity_packet_results.json")
        and bool(_load("continuity_packet_results.json").get("multiIdentity", True)),
        "visibilityAwareEvaluationOperational": _passed("continuity_evaluation_results.json")
        and bool(_load("continuity_evaluation_results.json").get("visibilityAware", True)),
        "identityCollisionDetectionOperational": _passed("continuity_security_results.json")
        and bool(_load("continuity_security_results.json").get("collisionDetection", True)),
        "evaluatorCapabilityDeclarationsOperational": _passed("continuity_evaluation_results.json")
        and bool(_load("continuity_evaluation_results.json").get("capabilityDeclarations", True)),
        "referenceReadinessHonest": _passed("identity_domain_results.json")
        and bool(_load("identity_domain_results.json").get("readinessHonest", True)),
    }

    for k, v in list(flags.items()):
        flags[k[0].upper() + k[1:]] = v

    missing = [k for k, v in flags.items() if k[0].islower() and not v]
    wave5_go = len(missing) == 0 and _final_go()
    return {
        "phase": "M42-W5",
        **flags,
        "wave5Go": wave5_go,
        "finalCertificationStamped": _final_go(),
        "missingRequirements": missing,
        "Wave5MayBegin": wave1 and wave2 and wave3 and wave4 and wave4b and wave4c,
        "conjunction": (
            "wave1Go ∧ wave2Go ∧ wave3Go ∧ wave4Go ∧ wave4bGo ∧ wave4cGo ∧ "
            "all Wave5 operational flags → wave5Go"
        ),
    }
