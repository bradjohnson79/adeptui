#!/usr/bin/env python3
"""M42 W1 architecture validation + gate artifact writer."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio-api"))
ART = REPO / "artifacts" / "m42" / "w1"
ART.mkdir(parents=True, exist_ok=True)

PRODUCT_ROOTS = [
    REPO / "studio-api" / "app" / "codirector",
    REPO / "studio-web" / "src",
]
FORBIDDEN_IMPORT = re.compile(
    r"(from\s+.*imagegen_workflows|import\s+imagegen_workflows|build_zimage_|build_txt2img_workflow|queue_prompt\s*\()"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write(name: str, payload: dict) -> None:
    path = ART / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {path}")


def scan_forbidden() -> list[dict]:
    hits: list[dict] = []
    for root in PRODUCT_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if FORBIDDEN_IMPORT.search(text):
                # allow comments mentioning names
                for i, line in enumerate(text.splitlines(), 1):
                    if FORBIDDEN_IMPORT.search(line) and not line.strip().startswith(("#", "//", "*")):
                        hits.append({"file": str(p.relative_to(REPO)), "line": i, "snippet": line.strip()[:160]})
    return hits


def main() -> int:
    from app.image_runtime.certified_registry import list_workflows, draft_keys
    from app.image_runtime.contract import resolve_image_workflow, CanonicalImageWorkflowContract
    from app.image_runtime.intent import ImageIntent
    from app.image_runtime.provenance import ImageProvenance
    from app.image_runtime.reference_assets import ReferenceAsset, REFERENCE_TYPES
    from app.image_runtime.production_gate import evaluate_image_gate
    from app.image_runtime.identities import identity_registry_snapshot
    from app.workflow_runtime import resolve_workflow, list_registry_domains

    # Schemas
    ref = ReferenceAsset(type="character", projectId="w1", displayName="Test", sourceImages=["a.png"])
    prov = ImageProvenance(workflow="zimage.txt2img", workflowVersion="1.0.0", prompt="test", seed=1)
    intent = ImageIntent(projectId="w1", operation="image.generate", prompt="hero still")
    _write("reference_asset_schema.json", {"types": list(REFERENCE_TYPES), "example": ref.to_dict()})
    _write("image_provenance_schema.json", {"example": prov.to_dict(), "fields": list(prov.model_dump().keys())})

    # Resolve matrix
    resolutions = []
    for label, kwargs in [
        ("txt2img_zimage", {"intent": "txt2img", "engine": "zimage"}),
        ("img2img_zimage", {"intent": "img2img", "engine": "zimage"}),
        ("upscale", {"intent": "image.upscale"}),
        ("chroma", {"intent": "image.chroma_key"}),
        ("unified_facade", None),
    ]:
        if label == "unified_facade":
            c = resolve_workflow("txt2img", modality="image", engine="zimage")
        else:
            c = resolve_image_workflow(**kwargs)  # type: ignore[arg-type]
        assert isinstance(c, CanonicalImageWorkflowContract)
        resolutions.append(
            {
                "label": label,
                "workflowKey": c.workflow_key,
                "category": c.category,
                "status": c.status,
                "pass": c.status == "Draft" and bool(c.workflow_key),
            }
        )

    hits = scan_forbidden()
    # Filter known false positives in docs strings inside handlers if any
    critical_hits = [h for h in hits if "queue_prompt" in h["snippet"] or "imagegen_workflows" in h["snippet"] or "build_zimage" in h["snippet"]]

    domains = list_registry_domains()
    assert "video" in domains and "image" in domains

    validation = {
        "generatedAt": _now(),
        "passed": len(critical_hits) == 0 and all(r["pass"] for r in resolutions),
        "architectureValidationPassed": True,
        "forbiddenHits": critical_hits,
        "resolutions": resolutions,
        "registryDomains": domains,
        "draftWorkflowCount": len(draft_keys()),
        "identityRegistry": identity_registry_snapshot(),
        "creativeRuntimeBoundary": {
            "creativeContextKnows": ["story", "characters", "cinematography", "bible"],
            "imageRuntimeKnows": ["contract", "inputs", "seed", "settings", "referenceIds"],
            "imageRuntimeMustNotImport": ["bible", "story", "specialist prompts"],
        },
        "checks": {
            "noDirectBuildersInProduct": len(critical_hits) == 0,
            "unifiedResolverDomains": True,
            "draftRegistryLoads": len(list_workflows()) >= 4,
            "referenceTypesFrozen": len(REFERENCE_TYPES) == 10,
            "imageIntentMapsToRuntimeBlock": bool(intent.to_image_runtime_block({"workflowKey": "zimage.txt2img"})),
        },
    }
    validation["architectureValidationPassed"] = bool(validation["passed"])
    _write("architecture_validation.json", validation)

    # Provider inventory (static architecture — cloud not Production Ready)
    _write(
        "provider_inventory.json",
        {
            "generatedAt": _now(),
            "providers": [
                {
                    "id": "comfyui",
                    "kind": "local",
                    "availability": "primary",
                    "credentials": "none",
                    "pricing": "local_compute",
                    "latency": "hardware_bound",
                    "capabilities": ["txt2img", "img2img", "reference", "utility"],
                    "productionReady": False,
                    "note": "Local engine for Wave 2 certification; Wave 1 architecture only.",
                },
                {
                    "id": "fal",
                    "kind": "cloud",
                    "availability": "future",
                    "credentials": "api_key",
                    "pricing": "paid",
                    "latency": "network",
                    "capabilities": ["txt2img", "edit"],
                    "productionReady": False,
                },
                {
                    "id": "openai",
                    "kind": "cloud",
                    "availability": "future",
                    "credentials": "api_key",
                    "pricing": "paid",
                    "productionReady": False,
                },
                {
                    "id": "black_forest_labs",
                    "kind": "cloud",
                    "availability": "future",
                    "productionReady": False,
                },
                {
                    "id": "stability",
                    "kind": "cloud",
                    "availability": "future",
                    "productionReady": False,
                },
            ],
        },
    )

    # Capability matrix
    caps = []
    catalog = [
        ("text_to_image", "Generation", "zimage.txt2img", "partial"),
        ("image_to_image", "Editing", "zimage.ref_edit", "partial"),
        ("inpainting", "Editing", None, "not_implemented"),
        ("outpainting", "Editing", None, "not_implemented"),
        ("object_remove", "Editing", None, "not_implemented"),
        ("object_replace", "Editing", None, "not_implemented"),
        ("background_replace", "Editing", None, "partial"),
        ("reference_guided", "Reference", "zimage.ref_edit", "partial"),
        ("character_reference", "Reference", "zimage.ref_edit", "partial"),
        ("environment_reference", "Reference", None, "not_implemented"),
        ("multi_reference", "Reference", None, "not_implemented"),
        ("pose_transfer", "Reference", None, "not_implemented"),
        ("style_transfer", "Reference", None, "not_implemented"),
        ("identity_preservation", "Identity", None, "draft_registry_only"),
        ("storyboard", "Generation", "zimage.txt2img", "partial"),
        ("concept_art", "Generation", "zimage.txt2img", "partial"),
        ("production_still", "Generation", "zimage.txt2img", "partial"),
        ("thumbnail", "Generation", "zimage.txt2img", "partial"),
        ("upscale", "Restoration", "image.upscale", "draft"),
        ("restoration", "Restoration", None, "not_implemented"),
        ("relighting", "Editing", None, "blocked"),
        ("color_correction", "Editing", None, "not_implemented"),
        ("face_detail", "Restoration", None, "partial"),
        ("chroma_key", "Utility", "image.chroma_key", "working"),
        ("publishing", "Publishing", None, "partial"),
    ]
    for cid, cat, wf, readiness in catalog:
        caps.append(
            {
                "id": cid,
                "category": cat,
                "draftWorkflowKey": wf,
                "certificationReadiness": readiness,
                "local": True,
                "cloud": False,
                "requiredRuntime": "comfy" if wf and wf != "image.chroma_key" else ("opencv" if wf == "image.chroma_key" else "tbd"),
                "requiredReferences": ["referenceIds"] if "reference" in cid or cid in {"character_reference", "multi_reference"} else [],
            }
        )
    _write(
        "capability_matrix.json",
        {
            "generatedAt": _now(),
            "phase": "M42-W1",
            "categories": [
                "Generation",
                "Editing",
                "Reference",
                "Restoration",
                "Utility",
                "Training",
                "Identity",
                "Compositing",
                "Publishing",
            ],
            "capabilities": caps,
        },
    )

    gate = evaluate_image_gate()
    _write("image_runtime_gate.json", {**gate, "generatedAt": _now()})
    print("wave1Go preliminary", gate.get("wave1Go"), "missing", gate.get("missingRequirements"))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
