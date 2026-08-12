"""Image Runtime Readiness Report generator (M42 W2)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .capability_probe import probe_runtime_capabilities, write_capabilities_artifact
from .certified_registry import list_workflows
from .model_discovery import discover_modern_image_models, write_discovery_artifact
from .provider_registry import provider_inventory

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ARTIFACTS = _REPO_ROOT / "artifacts" / "m42" / "w2"


def generate_readiness_report() -> dict[str, Any]:
    discovery = discover_modern_image_models()
    caps = probe_runtime_capabilities()
    providers = provider_inventory()
    workflows = []
    for w in list_workflows():
        fam = (discovery.get("families") or {}).get(w.model_family) or {}
        available_for_cert = w.status in {"Draft", "Built", "SmokeTested"} and (
            fam.get("installed") or w.provider_kind == "local" and w.model_family == "zimage"
        )
        if w.status == "Blocked":
            available_for_cert = False
        if w.status == "Certified":
            available_for_cert = True
        workflows.append(
            {
                "workflowKey": w.workflow_key,
                "modelFamily": w.model_family,
                "status": w.status,
                "provider": w.provider,
                "availableForCertification": available_for_cert and w.status != "Deferred",
                "certificationRecordId": w.certification_record_id,
                "reason": (w.limitations[0] if w.limitations else ""),
            }
        )

    report = {
        "phase": "M42-W2",
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "title": "Image Runtime Readiness Report",
        "discovery": discovery,
        "capabilities": caps.get("capabilities"),
        "providers": providers,
        "workflows": workflows,
        "summary": {
            "certified": [w["workflowKey"] for w in workflows if w["status"] == "Certified"],
            "draft": [w["workflowKey"] for w in workflows if w["status"] == "Draft"],
            "deferred": [w["workflowKey"] for w in workflows if w["status"] == "Deferred"],
            "blocked": [w["workflowKey"] for w in workflows if w["status"] == "Blocked"],
            "availableForCertification": [
                w["workflowKey"] for w in workflows if w.get("availableForCertification")
            ],
        },
        "ModernModelDiscoveryComplete": bool(discovery.get("discoveryComplete")),
        "WorkflowFamiliesRegistered": all(
            any(w.model_family == fam for w in list_workflows())
            for fam in ("zimage", "flux", "qwen", "imagen")
        ),
        "ProviderRegistryExpanded": len(providers.get("providers") or []) >= 4,
        "CapabilityDetectionOperational": isinstance(caps.get("capabilities"), dict),
    }
    return report


def write_readiness_artifacts() -> dict[str, Path]:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    try:
        from .registry_sync import sync_registry_status_from_discovery

        sync_registry_status_from_discovery()
    except Exception:
        pass
    paths = {
        "discovery": write_discovery_artifact(_ARTIFACTS / "modern_model_discovery.json"),
        "capabilities": write_capabilities_artifact(_ARTIFACTS / "runtime_capabilities.json"),
    }
    inv = provider_inventory()
    inv_path = _ARTIFACTS / "provider_inventory.json"
    inv_path.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    paths["provider_inventory"] = inv_path

    report = generate_readiness_report()
    report_path = _ARTIFACTS / "image_runtime_readiness.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    paths["readiness"] = report_path

    md_path = _REPO_ROOT / "docs" / "release-gate" / "m42" / "M42_W2_IMAGE_RUNTIME_READINESS_REPORT.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    lines = [
        "# M42 Wave 2 — Image Runtime Readiness Report",
        "",
        f"Generated: `{report['generatedAt']}`",
        "",
        "## Summary",
        "",
        f"- Certified: {', '.join(summary['certified']) or '(none)'}",
        f"- Draft: {', '.join(summary['draft']) or '(none)'}",
        f"- Deferred: {', '.join(summary['deferred']) or '(none)'}",
        f"- Blocked: {', '.join(summary['blocked']) or '(none)'}",
        f"- Available for certification: {', '.join(summary['availableForCertification']) or '(none)'}",
        "",
        "## Model families",
        "",
    ]
    for fam, data in (report.get("discovery") or {}).get("families", {}).items():
        lines.append(
            f"- **{fam}**: installed={data.get('installed')} statusHint={data.get('statusHint')} — {data.get('reason')}"
        )
    lines.extend(["", "## Workflows", ""])
    for w in report["workflows"]:
        lines.append(
            f"- `{w['workflowKey']}` — {w['status']} (family={w['modelFamily']}, certifiable={w['availableForCertification']})"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    paths["readiness_md"] = md_path
    return paths
