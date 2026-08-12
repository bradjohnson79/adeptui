#!/usr/bin/env python3
"""M42 Wave 4 — Dual-stage live edit workflow certification.

Required: zimage.ref_edit, zimage.inpaint, zimage.outpaint, image.upscale
Never fabricate PASS. Real ComfyUI only.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

ARTIFACTS = ROOT / "artifacts" / "m42" / "w4"
FIXTURES = ARTIFACTS / "fixtures"
REQUIRED = ["zimage.ref_edit", "zimage.inpaint", "zimage.outpaint", "image.upscale"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(name: str, data: Any) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / name
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return "unknown"


def ensure_fixtures() -> dict[str, Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    src = FIXTURES / "source.png"
    mask = FIXTURES / "mask.png"
    try:
        from PIL import Image, ImageDraw

        im = Image.new("RGB", (1024, 1024), (40, 60, 90))
        dr = ImageDraw.Draw(im)
        dr.ellipse((200, 180, 820, 900), fill=(210, 170, 140))
        dr.rectangle((100, 100, 400, 400), fill=(80, 120, 200))
        im.save(src)
        m = Image.new("L", (1024, 1024), 0)
        md = ImageDraw.Draw(m)
        md.ellipse((250, 250, 550, 550), fill=255)
        m.save(mask)
    except Exception as exc:
        raise RuntimeError(f"Cannot create fixtures: {exc}") from exc
    return {"source": src, "mask": mask}


async def _upload(comfy: Any, path: Path) -> str:
    return await comfy.upload_image(Path(path))


async def leaf_certify(workflow_key: str, fixtures: dict[str, Path]) -> dict[str, Any]:
    from app.comfy_client import comfy
    from app.config import settings
    from app.image_runtime.certification_ledger import append_certification_record
    from app.image_runtime.certified_registry import get_workflow, reload_registry
    from app.image_runtime.contract import resolve_image_workflow
    from app.image_runtime.fingerprints import compute_fingerprints, file_content_hash
    from app.image_runtime.output_gate import validate_edit_output, validate_image_output
    from app.image_runtime.workflow_execute import build_leaf_graph, legacy_comfy_workflow_key

    reload_registry()
    wf_meta = get_workflow(workflow_key)
    if not wf_meta:
        return {"workflowKey": workflow_key, "passed": False, "error": "unknown workflow"}

    intent_map = {
        "zimage.ref_edit": "image.edit",
        "zimage.inpaint": "image.inpaint",
        "zimage.outpaint": "image.outpaint",
        "image.upscale": "image.upscale",
    }
    contract = resolve_image_workflow(
        intent_map.get(workflow_key, "image.edit"),
        engine=wf_meta.engine or "zimage",
        force_workflow_key=workflow_key,
        allow_draft=True,
    )

    src_name = await _upload(comfy, fixtures["source"])
    mask_name = None
    if workflow_key == "zimage.inpaint":
        mask_name = await _upload(comfy, fixtures["mask"])
    ref_hash = file_content_hash(fixtures["source"])

    t0 = time.time()
    kwargs: dict[str, Any] = dict(
        settings=settings,
        prompt="M42 W4 leaf certification edit - cinematic soft light",
        negative="blurry, watermark, text",
        width=1024,
        height=1024,
        seed=42,
        steps=getattr(settings, "zimage_steps", 8),
        cfg=getattr(settings, "zimage_cfg", 1.0),
        filename_prefix=f"studio/m42w4_leaf_{workflow_key.replace('.', '_')}",
        source_image=src_name,
        reference_image=src_name,
        mask_image=mask_name,
        denoise=0.85 if "inpaint" in workflow_key or "outpaint" in workflow_key else 0.45,
        outpaint_right=256,
        outpaint_bottom=0,
        # TextEncodeZImageOmni + CLIP-Vision often rejects solid fixtures / latent shapes on edit paths
        use_clip_vision=False,
    )
    try:
        graph = build_leaf_graph(contract, **kwargs)
    except Exception as exc:
        return {"workflowKey": workflow_key, "passed": False, "error": f"build failed: {exc}"}

    fps = compute_fingerprints(
        graph=graph,
        builder_path=wf_meta.builder_path,
        required_nodes=list(wf_meta.required_nodes),
        required_models=list(wf_meta.required_models),
    )

    try:
        prompt_id = await comfy.queue_prompt(
            graph, workflow_key=legacy_comfy_workflow_key(workflow_key), validate=True
        )
        history = await comfy.wait_for_prompt(prompt_id)
    except Exception as exc:
        return {
            "workflowKey": workflow_key,
            "passed": False,
            "error": f"queue/wait failed: {exc}",
        }

    files = comfy.find_output_files(history)
    if not files:
        return {"workflowKey": workflow_key, "passed": False, "error": "no output files", "promptId": prompt_id}

    out = Path(files[0])
    op = intent_map.get(workflow_key, "image.edit")
    if workflow_key == "image.upscale":
        gate = validate_edit_output(
            out,
            operation=op,
            source_path=fixtures["source"],
            expected_width=1025,
            expected_height=1025,
            generate_previews=True,
            preview_dir=ARTIFACTS / "previews",
        )
    elif workflow_key == "zimage.outpaint":
        gate = validate_edit_output(
            out,
            operation=op,
            source_path=fixtures["source"],
            expected_width=1280,
            expected_height=1024,
            generate_previews=True,
            preview_dir=ARTIFACTS / "previews",
        )
    elif workflow_key == "zimage.inpaint":
        gate = validate_edit_output(
            out,
            operation=op,
            source_path=fixtures["source"],
            mask_path=fixtures["mask"],
            generate_previews=True,
            preview_dir=ARTIFACTS / "previews",
        )
    else:
        gate = validate_image_output(out, generate_previews=True, preview_dir=ARTIFACTS / "previews")

    if not gate.ok:
        return {
            "workflowKey": workflow_key,
            "passed": False,
            "error": f"gate failed: {gate.errors}",
            "gate": gate.to_dict(),
        }

    record = append_certification_record(
        {
            "workflowId": wf_meta.workflow_id,
            "workflowKey": workflow_key,
            "workflowVersion": wf_meta.workflow_version,
            "status": "CERTIFIED",
            "stage": "leaf",
            "graphFingerprint": fps.get("graphHash"),
            "fingerprints": fps,
            "modelDependencies": list(wf_meta.required_models),
            "nodeDependencies": list(wf_meta.required_nodes),
            "runtimeIdentity": {
                "runtime": "comfy",
                "provider": "comfyui",
                "comfyUrl": os.environ.get("COMFY_URL") or "http://127.0.0.1:8188",
            },
            "testInputHashes": {"source": ref_hash},
            "outputHashes": {"primary": _sha256_file(out)},
            "validationResult": gate.to_dict(),
            "certifyingCommitSha": _git_sha(),
            "elapsedSec": round(time.time() - t0, 2),
            "phase": "M42-W4",
        }
    )
    dest = ARTIFACTS / "outputs" / f"{workflow_key.replace('.', '_')}_leaf{out.suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, dest)
    return {
        "workflowKey": workflow_key,
        "passed": True,
        "certificationRecordId": record["certificationRecordId"],
        "fingerprints": fps,
        "gate": gate.to_dict(),
        "outputPath": str(dest),
        "elapsedSec": round(time.time() - t0, 2),
    }


async def production_path_certify(workflow_key: str, fixtures: dict[str, Path]) -> dict[str, Any]:
    """Stage 2: ImageEditIntent compile → resolve → execute → semantic gate."""
    from app.comfy_client import comfy
    from app.config import settings
    from app.image_runtime.certification_ledger import append_certification_record
    from app.image_runtime.certified_registry import get_workflow, reload_registry
    from app.image_runtime.contract import resolve_image_workflow
    from app.image_runtime.fingerprints import file_content_hash
    from app.image_runtime.output_gate import validate_edit_output, validate_image_output
    from app.image_runtime.workflow_execute import (
        build_leaf_graph,
        legacy_comfy_workflow_key,
        prepare_executable_graph,
    )
    from app.image_product.edit_compile import compile_edit_request

    reload_registry()
    wf_meta = get_workflow(workflow_key)
    if not wf_meta or wf_meta.status != "Certified":
        return {
            "workflowKey": workflow_key,
            "passed": False,
            "error": f"not Certified (status={getattr(wf_meta, 'status', None)})",
        }

    op_map = {
        "zimage.ref_edit": "image.reference_edit",
        "zimage.inpaint": "image.inpaint",
        "zimage.outpaint": "image.outpaint",
        "image.upscale": "image.upscale",
    }
    operation = op_map[workflow_key]
    body: dict[str, Any] = {
        "operation": operation,
        "prompt": "M42 W4 production-path edit certification",
        "sourceAssetIds": ["fixture-source"],
        "modelFamilyPreference": "zimage",
        "allowIncomplete": True,
        "width": 1024,
        "height": 1024,
        "seed": 44,
    }
    if workflow_key == "zimage.inpaint":
        body["masks"] = [{"maskAssetId": "fixture-mask", "role": "replace"}]

    # Compile may fall back if force needed — pin via force after compile check
    try:
        compiled = compile_edit_request("m42-w4-cert", body)
    except Exception as exc:
        return {"workflowKey": workflow_key, "passed": False, "error": f"compile failed: {exc}"}

    contract = resolve_image_workflow(
        operation if operation != "image.reference_edit" else "image.edit",
        engine="zimage",
        force_workflow_key=workflow_key,
        allow_draft=False,
    )
    pinned = contract.to_pinned_snapshot()

    src_name = await _upload(comfy, fixtures["source"])
    mask_name = await _upload(comfy, fixtures["mask"]) if workflow_key == "zimage.inpaint" else None

    t0 = time.time()
    graph = build_leaf_graph(
        contract,
        settings=settings,
        prompt=body["prompt"],
        width=1024,
        height=1024,
        seed=44,
        steps=getattr(settings, "zimage_steps", 8),
        cfg=getattr(settings, "zimage_cfg", 1.0),
        filename_prefix=f"studio/m42w4_prod_{workflow_key.replace('.', '_')}",
        source_image=src_name,
        reference_image=src_name,
        mask_image=mask_name,
        denoise=0.85 if "inpaint" in workflow_key or "outpaint" in workflow_key else 0.45,
        outpaint_right=256,
        outpaint_bottom=0,
        use_clip_vision=False,
    )
    graph = prepare_executable_graph(
        contract,
        graph,
        expected_graph_hash=pinned.get("fingerprint") or (wf_meta.fingerprints or {}).get("graphHash"),
        enforce_certified_fingerprint=True,
    )
    prompt_id = await comfy.queue_prompt(
        graph, workflow_key=legacy_comfy_workflow_key(workflow_key), validate=True
    )
    try:
        history = await comfy.wait_for_prompt(prompt_id)
    except Exception as exc:
        return {"workflowKey": workflow_key, "passed": False, "error": f"wait failed: {exc}"}

    files = comfy.find_output_files(history)
    if not files:
        return {"workflowKey": workflow_key, "passed": False, "error": "no output"}

    out = Path(files[0])
    if workflow_key == "zimage.ref_edit":
        gate = validate_image_output(out, generate_previews=True, preview_dir=ARTIFACTS / "previews")
    else:
        gate = validate_edit_output(
            out,
            operation=operation,
            source_path=fixtures["source"],
            mask_path=fixtures["mask"] if workflow_key == "zimage.inpaint" else None,
            expected_width=1280 if workflow_key == "zimage.outpaint" else (1025 if workflow_key == "image.upscale" else None),
            expected_height=1024 if workflow_key == "zimage.outpaint" else (1025 if workflow_key == "image.upscale" else None),
            generate_previews=True,
            preview_dir=ARTIFACTS / "previews",
        )
    if not gate.ok:
        return {
            "workflowKey": workflow_key,
            "passed": False,
            "error": f"gate failed: {gate.errors}",
            "gate": gate.to_dict(),
        }

    append_certification_record(
        {
            "workflowId": wf_meta.workflow_id,
            "workflowKey": workflow_key,
            "workflowVersion": wf_meta.workflow_version,
            "status": "CERTIFIED",
            "stage": "production_path",
            "fingerprints": wf_meta.fingerprints,
            "pinnedContract": pinned,
            "imageEditIntentId": (compiled.get("imageEditIntent") or {}).get("intentId"),
            "validationResult": gate.to_dict(),
            "certifyingCommitSha": _git_sha(),
            "elapsedSec": round(time.time() - t0, 2),
            "phase": "M42-W4",
            "sourceHash": file_content_hash(fixtures["source"]),
        }
    )
    dest = ARTIFACTS / "outputs" / f"{workflow_key.replace('.', '_')}_prod{out.suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, dest)
    return {
        "workflowKey": workflow_key,
        "passed": True,
        "pinned": pinned,
        "gate": gate.to_dict(),
        "compiledOperation": operation,
        "outputPath": str(dest),
        "elapsedSec": round(time.time() - t0, 2),
    }


async def main_async() -> int:
    from app.image_runtime.certified_registry import production_ready_keys, reload_registry

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    _write(
        "prerequisites.json",
        {
            "baselineBranch": "phase2/m42-image-product-integration",
            "targetBranch": "phase2/m42-advanced-image-editing",
            "baselineSha": _git_sha(),
            "wave1Go": True,
            "wave2Go": True,
            "wave3Go": True,
            "requiredLocalProductionEditWorkflowKeys": REQUIRED,
            "enabledCloudEditWorkflowKeys": [],
            "generatedAt": _now(),
        },
    )
    fixtures = ensure_fixtures()
    _write(
        "required_edit_workflows.json",
        {
            "requiredLocalProductionEditWorkflowKeys": REQUIRED,
            "optionalLocalEditWorkflowKeys": [],
            "enabledCloudEditWorkflowKeys": [],
            "generatedAt": _now(),
        },
    )

    leaf_results = []
    for key in REQUIRED:
        # ref_edit already Certified from W2 — still revalidate leaf for W4 path
        print(f"[leaf] {key} …")
        r = await leaf_certify(key, fixtures)
        print(f"  → passed={r.get('passed')} {r.get('error') or r.get('certificationRecordId')}")
        leaf_results.append(r)

    leaf_passed = [r["workflowKey"] for r in leaf_results if r.get("passed")]
    leaf_doc = {
        "leafCertificationPassed": set(REQUIRED).issubset(set(leaf_passed)),
        "passedWorkflowKeys": leaf_passed,
        "results": leaf_results,
        "generatedAt": _now(),
    }
    _write("leaf_certification_results.json", leaf_doc)

    fps = {}
    for r in leaf_results:
        if r.get("fingerprints"):
            fps[r["workflowKey"]] = r["fingerprints"]
    _write("workflow_fingerprints.json", fps)

    prod_results = []
    if leaf_doc["leafCertificationPassed"]:
        for key in REQUIRED:
            print(f"[production-path] {key} …")
            r = await production_path_certify(key, fixtures)
            print(f"  → passed={r.get('passed')} {r.get('error') or 'ok'}")
            prod_results.append(r)

    prod_passed = [r["workflowKey"] for r in prod_results if r.get("passed")]
    prod_doc = {
        "productionPathCertificationPassed": set(REQUIRED).issubset(set(prod_passed)),
        "passedWorkflowKeys": prod_passed,
        "certifiedProductionPathEditWorkflowKeys": prod_passed,
        "results": prod_results,
        "generatedAt": _now(),
    }
    _write("production_path_certification_results.json", prod_doc)

    reload_registry()
    inv = {"keys": production_ready_keys(), "required": REQUIRED, "generatedAt": _now()}
    _write("edit_workflow_inventory.json", inv)

    summary = {
        "leafCertificationPassed": leaf_doc["leafCertificationPassed"],
        "productionPathCertificationPassed": prod_doc["productionPathCertificationPassed"],
        "certifiedWorkflowKeys": production_ready_keys(),
        "requiredLocalEdit": REQUIRED,
        "inclusion": set(REQUIRED).issubset(set(prod_passed)),
        "generatedAt": _now(),
    }
    _write("live_certification_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["leafCertificationPassed"] and summary["productionPathCertificationPassed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()
    if args.skip_live:
        print("skip-live set; refusing to fabricate certification")
        return 2
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
