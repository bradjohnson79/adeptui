"""Release-defined production workflow gate sets (M41 4.1B-L)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .certified_registry import production_ready_keys

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_GATE = _REPO_ROOT / "config" / "video-workflows" / "production-gate.json"
_GO_STAMP_41BL = (
    _REPO_ROOT / "docs" / "release-gate" / "m41" / "M41_41BL_FINAL_GO_REPORT.md"
)
_GO_STAMP_41B = (
    _REPO_ROOT / "docs" / "release-gate" / "m41" / "M41_41B_FINAL_CERTIFICATION.md"
)
_WAVE6_CONSUMER_CONTRACT = (
    _REPO_ROOT / "artifacts" / "m41" / "41bl" / "wave6_consumer_contract_results.json"
)


@lru_cache(maxsize=2)
def load_production_gate(path: str | None = None) -> dict[str, Any]:
    gate_path = Path(path) if path else _DEFAULT_GATE
    if not gate_path.is_file():
        return {
            "requiredLocalProductionWorkflowKeys": [],
            "requiredCloudProductionWorkflowKeys": [],
            "enabledCloudProductionWorkflowKeys": [],
        }
    data = json.loads(gate_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def reload_production_gate() -> None:
    load_production_gate.cache_clear()


def required_local_keys() -> list[str]:
    return list(load_production_gate().get("requiredLocalProductionWorkflowKeys") or [])


def required_cloud_keys() -> list[str]:
    return list(load_production_gate().get("requiredCloudProductionWorkflowKeys") or [])


def enabled_cloud_keys() -> list[str]:
    """Release-defined enabled cloud keys (not mutated by credential presence)."""
    return list(load_production_gate().get("enabledCloudProductionWorkflowKeys") or [])


def _go_stamp_present() -> bool:
    for stamp in (_GO_STAMP_41BL, _GO_STAMP_41B):
        if not stamp.is_file():
            continue
        text = stamp.read_text(encoding="utf-8", errors="ignore")
        # Accept prose ("**Verdict:** **GO**") and table ("| **Verdict** | **GO** |") forms.
        go = (
            "**Verdict:** **GO**" in text
            or "Verdict:** GO" in text
            or "| **Verdict** | **GO** |" in text
        )
        nogo = (
            "**Verdict:** **NO-GO**" in text
            or "Verdict:** NO-GO" in text
            or "| **Verdict** | **NO-GO** |" in text
        )
        if stamp == _GO_STAMP_41BL:
            if nogo and not go:
                return False
            if go:
                return True
            continue
        if go and not _GO_STAMP_41BL.is_file():
            return True
    return False


def _wave6_consumer_contract_passed() -> bool:
    """L-10B: Wave 6 surfaces consume Certified Library via public contracts only."""
    path = _WAVE6_CONSUMER_CONTRACT
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    return bool(data.get("wave6ConsumerContractPassed") or data.get("passed"))


def evaluate_gate() -> dict[str, Any]:
    certified = production_ready_keys()
    certified_set = set(certified)
    local_req = required_local_keys()
    cloud_req = required_cloud_keys()
    cloud_enabled = enabled_cloud_keys()
    missing_local = [k for k in local_req if k not in certified_set]
    missing_enabled_cloud = [k for k in cloud_enabled if k not in certified_set]
    local_ok = len(missing_local) == 0 and len(local_req) > 0
    cloud_ok = len(missing_enabled_cloud) == 0
    go_stamp = _go_stamp_present()
    consumer_ok = _wave6_consumer_contract_passed()
    # Wave 6 production activation = local set certified + GO stamp + consumer contract.
    # Cloud enablement is separate: enabled cloud keys must be certified to advertise.
    production_unlocked = bool(local_ok and go_stamp and consumer_ok)
    return {
        "requiredLocalProductionWorkflowKeys": local_req,
        "requiredCloudProductionWorkflowKeys": cloud_req,
        "enabledCloudProductionWorkflowKeys": cloud_enabled,
        "certifiedWorkflowKeys": certified,
        "missingRequiredLocalKeys": missing_local,
        "missingEnabledCloudKeys": missing_enabled_cloud,
        "localGateSatisfied": local_ok,
        "cloudGateSatisfied": cloud_ok,
        "phase41bGo": go_stamp,
        "wave6ConsumerContractPassed": consumer_ok,
        "wave6ProductionActivationUnlocked": production_unlocked,
        "wave6MediaExecutionUnlocked": production_unlocked,
        "phase": "M41-4.1B-L",
    }
