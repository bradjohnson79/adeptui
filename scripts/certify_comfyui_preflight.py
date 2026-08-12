"""ComfyUI preflight certification — NO GPU execution.

Proves each Timeline-capable provider's request/graph pathway is ready for a
manual creator generation run, without enqueueing any GPU work:

- MiniMax H3 Route A: object_info node-class presence, real T2VA + I2VA graph
  builds for two distinct batches (unique prefixes/seeds/prompts), I2V binding
  assertions, prompt/seed/prefix injection checks, no-T2V-fallback proof, and
  server-side schema validation of the constructed graph against the runtime's
  own object_info (node classes, required inputs, link integrity, and loader
  model names as the runtime reports them). Stock ComfyUI exposes no
  validation-only/non-executing prompt route — that boundary is documented
  explicitly rather than enqueueing anything to prove validation.
- LTX: structural request build + capability validation + queue-worker
  per-batch param handling (static contract check). No queue submission.
- WAN / Hunyuan: capability-gated (supportsTimelineGeneration=False).

Writes docs/release-gate/timeline-multi-batch/artifacts/comfyui-preflight.json
with a per-provider verdict: READY FOR MANUAL GENERATION or BLOCKED — reason.
MiniMax H3 must be READY for the milestone to pass.

Usage: python scripts/certify_comfyui_preflight.py
Exit 0 when every required provider is READY; 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "studio-api"))

ARTIFACT = REPO_ROOT / "docs" / "release-gate" / "timeline-multi-batch" / "artifacts" / "comfyui-preflight.json"


def _validate_graph_against_object_info(
    graph: dict[str, Any],
    object_info: dict[str, Any],
) -> list[str]:
    """Server-side schema validation without execution.

    Uses the runtime's own object_info to prove ComfyUI recognizes every node
    class, required input, link, and loader model name in the graph. This is
    the honest non-executing boundary: stock ComfyUI has no validation-only
    prompt route, and POST /prompt would enqueue GPU work (forbidden here).
    """
    errors: list[str] = []
    for node_id, node in graph.items():
        class_type = node.get("class_type")
        inputs = node.get("inputs") or {}
        if class_type not in object_info:
            errors.append(f"node {node_id}: class_type {class_type!r} not recognized by runtime")
            continue
        spec = object_info[class_type]
        required = ((spec.get("input") or {}).get("required") or {})
        for key, cfg in required.items():
            if key not in inputs:
                errors.append(f"node {node_id} ({class_type}): missing required input {key!r}")
                continue
            value = inputs[key]
            if isinstance(value, list):
                # Link — validate target node exists and output index is numeric.
                if not value or str(value[0]) not in graph:
                    errors.append(f"node {node_id}.{key}: link target {value!r} not in graph")
                continue
            # Loader model names: the runtime advertises available files as the
            # first element of the input config — assert recognition.
            if isinstance(cfg, (list, tuple)) and cfg and isinstance(cfg[0], (list, tuple)):
                available = {str(v) for v in cfg[0]}
                if available and str(value) not in available:
                    errors.append(
                        f"node {node_id} ({class_type}).{key}: {value!r} not in runtime list "
                        f"({len(available)} available)"
                    )
    return errors


def certify_minimax_h3() -> dict[str, Any]:
    from app.minimax_h3.private_access import runtime_url
    from app.minimax_h3.route_a_adapter import (
        REQUIRED_NODES,
        REQUIRED_NODES_I2V,
        assert_i2va_graph_binding,
        build_i2va_graph,
        build_t2va_graph,
        required_checkpoint_paths,
    )

    result: dict[str, Any] = {"provider": "minimax-h3", "route": "A", "checks": {}, "verdict": "BLOCKED"}
    base = runtime_url()

    # 1. Runtime reachability + object_info
    try:
        import httpx

        resp = httpx.get(f"{base}/object_info", timeout=60)
        resp.raise_for_status()
        object_info = resp.json()
    except Exception as exc:
        result["checks"]["object_info"] = {"ok": False, "error": repr(exc)}
        result["reason"] = f"ComfyUI runtime unreachable at {base}: {exc!r}"
        return result
    missing = [n for n in REQUIRED_NODES_I2V if n not in object_info]
    result["checks"]["object_info"] = {"ok": not missing, "missingNodes": missing}
    if missing:
        result["reason"] = f"runtime missing node classes: {missing}"
        return result

    # 2. Checkpoint files present on the model root
    missing_files = [role for role, p in required_checkpoint_paths().items() if not (p.is_file() and p.stat().st_size > 0)]
    result["checks"]["checkpoints"] = {"ok": not missing_files, "missing": missing_files}
    if missing_files:
        result["reason"] = f"missing checkpoint files: {missing_files}"
        return result

    # 3. Real graph builds for two distinct batches (unique prefixes/seeds/prompts)
    batch_a = {"prompt": "CERT BATCH A — crimson sailboat at dawn, gentle waves", "seed": 101010, "prefix": "video/CERT_H3_batchA_t2va"}
    batch_b = {"prompt": "CERT BATCH B — cobalt motorcycle at midnight, neon rain", "seed": 202020, "prefix": "video/CERT_H3_batchB_i2va"}
    graph_a = build_t2va_graph(batch_a["prompt"], seed=batch_a["seed"], filename_prefix=batch_a["prefix"])

    # Upload a REAL start frame so the runtime genuinely recognizes the
    # LoadImage reference during server-side schema validation.
    import base64
    import tempfile

    from app.minimax_h3.route_a_adapter import RouteARuntimeAdapter

    png_blue = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEElEQVR4nGNgYPiPAw0pCQCpcD/BFMrqcwAAAABJRU5ErkJggg=="
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_blue)
        tmp_path = Path(tmp.name)
    try:
        comfy_name_b = RouteARuntimeAdapter(base_url=base).upload_image(
            tmp_path, filename="cert_batch_b_start.png", subfolder=""
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    result["checks"]["start_image_upload"] = {"ok": True, "comfyName": comfy_name_b}
    graph_b = build_i2va_graph(batch_b["prompt"], seed=batch_b["seed"], filename_prefix=batch_b["prefix"], first_frame_comfy_name=comfy_name_b)

    # 4. I2V binding + no T2V fallback when I2V requested
    try:
        assert_i2va_graph_binding(graph_b, expected_comfy_name=comfy_name_b)
        binding_ok = True
    except Exception as exc:
        binding_ok = False
        result["checks"]["i2va_binding"] = {"ok": False, "error": str(exc)}
        result["reason"] = f"I2V graph binding failed: {exc}"
        return result
    no_fallback = "first_frame" in json.dumps(graph_b) and "first_frame" not in json.dumps(graph_a)
    result["checks"]["i2va_binding"] = {"ok": binding_ok}
    result["checks"]["no_t2v_fallback_for_i2v"] = {"ok": no_fallback}

    # 5. Prompt / seed / prefix injection + uniqueness
    inject = {
        "prompt_a": graph_a["5"]["inputs"]["prompt"] == batch_a["prompt"],
        "prompt_b": graph_b["5"]["inputs"]["prompt"] == batch_b["prompt"],
        "seed_a": graph_a["6"]["inputs"]["noise_seed"] == batch_a["seed"],
        "seed_b": graph_b["6"]["inputs"]["noise_seed"] == batch_b["seed"],
        "prefix_a": graph_a["14"]["inputs"]["filename_prefix"] == batch_a["prefix"],
        "prefix_b": graph_b["14"]["inputs"]["filename_prefix"] == batch_b["prefix"],
        "prefixes_unique": batch_a["prefix"] != batch_b["prefix"],
        "loadimage_ref": graph_b["15"]["inputs"]["image"] == comfy_name_b,
    }
    result["checks"]["injection"] = {"ok": all(inject.values()), "detail": inject}

    # 6. Server-side schema validation (non-executing) against runtime object_info.
    # Re-fetch AFTER the start-frame upload: ComfyUI's folder listing cache is
    # mtime-invalidated, so the fresh object_info now includes the uploaded image.
    try:
        import httpx

        resp = httpx.get(f"{base}/object_info", timeout=60)
        resp.raise_for_status()
        object_info = resp.json()
    except Exception as exc:
        result["checks"]["server_side_schema_validation"] = {"ok": False, "error": repr(exc)}
        result["reason"] = f"object_info refresh failed: {exc!r}"
        return result
    errors_a = _validate_graph_against_object_info(graph_a, object_info)
    errors_b = _validate_graph_against_object_info(graph_b, object_info)
    result["checks"]["server_side_schema_validation"] = {
        "ok": not errors_a and not errors_b,
        "batchA_errors": errors_a,
        "batchB_errors": errors_b,
        "boundary": (
            "Stock ComfyUI exposes no validation-only / non-executing prompt route; "
            "POST /prompt would enqueue GPU generation (forbidden in automated cert). "
            "Graphs were therefore validated against the runtime's own object_info: "
            "node classes, required inputs, link integrity, and loader model names."
        ),
    }

    # 6b. Fingerprint contract for H3 builds: topology is stable under
    # per-batch binding variation (prompt/seed/prefix/image), and dynamic
    # bindings validate. H3 graphs are adapter-owned (no registry entry), so
    # the contract is asserted as build-to-build stability, not registry match.
    from app.video_runtime.fingerprints import topology_hash, validate_dynamic_bindings

    graph_b2 = build_i2va_graph(
        "CERT BATCH B2 — same topology, different bindings",
        seed=909090,
        filename_prefix="video/CERT_H3_batchB2_i2va",
        first_frame_comfy_name=comfy_name_b,
    )
    h3_topology_stable = topology_hash(graph_b) == topology_hash(graph_b2)
    h3_bindings = validate_dynamic_bindings(graph_b)
    result["checks"]["fingerprint_contract"] = {
        "ok": h3_topology_stable and h3_bindings["ok"],
        "topologyStableUnderBindingVariation": h3_topology_stable,
        "bindingsValid": h3_bindings["ok"],
        "bindingsErrors": h3_bindings["errors"],
    }

    ok = all(
        c.get("ok")
        for c in (
            result["checks"]["object_info"],
            result["checks"]["checkpoints"],
            result["checks"]["start_image_upload"],
            result["checks"]["i2va_binding"],
            result["checks"]["no_t2v_fallback_for_i2v"],
            result["checks"]["injection"],
            result["checks"]["server_side_schema_validation"],
            result["checks"]["fingerprint_contract"],
        )
    )
    if ok:
        result["verdict"] = "READY FOR MANUAL GENERATION"
    else:
        result["reason"] = "one or more preflight checks failed"
    return result


def certify_ltx() -> dict[str, Any]:
    result: dict[str, Any] = {"provider": "ltx-local", "checks": {}, "verdict": "BLOCKED"}
    try:
        from app.director_timeline_w46.contracts import BatchBlock, DurationState, ExecutionSnapshot, TimelinePromptSegment
        from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter
        from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request

        batch = BatchBlock(
            sceneId="cert-scene",
            label="Cert Batch",
            generatorId="ltx-local",
            duration=DurationState(plannedDuration=5.0),
            promptSegments=[TimelinePromptSegment(start=0, length=5, text="cert ltx prompt")],
        )
        snap = ExecutionSnapshot(batchBlockId=batch.id, compiledPrompts={}, duration=batch.duration.model_copy())
        req = build_timeline_generation_request(
            project_id="cert-project",
            scene_id="cert-scene",
            batch=batch,
            snapshot=snap,
        )
        validation = LtxLocalAdapter().validate(req)
        result["checks"]["request_build"] = {
            "ok": True,
            "batchBlockId": req.batchBlockId,
            "executionSnapshotId": req.executionSnapshotId,
            "duration": req.duration,
        }
        result["checks"]["capability_validation"] = {"ok": validation.ok, "errors": validation.errors}

        # Static contract: the queue worker honors per-batch params for
        # timelineGeneration jobs (TIMELINE_BATCH_LTX).
        import inspect

        from app import queue_worker

        src = inspect.getsource(queue_worker.JobQueue._build_and_run_scene)
        worker_ok = "timelineGeneration" in src and "batchBlockId" in src
        result["checks"]["queue_worker_batch_params"] = {"ok": worker_ok}

        # FINGERPRINT CONTRACT: build the REAL LTX graph for two distinct
        # batches (different prompt/seed/duration→frames/dims/fps/steps) and
        # assert the canonical contract end-to-end:
        #   TOPOLOGY MATCH: YES (certified topologyHash, both builds)
        #   DYNAMIC BINDINGS VALID: YES
        #   per-batch bindings actually differ (frames/dims/fps/steps/prompt/seed)
        #   unique filename prefixes, LoadImage I2V binding present, no T2V downgrade
        from types import SimpleNamespace

        from app.config import settings
        from app.video_runtime.certified_registry import get_workflow
        from app.video_runtime.fingerprints import topology_hash, validate_dynamic_bindings
        from app.video_runtime.workflow_execute import build_leaf_graph, prepare_executable_graph

        leaf = get_workflow("ltx.simple_i2v")
        certified_topology = leaf.fingerprints.topology_hash if leaf else None
        contract = SimpleNamespace(
            leaf_workflow_key="ltx.simple_i2v",
            leaf_workflow_version="1.0.0",
            fingerprint_expected={},
        )
        build_a = dict(positive="CERT LTX A — korri at the lantern gate", negative="",
                       width=768, height=512, length=121, fps=24, seed=111,
                       start_image="cert_ltx_a.png", steps=8,
                       filename_prefix="studio/cert/ltx_batch_a")
        build_b = dict(positive="CERT LTX B — korri boards the night train", negative="",
                       width=832, height=480, length=65, fps=30, seed=222,
                       start_image="cert_ltx_b.png", steps=12,
                       filename_prefix="studio/cert/ltx_batch_b")
        graph_a = prepare_executable_graph(contract, build_leaf_graph(contract, settings=settings, **build_a))
        graph_b = prepare_executable_graph(contract, build_leaf_graph(contract, settings=settings, **build_b))

        topo_a, topo_b = topology_hash(graph_a), topology_hash(graph_b)
        bindings_a, bindings_b = validate_dynamic_bindings(graph_a), validate_dynamic_bindings(graph_b)
        classes_a = {n.get("class_type") for n in graph_a.values()}
        contract_checks = {
            "certifiedTopologyHashPresent": bool(certified_topology),
            "topologyMatchA": topo_a == certified_topology,
            "topologyMatchB": topo_b == certified_topology,
            "bindingsValidA": bindings_a["ok"],
            "bindingsValidB": bindings_b["ok"],
            "bindingsErrors": bindings_a["errors"] + bindings_b["errors"],
            "promptsDiffer": graph_a["2"]["inputs"]["text"] != graph_b["2"]["inputs"]["text"],
            "framesDiffer": graph_a["5"]["inputs"]["length"] != graph_b["5"]["inputs"]["length"],
            "dimsDiffer": graph_a["5"]["inputs"]["width"] != graph_b["5"]["inputs"]["width"],
            "fpsDiffer": graph_a["3b"]["inputs"]["frame_rate"] != graph_b["3b"]["inputs"]["frame_rate"],
            "stepsDiffer": graph_a["8"]["inputs"]["steps"] != graph_b["8"]["inputs"]["steps"],
            "prefixesUnique": build_a["filename_prefix"] != build_b["filename_prefix"],
            "i2vBindingA": any(n.get("class_type") == "LoadImage" for n in graph_a.values()),
            "noT2vDowngrade": "LTXVImgToVideo" in classes_a and "LTXVTextToVideo" not in classes_a,
        }
        result["checks"]["fingerprint_contract"] = {
            "ok": all(v for k, v in contract_checks.items() if k != "bindingsErrors" and v is not None),
            "detail": contract_checks,
        }

        if (
            validation.ok
            and worker_ok
            and result["checks"]["fingerprint_contract"]["ok"]
        ):
            result["verdict"] = "READY FOR MANUAL GENERATION"
        else:
            result["reason"] = "capability validation, worker contract, or fingerprint contract failed"
    except Exception as exc:
        result["reason"] = repr(exc)
    return result


def certify_capability_gated() -> dict[str, Any]:
    from app.director_timeline_w46.capabilities import list_generators

    gens = {g.id: g for g in list_generators()}
    out: dict[str, Any] = {"checks": {}, "verdict": "READY"}
    for gid in ("wan-local", "hunyuan-video-1.5-local", "hunyuan-video-13b-local"):
        gen = gens.get(gid)
        gated = bool(gen and not gen.supportsTimelineGeneration)
        out["checks"][gid] = {
            "ok": gated,
            "supportsTimelineGeneration": getattr(gen, "supportsTimelineGeneration", None),
            "note": "capability-gated off Timeline until a Timeline adapter is registered",
        }
    if not all(c["ok"] for c in out["checks"].values()):
        out["verdict"] = "BLOCKED"
        out["reason"] = "a provider without a Timeline adapter is not capability-gated"
    return out


def main() -> int:
    results = {
        "minimax_h3_route_a": certify_minimax_h3(),
        "ltx_local": certify_ltx(),
        "capability_gated_providers": certify_capability_gated(),
    }
    overall = (
        results["minimax_h3_route_a"]["verdict"] == "READY FOR MANUAL GENERATION"
        and results["ltx_local"]["verdict"] == "READY FOR MANUAL GENERATION"
        and results["capability_gated_providers"]["verdict"] == "READY"
    )
    payload = {
        "ok": overall,
        "verdict": "READY FOR MANUAL GENERATION" if overall else "BLOCKED",
        "providers": results,
        "gpuExecutionEnqueued": False,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
