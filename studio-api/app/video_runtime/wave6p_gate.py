"""Wave 6P product/beta gate — exact required-condition inclusion (W6P-20)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .production_gate import evaluate_gate

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ARTIFACTS = _REPO_ROOT / "artifacts" / "m41" / "w6p"
_FINAL_CERT = _REPO_ROOT / "docs" / "release-gate" / "m41" / "M41_W6P_FINAL_CERTIFICATION.md"


def _artifact_pass(name: str, *keys: str) -> bool:
    path = _ARTIFACTS / name
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    for key in keys:
        if data.get(key) is True or data.get("passed") is True:
            return True
    return bool(data.get("pass") or data.get("ok"))


def _final_go_stamp() -> bool:
    if not _FINAL_CERT.is_file():
        return False
    text = _FINAL_CERT.read_text(encoding="utf-8", errors="ignore")
    go = "| **Verdict** | **GO** |" in text or "**Verdict:** **GO**" in text
    nogo = "| **Verdict** | **NO-GO** |" in text or "**Verdict:** **NO-GO**" in text
    return bool(go and not nogo)


def evaluate_wave6p_gate() -> dict[str, Any]:
    engine = evaluate_gate()
    prerequisite_engine_go = bool(
        engine.get("phase41bGo") and engine.get("wave6ProductionActivationUnlocked")
    )
    consumer = bool(engine.get("wave6ConsumerContractPassed"))

    flags = {
        "prerequisiteEngineGo": prerequisite_engine_go,
        "consumerContractPassed": consumer,
        "toolRegistryPassed": _artifact_pass("tool_registry_results.json", "toolRegistryPassed"),
        "productionIntentPassed": _artifact_pass(
            "production_intent_results.json", "productionIntentPassed"
        ),
        "plannerPassed": _artifact_pass("production_plan_results.json", "plannerPassed"),
        "codirectorUxPassed": _artifact_pass("codirector_ux_results.json", "codirectorUxPassed"),
        "directorIntegrationPassed": _artifact_pass(
            "director_integration_results.json", "directorIntegrationPassed"
        ),
        "timelineIntegrationPassed": _artifact_pass(
            "timeline_results.json", "timelineIntegrationPassed"
        ),
        "assetProvenancePassed": _artifact_pass(
            "asset_provenance_results.json", "assetProvenancePassed"
        ),
        "cancellationRecoveryPassed": _artifact_pass(
            "recovery_results.json", "cancellationRecoveryPassed"
        ),
        "persistencePassed": _artifact_pass("persistence_results.json", "persistencePassed"),
        "liveE2ePassed": _artifact_pass("live_e2e_results.json", "liveE2ePassed"),
        "playwrightPassed": _artifact_pass("playwright_results.json", "playwrightPassed"),
        "subagentBetaPassed": _artifact_pass("subagent_beta_results.json", "subagentBetaPassed"),
    }
    manual_path = _REPO_ROOT / "docs" / "release-gate" / "m41" / "M41_W6P_MANUAL_BETA_CHECKLIST.md"
    flags["manualBetaReady"] = manual_path.is_file()

    missing = [k for k, v in flags.items() if not v]
    stamp = _final_go_stamp()
    if not stamp:
        missing = list(missing) + ["finalCertificationGo"]
    wave6p_go = len(missing) == 0 and stamp

    return {
        "phase": "M41-W6P",
        **flags,
        "wave6pGo": wave6p_go,
        "missingRequirements": missing if not wave6p_go else [],
        "engineGate": {
            "phase41bGo": engine.get("phase41bGo"),
            "wave6ProductionActivationUnlocked": engine.get("wave6ProductionActivationUnlocked"),
            "wave6ConsumerContractPassed": engine.get("wave6ConsumerContractPassed"),
        },
    }
