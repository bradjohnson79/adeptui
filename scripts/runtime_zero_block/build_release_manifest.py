"""Freeze CURRENT_RELEASE_CAPABILITY_MANIFEST.json from live registries."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.capabilities.registry import CAPABILITIES  # noqa: E402
from app.capabilities.models import SCENECRAFT_RELEASE_EXCLUSION  # noqa: E402
from app.workflows.registry import DEFAULT_WORKFLOW_REGISTRY  # noqa: E402
from app.workflows.readiness import WORKFLOW_MODEL_COMPONENTS  # noqa: E402


def main() -> Path:
    out_dir = ROOT / "docs" / "release-gate" / "runtime-zero-block"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "CURRENT_RELEASE_CAPABILITY_MANIFEST.json"

    entries = []
    for cap in CAPABILITIES:
        # Map capability to workflows by shared tokens / capability tags.
        workflow_ids: list[str] = []
        for meta in DEFAULT_WORKFLOW_REGISTRY.list():
            caps = {c.lower() for c in meta.capabilities}
            if cap.id.lower() in caps or cap.id.lower().replace(".", "_") in meta.key.lower().replace(".", "_"):
                workflow_ids.append(meta.key)
            elif any(token in meta.key.lower() for token in cap.id.lower().split(".") if len(token) > 3):
                workflow_ids.append(meta.key)
        workflow_ids = sorted(set(workflow_ids))

        required_nodes: list[str] = []
        required_models: list[str] = []
        for wid in workflow_ids:
            meta = DEFAULT_WORKFLOW_REGISTRY.get(wid)
            if meta:
                required_nodes.extend(meta.compatibility.required_node_types)
            required_models.extend(WORKFLOW_MODEL_COMPONENTS.get(wid, ()))

        # Skip deferred roadmap-only rows from CURRENTLY_SUPPORTED freeze.
        if getattr(cap, "baseline_status", None) and str(getattr(cap.baseline_status, "value", cap.baseline_status)) == "deferred_version_1_2":
            continue

        entries.append(
            {
                "capabilityId": cap.id,
                "workflowIds": workflow_ids,
                "providerId": getattr(cap, "service_ref", None) or None,
                "adapterId": getattr(cap, "http_ref", None) or None,
                "releaseStatus": "CURRENTLY_SUPPORTED",
                "requiredNodeTypes": sorted(set(required_nodes)),
                "requiredPackages": [],
                "requiredModels": sorted(set(required_models)),
                "exposedSurfaces": [
                    s
                    for s in [
                        "ui" if getattr(cap, "http_ref", None) else None,
                        "codirector" if "codirector" in (cap.id + (cap.summary or "")).lower() else None,
                        "timeline" if "timeline" in cap.id.lower() else None,
                        "api",
                    ]
                    if s
                ],
            }
        )

    # Also include every registered workflow as its own catalog row when not already covered.
    covered = {wid for e in entries for wid in e["workflowIds"]}
    for meta in DEFAULT_WORKFLOW_REGISTRY.list():
        if meta.key in covered:
            continue
        entries.append(
            {
                "capabilityId": f"workflow.{meta.key}",
                "workflowIds": [meta.key],
                "providerId": meta.family,
                "adapterId": meta.builder_path,
                "releaseStatus": "CURRENTLY_SUPPORTED",
                "requiredNodeTypes": list(meta.compatibility.required_node_types),
                "requiredPackages": [],
                "requiredModels": list(WORKFLOW_MODEL_COMPONENTS.get(meta.key, ())),
                "exposedSurfaces": ["api", "workflow_registry", meta.modality],
            }
        )

    payload = {
        "frozenAt": datetime.now(timezone.utc).isoformat(),
        "freezeLaw": "No CURRENTLY_SUPPORTED row may be removed after Wave 3 starts without product-policy audit diff.",
        "scenecraftExclusion": SCENECRAFT_RELEASE_EXCLUSION,
        "entryCount": len(entries),
        "entries": sorted(entries, key=lambda e: e["capabilityId"]),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out_path)
    print("entries", len(entries))
    return out_path


if __name__ == "__main__":
    main()
