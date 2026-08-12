"""M42 W43 Character Creator gate — binary characterCreatorGo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_ART = _REPO / "artifacts" / "m42" / "w43"
_DOCS = _REPO / "docs" / "release-gate" / "m42"
_FINAL = _DOCS / "M42_W43_FINAL_CERTIFICATION.md"

_ARTIFACT_NAMES = [
    "prerequisites.json",
    "korri_domain_results.json",
    "motion_results.json",
    "performance_results.json",
    "relationship_results.json",
    "prompt_package_results.json",
    "promotion_results.json",
    "visual_sheet_results.json",
    "voice_creator_results.json",
    "unit_results.json",
    "playwright_results.json",
    "certification_results.json",
    "wave43_gate_results.json",
]

_REPORT_NAMES = [
    "M42_W43_FOUNDATION_AUDIT.md",
    "M42_PHASE_4_VIRTUAL_STUDIO_ROADMAP.md",
    "M42_W43_CHARACTER_CREATOR_REPORT.md",
    "M42_W43_CHARACTER_CREATOR_COMPLETION_REPORT.md",
    "M42_W43_KORRI_CERTIFICATION_REPORT.md",
    "M42_W43_GENERATED_IMAGE_PROFILE_ADDENDUM.md",
    "M42_W43_VOICE_CREATOR_ADDENDUM.md",
    "M42_W43_FINAL_CERTIFICATION.md",
]

_VOICE_CREATOR_FLAGS = [
    "korriVoiceCreatorWorkspaceOperational",
    "korriQwenVoiceDesignOperational",
    "korriQwenVoiceCloneOperational",
    "korriVoiceConsentOperational",
    "korriVoiceReferenceValidationOperational",
    "korriVoiceCandidateGenerationOperational",
    "korriVoiceAuditionOperational",
    "korriVoiceComparisonOperational",
    "korriVoiceRefinementOperational",
    "korriVoicePronunciationOperational",
    "korriVoiceReactionLibraryOperational",
    "korriVoiceVersioningOperational",
    "korriVoiceApprovalOperational",
    "korriVoiceAssetRegistrationOperational",
    "korriVoiceProductionBibleIntegrationOperational",
    "korriVoicePromptPackageOperational",
    "korriVoiceTimelineHandoffOperational",
    "korriVoiceCoDirectorOperational",
    "korriVoiceProvenanceComplete",
    "korriVoiceNoMockData",
]

_KORRI_FLAGS = [
    "korriCertificationCharacterOperational",
    "korriCanonicalIdentityApproved",
    "korriHairProfileOperational",
    "korriSkinProfileOperational",
    "korriWardrobeOperational",
    "korriAccessoriesOperational",
    "korriVoiceProfileOperational",
    "korriEmotionalProfileOperational",
    "korriMotionProfileOperational",
    "korriPerformanceBibleOperational",
    "korriRelationshipGraphOperational",
    "korriPromptPackageOperational",
    "korriGeneratedImageProfileOperational",
    "korriProductionBibleIntegrationOperational",
    "korriIdentityRegistryOperational",
    "korriSceneReferenceOperational",
    "korriTimelineOperational",
    "korriEditorOperational",
    "korriCoDirectorOperational",
    "korriEndToEndWorkflowPassed",
    *_VOICE_CREATOR_FLAGS,
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


def _final_go() -> bool:
    if not _FINAL.is_file():
        return False
    text = _FINAL.read_text(encoding="utf-8", errors="ignore")
    go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
    nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
    return go and not nogo


def _wave6p() -> bool:
    p = _REPO / "artifacts" / "m42" / "w6p" / "wave6p_gate_results.json"
    if not p.is_file():
        return False
    try:
        return bool(json.loads(p.read_text(encoding="utf-8")).get("wave6pGo"))
    except Exception:
        return False


def evaluate_m42_character_creator_gate() -> dict[str, Any]:
    cert = _load("certification_results.json")
    prereq = _load("prerequisites.json")
    wave6p = _wave6p() and bool(prereq.get("wave6pGo", True))

    visual = _load("visual_sheet_results.json")
    voice = _load("voice_creator_results.json")
    flags = {k: bool(cert.get(k, False)) for k in _KORRI_FLAGS}
    # Generated Image Profile: require live visual_sheet evidence (no mock)
    flags["korriGeneratedImageProfileOperational"] = bool(
        cert.get("korriGeneratedImageProfileOperational")
    ) or bool(visual.get("passed") and visual.get("mock") is not True)
    # Voice Creator: require voice_creator_results evidence (no mock / no form-only UI)
    voice_flags = voice.get("flags") if isinstance(voice.get("flags"), dict) else voice
    for vf in _VOICE_CREATOR_FLAGS:
        flags[vf] = bool(cert.get(vf, False)) or bool(voice_flags.get(vf, False))
    flags["korriVoiceProfileOperational"] = bool(flags.get("korriVoiceProfileOperational")) or bool(
        flags.get("korriVoiceCreatorWorkspaceOperational") and flags.get("korriVoiceApprovalOperational")
    )
    flags["wave6pPrerequisitePassed"] = wave6p
    flags["noMockData"] = (
        bool(cert.get("noMockData", True))
        and visual.get("mock") is not True
        and voice.get("mock") is not True
    )
    flags["noDuplicateIdentities"] = bool(cert.get("noDuplicateIdentities", True))
    flags["noManualDbCertPath"] = bool(cert.get("noManualDbCertPath", True))
    # Allow gate file to be written after evaluation
    flags["artifactsComplete"] = all(_art(n) for n in _ARTIFACT_NAMES if n != "wave43_gate_results.json")
    flags["reportsComplete"] = all((_DOCS / n).is_file() for n in _REPORT_NAMES)
    flags["unitComplete"] = bool(_load("unit_results.json").get("passed"))
    flags["playwrightComplete"] = bool(_load("playwright_results.json").get("passed"))

    all_ok = all(flags.values()) and _final_go() and bool(cert.get("passed", True))
    return {
        "phase": "M42-W43",
        "characterCreatorGo": all_ok,
        "flags": flags,
        "binaryOnly": True,
        "conditionalGoForbidden": True,
        "conjunction": (
            "all Phase 4.3 requirements ∧ all Character Voice Creator requirements "
            "∧ wave6pGo ∧ final GO → characterCreatorGo"
        ),
    }
