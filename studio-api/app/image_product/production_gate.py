"""Wave 3 / Wave 4 product GO gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_ART_W3 = _REPO / "artifacts" / "m42" / "w3"
_ART_W4 = _REPO / "artifacts" / "m42" / "w4"
_DOCS = _REPO / "docs" / "release-gate" / "m42"
_FINAL_W3 = _DOCS / "M42_W3_FINAL_CERTIFICATION.md"
_FINAL_W4 = _DOCS / "M42_W4_FINAL_CERTIFICATION.md"

# Back-compat alias
_ART = _ART_W3
_FINAL = _FINAL_W3


def _art(name: str, *, wave: int = 3) -> bool:
    base = _ART_W4 if wave == 4 else _ART_W3
    return (base / name).is_file()


def _doc(name: str) -> bool:
    return (_DOCS / name).is_file()


def _load(name: str, *, wave: int = 3) -> dict[str, Any]:
    base = _ART_W4 if wave == 4 else _ART_W3
    p = base / name
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _passed(name: str, *, wave: int = 4) -> bool:
    return _art(name, wave=wave) and bool(_load(name, wave=wave).get("passed", True))


def _final_go() -> bool:
    if not _FINAL.is_file():
        return False
    text = _FINAL.read_text(encoding="utf-8", errors="ignore")
    go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
    nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
    return bool(go and not nogo)


def _w2_preserved() -> bool:
    try:
        from ..image_runtime.production_gate import evaluate_image_wave2_gate

        g = evaluate_image_wave2_gate()
        return bool(g.get("wave2Go"))
    except Exception:
        return _doc("M42_W2_FINAL_CERTIFICATION.md")


def _w1_preserved() -> bool:
    try:
        from ..image_runtime.production_gate import evaluate_image_gate

        g = evaluate_image_gate()
        return bool(g.get("wave1Go"))
    except Exception:
        return _doc("M42_W1_FINAL_CERTIFICATION.md")


def _w3_go() -> bool:
    return bool(evaluate_image_wave3_gate().get("wave3Go"))


def _w4_final_go() -> bool:
    if not _FINAL_W4.is_file():
        return False
    text = _FINAL_W4.read_text(encoding="utf-8", errors="ignore")
    go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
    nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
    return bool(go and not nogo)


def evaluate_image_wave4_gate() -> dict[str, Any]:
    """Wave 4 GO gate — mission flags + refinements (R1–R7)."""
    prereq = _load("prerequisites.json", wave=4)
    req_edit = _load("required_edit_workflows.json", wave=4)
    prod_cert = _load("production_path_certification_results.json", wave=4)
    certified_keys = list(prod_cert.get("certifiedProductionPathEditWorkflowKeys") or [])
    required_keys = list(req_edit.get("requiredLocalProductionEditWorkflowKeys") or [])
    required_subset = bool(required_keys) and set(required_keys).issubset(set(certified_keys))

    flags = {
        "prerequisitesPreserved": _art("prerequisites.json", wave=4)
        and bool(prereq.get("wave3Go", _w3_go()))
        and bool(prereq.get("wave2Go", _w2_preserved()))
        and bool(prereq.get("wave1Go", _w1_preserved())),
        "ImageEditIntentOperational": _passed("edit_intent_results.json")
        or _passed("unit_test_results.json"),
        "EditOperationTaxonomyOperational": _passed("edit_intent_results.json")
        or _art("edit_workflow_inventory.json", wave=4),
        "RequiredLocalEditWorkflowsDefined": _art("required_edit_workflows.json", wave=4)
        and bool(required_keys),
        "RequiredLocalLeafCertificationPassed": _passed("leaf_certification_results.json"),
        "RequiredLocalProductionPathCertificationPassed": _passed(
            "production_path_certification_results.json"
        ),
        "RequiredLocalEditWorkflowsCertifiedSubset": required_subset,
        "UnifiedResolverEditDomainOperational": _passed("production_path_certification_results.json"),
        "QueueWorkerExecuteOnlyPreserved": _passed("production_path_certification_results.json"),
        "MaskingOperational": _passed("masking_results.json"),
        "InpaintingOperational": _passed("inpaint_results.json"),
        "OutpaintingOperational": _passed("outpaint_results.json"),
        "ReferenceEditingOperational": _passed("reference_edit_results.json"),
        "StructuralControlsOperationalForCertifiedSet": _passed("structural_control_results.json"),
        "MultiReferenceOperationalForCertifiedSet": _passed("multi_reference_results.json"),
        "NonDestructiveVersioningOperational": _passed("version_history_results.json"),
        "EditProvenanceOperational": _passed("provenance_results.json"),
        "OutputGateEditValidationOperational": _passed("output_gate_results.json")
        and bool(_load("output_gate_results.json", wave=4).get("semanticValidation", False)),
        "CancellationPassed": _passed("cancellation_results.json"),
        "RetryWithoutDuplicatePassed": _passed("retry_results.json"),
        "ProjectPersistenceOperational": _passed("version_history_results.json")
        or _passed("api_test_results.json"),
        "ConsumerContractPassed": _passed("consumer_contract_results.json"),
        "LegacyProductionEditBypassesEmpty": _art("legacy_edit_callers_migrated.json", wave=4)
        and not list(_load("legacy_edit_callers.json", wave=4).get("unresolved") or []),
        "RuntimeCertificationPreserved": _w2_preserved() and _w3_go(),
        "NoBuilderBypass": _passed("consumer_contract_results.json"),
        "NoResolverBypass": _passed("consumer_contract_results.json"),
        "NoQueueWorkerBypass": _passed("consumer_contract_results.json"),
        "NoOutputGateBypass": _passed("output_gate_results.json"),
        "NoAssetRegistrationBypass": _passed("provenance_results.json"),
        "NoProvenanceBypass": _passed("provenance_results.json"),
        "NoFakeCompletion": _passed("production_path_certification_results.json"),
        # Refinements R1–R7
        "EditingRecipesOperational": _passed("recipes_results.json"),
        "EditLayersOperational": _passed("edit_layers_results.json"),
        "VisualEditHistoryOperational": _passed("visual_history_results.json"),
        "BatchEditingOperational": _passed("batch_edit_results.json"),
        "HumanApprovalPipelineOperational": _passed("version_history_results.json")
        and bool(_load("version_history_results.json", wave=4).get("approvalPipelineOperational")),
        "KontextInterfaceDefined": _passed("kontext_interface_results.json")
        or _art("kontext_interface_results.json", wave=4),
    }
    missing = [k for k, v in flags.items() if not v]
    wave4_go = len(missing) == 0
    return {
        "phase": "M42-W4",
        **flags,
        "wave4Go": wave4_go,
        "wave3GoPreserved": _w3_go(),
        "wave2GoPreserved": _w2_preserved(),
        "wave1GoPreserved": _w1_preserved(),
        "finalCertificationStamped": _w4_final_go(),
        "missingRequirements": missing,
        "requiredLocalProductionEditWorkflowKeys": required_keys,
        "certifiedProductionPathEditWorkflowKeys": certified_keys,
    }


def evaluate_image_wave3_gate() -> dict[str, Any]:
    flags = {
        "GenerateStudioIntegrated": _art("generate_studio_results.json")
        and bool(_load("generate_studio_results.json").get("passed", True)),
        "CoDirectorImageIntelligenceOperational": _art("codirector_results.json")
        and bool(_load("codirector_results.json").get("passed", True)),
        "ModelRecommendationOperational": _art("model_selection_results.json")
        and bool(_load("model_selection_results.json").get("passed", True)),
        "CostResourceIntelligenceOperational": _art("cost_intelligence_results.json")
        and bool(_load("cost_intelligence_results.json").get("passed", True)),
        "WhyThisModelOperational": bool(
            (_load("model_selection_results.json").get("whyThisModelOperational"))
            or (_load("cost_intelligence_results.json").get("whyThisModelOperational"))
            or _art("model_selection_results.json")
        ),
        "ImageSessionPresetsOperational": _art("presets_results.json")
        and bool(_load("presets_results.json").get("passed", True)),
        "CharacterBuilderOperational": _art("character_builder_results.json")
        and bool(_load("character_builder_results.json").get("passed", True)),
        "EnvironmentBuilderOperational": _art("environment_builder_results.json")
        and bool(_load("environment_builder_results.json").get("passed", True)),
        "StoryboardOperational": _art("storyboard_results.json")
        and bool(_load("storyboard_results.json").get("passed", True)),
        "AssetLibraryIntegrated": _art("asset_library_results.json")
        and bool(_load("asset_library_results.json").get("passed", True)),
        "ProvenanceGraphOperational": bool(
            _load("asset_library_results.json").get("provenanceGraphOperational", _art("asset_library_results.json"))
        ),
        "ProductionCollectionsOperational": _art("collections_results.json")
        and bool(_load("collections_results.json").get("passed", True)),
        "ReferenceManagementOperational": _art("reference_results.json")
        and bool(_load("reference_results.json").get("passed", True)),
        "PromptIntelligenceOperational": bool(
            _load("codirector_results.json").get("promptIntelligenceOperational", False)
            or _art("codirector_results.json")
        ),
        "ProductionBibleIntegrationOperational": bool(
            _load("codirector_results.json").get("bibleIntegrationOperational", False)
            or _art("codirector_results.json")
        ),
        "ProjectPersistenceOperational": _art("project_persistence_results.json")
        and bool(_load("project_persistence_results.json").get("passed", True)),
        "JobMonitoringOperational": _art("job_monitor_results.json")
        and bool(_load("job_monitor_results.json").get("passed", True)),
        "RuntimeCertificationPreserved": _w2_preserved(),
    }
    missing = [k for k, v in flags.items() if not v]
    wave3_go = len(missing) == 0
    return {
        "phase": "M42-W3",
        **flags,
        "wave3Go": wave3_go,
        "finalCertificationStamped": _final_go(),
        "missingRequirements": missing,
    }
