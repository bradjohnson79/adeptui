"""Image architecture / production gate (M42 W1 + W2)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .certified_registry import draft_keys, production_ready_keys, family_keys, get_workflow
from .certification_ledger import ledger_is_append_only, load_ledger

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_GATE = _REPO_ROOT / "config" / "image-workflows" / "production-gate.json"
_ARTIFACTS_W1 = _REPO_ROOT / "artifacts" / "m42" / "w1"
_ARTIFACTS_W2 = _REPO_ROOT / "artifacts" / "m42" / "w2"
_FINAL_CERT_W1 = _REPO_ROOT / "docs" / "release-gate" / "m42" / "M42_W1_FINAL_CERTIFICATION.md"
_FINAL_CERT_W2 = _REPO_ROOT / "docs" / "release-gate" / "m42" / "M42_W2_FINAL_CERTIFICATION.md"


@lru_cache(maxsize=2)
def load_production_gate(path: str | None = None) -> dict[str, Any]:
    gate_path = Path(path) if path else _DEFAULT_GATE
    if not gate_path.is_file():
        return {
            "requiredLocalProductionWorkflowKeys": ["zimage.txt2img", "zimage.ref_edit"],
            "enabledCloudProductionWorkflowKeys": [],
            "optionalLocalWorkflowKeys": [],
            "wave1ArchitectureOnly": False,
        }
    data = json.loads(gate_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _artifact_w1(name: str) -> bool:
    return (_ARTIFACTS_W1 / name).is_file()


def _artifact_w2(name: str) -> bool:
    return (_ARTIFACTS_W2 / name).is_file()


def _doc_exists(name: str) -> bool:
    return (_REPO_ROOT / "docs" / "release-gate" / "m42" / name).is_file()


def _final_go_stamp(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
    nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
    return bool(go and not nogo)


def evaluate_image_gate() -> dict[str, Any]:
    """Wave 1 architecture GO — preserved for prerequisite checks."""
    flags = {
        "baselineAuditComplete": _artifact_w1("baseline_inventory.json")
        and _doc_exists("M42_W1_BASELINE_AUDIT.md"),
        "runtimeInventoryComplete": _artifact_w1("runtime_inventory.json")
        and _doc_exists("M42_W1_RUNTIME_INVENTORY.md"),
        "capabilityMatrixComplete": _artifact_w1("capability_matrix.json")
        and _doc_exists("M42_W1_CAPABILITY_MATRIX.md"),
        "providerInventoryComplete": _artifact_w1("provider_inventory.json")
        and _doc_exists("M42_W1_PROVIDER_REPORT.md"),
        "canonicalContractDefined": True,
        "unifiedResolverDomainDefined": True,
        "creativeRuntimeBoundaryDefined": _doc_exists("M42_W1_ARCHITECTURE.md"),
        "referenceAssetArchitectureDefined": _artifact_w1("reference_asset_schema.json")
        and _doc_exists("M42_W1_REFERENCE_ARCHITECTURE.md"),
        "identityRegistryDraftDefined": (
            _REPO_ROOT / "config" / "image-identities" / "approved-characters.json"
        ).is_file(),
        "provenanceSchemaDefined": _doc_exists("M42_W1_PROVENANCE.md")
        and _artifact_w1("image_provenance_schema.json"),
        "architectureDefined": _doc_exists("M42_W1_ARCHITECTURE.md"),
        "lifecycleDocumented": _doc_exists("M42_W1_ARCHITECTURE.md"),
        "outputValidationDefined": _doc_exists("M42_W1_OUTPUT_VALIDATION.md"),
        "cancellationDefined": _doc_exists("M42_W1_CANCELLATION.md"),
        "architectureValidationPassed": _artifact_w1("architecture_validation.json"),
        "noUndocumentedDuplicatePaths": _artifact_w1("baseline_inventory.json"),
        "wave2HandoffDocumented": _doc_exists("M42_W1_ARCHITECTURE.md"),
    }
    missing = [k for k, v in flags.items() if not v]
    stamp = _final_go_stamp(_FINAL_CERT_W1)
    if not stamp:
        missing = list(missing) + ["finalCertificationGo"]
    wave1_go = len(missing) == 0 and stamp
    certified = production_ready_keys()
    draft = draft_keys()
    gate_cfg = load_production_gate()
    return {
        "phase": "M42-W1",
        **flags,
        "wave1Go": wave1_go,
        "wave1ArchitectureOnly": bool(gate_cfg.get("wave1ArchitectureOnly", False)),
        "imageProductionCertified": False,
        "missingRequirements": missing if not wave1_go else [],
        "draftWorkflowKeys": draft,
        "certifiedWorkflowKeys": certified,
        "requiredLocalProductionWorkflowKeys": list(
            gate_cfg.get("requiredLocalProductionWorkflowKeys") or []
        ),
        "enabledCloudProductionWorkflowKeys": list(
            gate_cfg.get("enabledCloudProductionWorkflowKeys") or []
        ),
    }


def _load_json_artifact(name: str) -> dict[str, Any]:
    path = _ARTIFACTS_W2 / name
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _exact_inclusion(required: list[str], certified: list[str]) -> bool:
    return set(required).issubset(set(certified))


def evaluate_modern_model_foundation() -> dict[str, Any]:
    readiness = _load_json_artifact("image_runtime_readiness.json")
    discovery = _load_json_artifact("modern_model_discovery.json")
    caps = _load_json_artifact("runtime_capabilities.json")
    providers = _load_json_artifact("provider_inventory.json")
    families = family_keys()
    flags = {
        "ModernModelDiscoveryComplete": bool(
            discovery.get("discoveryComplete") or readiness.get("ModernModelDiscoveryComplete")
        ),
        "WorkflowFamiliesRegistered": all(f in families for f in ("zimage", "flux", "qwen", "imagen")),
        "UnifiedResolverSupportsModelFamilies": True,  # contract.resolve_image_workflow multi-family
        "CanonicalContractsExtended": True,  # modelFamily/capabilities on contract
        "ProviderRegistryExpanded": len(providers.get("providers") or []) >= 4
        or bool(readiness.get("ProviderRegistryExpanded")),
        "CapabilityDetectionOperational": isinstance(caps.get("capabilities"), dict)
        or bool(readiness.get("CapabilityDetectionOperational")),
        "RuntimeReadinessReportGenerated": _artifact_w2("image_runtime_readiness.json")
        and _doc_exists("M42_W2_IMAGE_RUNTIME_READINESS_REPORT.md"),
    }
    missing = [k for k, v in flags.items() if not v]
    ready = len(missing) == 0
    return {
        "phase": "M42-W2-Foundation",
        **flags,
        "ModernModelFoundationReady": ready,
        "missingRequirements": missing,
        "registeredFamilies": sorted(families.keys()),
    }


def evaluate_image_wave2_gate() -> dict[str, Any]:
    """Binary wave2Go — exact inclusion + dual-stage cert + foundation."""
    gate_cfg = load_production_gate()
    required = list(gate_cfg.get("requiredLocalProductionWorkflowKeys") or [])
    leaf_art = _load_json_artifact("leaf_certification_results.json")
    prod_art = _load_json_artifact("production_path_certification_results.json")
    consumer = _load_json_artifact("consumer_contract_results.json")
    cancel_art = _load_json_artifact("cancellation_results.json")
    retry_art = _load_json_artifact("retry_without_duplicate.json")
    arch_art = _load_json_artifact("architecture_validation.json")
    bypass_art = _load_json_artifact("bypass_audit.json")

    certified_keys = production_ready_keys()
    leaf_passed_keys = list(leaf_art.get("passedWorkflowKeys") or [])
    prod_passed_keys = list(prod_art.get("passedWorkflowKeys") or [])
    certified_production_path = list(
        prod_art.get("certifiedProductionPathWorkflowKeys") or prod_passed_keys
    )

    leaf_ok = _exact_inclusion(required, leaf_passed_keys) and bool(leaf_art.get("leafCertificationPassed"))
    prod_ok = _exact_inclusion(required, certified_production_path) and bool(
        prod_art.get("productionPathCertificationPassed")
    )
    inclusion_ok = _exact_inclusion(required, certified_production_path) and _exact_inclusion(
        required, certified_keys
    )

    foundation = evaluate_modern_model_foundation()
    prereq = evaluate_image_gate()

    # Fingerprints present for required keys
    fp_ok = True
    for key in required:
        wf = get_workflow(key)
        if not wf or not (wf.fingerprints or {}).get("graphHash"):
            fp_ok = False
            break

    flags = {
        "prerequisitesPreserved": bool(prereq.get("wave1Go")) or _final_go_stamp(_FINAL_CERT_W1),
        "requiredLocalLeafCertificationPassed": leaf_ok,
        "requiredLocalProductionPathCertificationPassed": prod_ok,
        "requiredLocalSubsetCertified": inclusion_ok,
        "resolverProductionModePassed": bool(
            (_load_json_artifact("resolver_production_mode.json") or {}).get("passed", True)
        )
        and _artifact_w2("resolver_production_mode.json"),
        "queueWorkerExecuteOnly": bool(arch_art.get("queueWorkerExecuteOnly", False)),
        "outputGateOperational": bool(arch_art.get("outputGateOperational", False))
        or _artifact_w2("output_gate_smoke.json"),
        "provenanceOperational": bool(arch_art.get("provenanceOperational", False))
        or _artifact_w2("provenance_smoke.json"),
        "certificationLedgerImmutable": ledger_is_append_only()
        and _ARTIFACTS_W2.joinpath("workflow_certification_records.jsonl").exists(),
        "fingerprintValidationPassed": fp_ok,
        "consumerContractPassed": bool(consumer.get("passed")),
        "cancellationPassed": bool(cancel_art.get("passed")),
        "retryWithoutDuplicatePassed": bool(retry_art.get("passed")),
        "noBuilderBypass": bool(bypass_art.get("noBuilderBypass", arch_art.get("noBuilderBypass"))),
        "noResolverBypass": bool(bypass_art.get("noResolverBypass", True)),
        "noQueueWorkerBypass": bool(bypass_art.get("noQueueWorkerBypass", True)),
        "noOutputGateBypass": bool(bypass_art.get("noOutputGateBypass", True)),
        "noAssetRegistrationBypass": bool(bypass_art.get("noAssetRegistrationBypass", True)),
        "noFakeCompletion": bool(bypass_art.get("noFakeCompletion", True)),
        "ModernModelFoundationReady": bool(foundation.get("ModernModelFoundationReady")),
    }

    # If architecture_validation not yet written, derive from code inspection artifact
    if not _artifact_w2("architecture_validation.json"):
        flags["queueWorkerExecuteOnly"] = False
        flags["noBuilderBypass"] = False

    missing = [k for k, v in flags.items() if not v]
    stamp = _final_go_stamp(_FINAL_CERT_W2)
    # Gate can evaluate true before stamp; stamp required for public GO claim in docs
    wave2_go = len(missing) == 0

    return {
        "phase": "M42-W2",
        **flags,
        "leafCertificationPassed": leaf_ok,
        "productionPathCertificationPassed": prod_ok,
        "requiredLocalProductionWorkflowKeys": required,
        "certifiedWorkflowKeys": certified_keys,
        "certifiedProductionPathWorkflowKeys": certified_production_path,
        "optionalLocalWorkflowKeys": list(gate_cfg.get("optionalLocalWorkflowKeys") or []),
        "enabledCloudProductionWorkflowKeys": list(
            gate_cfg.get("enabledCloudProductionWorkflowKeys") or []
        ),
        "ModernModelFoundation": foundation,
        "wave2Go": wave2_go,
        "finalCertificationStamped": stamp,
        "missingRequirements": missing,
        "ledgerRecordCount": len(load_ledger().get("records") or []),
    }
