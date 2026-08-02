"""Binary voicePerformanceGo gate for M42 W44."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_ART = _REPO / "artifacts" / "m42" / "w44"
_DOCS = _REPO / "docs" / "release-gate" / "m42"
_W43 = _REPO / "artifacts" / "m42" / "w43" / "wave43_gate_results.json"
_W6P = _REPO / "artifacts" / "m42" / "w6p" / "wave6p_gate_results.json"

_FLAGS = [
    "wave6pPrerequisitePassed",
    "characterCreatorPrerequisitePassed",
    "approvedCharacterVoiceOperational",
    "performanceMarkupOperational",
    "performanceTagRegistryOperational",
    "performanceParserOperational",
    "performanceValidationOperational",
    "normalizedPerformancePlanOperational",
    "performancePlanVersioningOperational",
    "characterPerformanceBibleIntegrationOperational",
    "characterEmotionProfileIntegrationOperational",
    "relationshipDynamicsIntegrationOperational",
    "pronunciationProfileIntegrationOperational",
    "reactionLibraryIntegrationOperational",
    "pauseTagOperational",
    "beatTagOperational",
    "reactionTagOperational",
    "deliveryTagOperational",
    "emotionTagOperational",
    "pronunciationTagOperational",
    "interruptTagOperational",
    "overlapTagOperational",
    "providerCapabilityRegistryOperational",
    "providerTranslationOperational",
    "providerCapabilityHonestyOperational",
    "qwenPerformanceTranslationOperational",
    "segmentedGenerationOperational",
    "segmentRetryOperational",
    "segmentVersioningOperational",
    "dialogueAssemblyOperational",
    "dialogueAssetRegistrationOperational",
    "timelineDialoguePlacementOperational",
    "timelineDialoguePersistenceOperational",
    "timelineOverlapOperational",
    "characterVoiceVersionLinkageOperational",
    "coDirectorVoicePerformanceOperational",
    "coDirectorPerformanceGrounded",
    "coDirectorMutationsApprovalGated",
    "voicePerformanceProvenanceComplete",
    "voicePerformanceProjectAuthorizationOperational",
    "voicePerformanceLockedProjectAccessDenied",
    "voicePerformanceNoMockData",
    "voicePerformanceUnitTestsPassed",
    "voicePerformancePlaywrightPassed",
    "voicePerformanceArtifactsComplete",
    "voicePerformanceReportsComplete",
    "korriVoicePerformanceCertificationPassed",
]

_REPORTS = [
    "M42_W44_FOUNDATION_AUDIT.md",
    "M42_W44_PERFORMANCE_MARKUP_REPORT.md",
    "M42_W44_PARSER_VALIDATION_REPORT.md",
    "M42_W44_CHARACTER_PROFILE_INTEGRATION_REPORT.md",
    "M42_W44_PROVIDER_TRANSLATION_REPORT.md",
    "M42_W44_SEGMENTED_GENERATION_REPORT.md",
    "M42_W44_TIMELINE_INTEGRATION_REPORT.md",
    "M42_W44_CODIRECTOR_REPORT.md",
    "M42_W44_SECURITY_REPORT.md",
    "M42_W44_PLAYWRIGHT_REPORT.md",
    "M42_W44_PRODUCTION_READINESS_REPORT.md",
    "M42_W44_FINAL_CERTIFICATION.md",
]


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def evaluate_m42_voice_performance_gate() -> dict[str, Any]:
    cert = _load(_ART / "certification_results.json")
    unit = _load(_ART / "unit_results.json")
    pw = _load(_ART / "playwright_results.json")
    w43 = _load(_W43)
    w6p = _load(_W6P)
    flags = {k: bool(cert.get(k, False)) for k in _FLAGS}
    flags["wave6pPrerequisitePassed"] = bool(w6p.get("wave6pGo")) or flags["wave6pPrerequisitePassed"]
    flags["characterCreatorPrerequisitePassed"] = bool(w43.get("characterCreatorGo")) or flags[
        "characterCreatorPrerequisitePassed"
    ]
    flags["voicePerformanceUnitTestsPassed"] = bool(unit.get("passed")) or flags["voicePerformanceUnitTestsPassed"]
    flags["voicePerformancePlaywrightPassed"] = bool(pw.get("passed")) or flags["voicePerformancePlaywrightPassed"]
    flags["voicePerformanceArtifactsComplete"] = (_ART / "certification_results.json").is_file() and (
        _ART / "prerequisites.json"
    ).is_file()
    flags["voicePerformanceReportsComplete"] = all((_DOCS / n).is_file() for n in _REPORTS)
    flags["voicePerformanceNoMockData"] = bool(cert.get("voicePerformanceNoMockData", True)) and cert.get("mock") is not True

    if not flags["characterCreatorPrerequisitePassed"]:
        return {
            "phase": "M42-W44",
            "voicePerformanceGo": False,
            "flags": flags,
            "binaryOnly": True,
            "conditionalGoForbidden": True,
            "reason": "characterCreatorGo is not true",
            "mock": False,
        }

    all_ok = all(flags.values()) and bool(cert.get("passed", False))
    return {
        "phase": "M42-W44",
        "voicePerformanceGo": all_ok,
        "flags": flags,
        "binaryOnly": True,
        "conditionalGoForbidden": True,
        "conjunction": "all required flags → voicePerformanceGo",
        "mock": False,
    }
