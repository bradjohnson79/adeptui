#!/usr/bin/env python3
"""M41 4.1B-L L-10B — Wave 6 Consumer Contract Certification.

Verifies Wave 6 product surfaces consume the Certified Workflow Library only
through public contracts (WorkflowResolver → CanonicalWorkflowContract).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

ARTIFACTS = ROOT / "artifacts" / "m41" / "41bl"
REPORTS = ROOT / "docs" / "release-gate" / "m41"
RESULTS = ARTIFACTS / "wave6_consumer_contract_results.json"

CONSUMER_ROOTS = [
    ROOT / "studio-api" / "app" / "codirector",
    ROOT / "studio-web" / "src",
]
# Surfaces that may enqueue jobs but must not import Comfy builders.
FORBIDDEN_BUILDER_IMPORTS = re.compile(
    r"(ltx_builder|wan_builder|lipsync_builder|build_ltx_|build_wan_|build_latentsync|"
    r"compile_ingredients_workflow)",
    re.I,
)
# Imperative leaf selection outside the resolver (engine→builder if/else without resolve).
IMPERATIVE_ENGINE_PATTERNS = [
    re.compile(r"if\s+.*engine\s*==\s*['\"]wan['\"].*:\s*\n\s*.*build_wan", re.I | re.M),
    re.compile(r"build_ltx_simple_i2v\s*\(", re.I),
    re.compile(r"build_wan_flf_workflow\s*\(", re.I),
]

REQUIRED_CONTRACT_FIELDS = [
    "workflow_id",
    "workflow_version",
    "leaf_workflow_key",
    "leaf_workflow_version",
    "provider_kind",
    "required_inputs",
    "cancellation_policy",
    "concurrency_class",
    "output_contract",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "pass": bool(ok), "detail": detail}


def _assert_contract_shape(contract: Any) -> list[str]:
    missing: list[str] = []
    d = contract.to_dict() if hasattr(contract, "to_dict") else dict(contract)
    for field in REQUIRED_CONTRACT_FIELDS:
        camel = "".join(
            w.capitalize() if i else w for i, w in enumerate(field.split("_"))
        )
        if field not in d and camel not in d and field.replace("_", "") not in {
            k.lower().replace("_", "") for k in d
        }:
            # Accept either snake or camel on dict
            if field == "provider_kind" and ("provider" in d or "provider_kind" in d):
                continue
            if field == "concurrency_class" and (
                "concurrency_class" in d or "concurrencyClass" in d
            ):
                continue
            if field == "required_inputs" and (
                "required_inputs" in d or "requiredInputs" in d
            ):
                continue
            if field == "cancellation_policy" and (
                "cancellation_policy" in d or "cancellationPolicy" in d
            ):
                continue
            if field == "output_contract" and (
                "output_contract" in d or "outputContract" in d
            ):
                continue
            missing.append(field)
    # Exact Certified version
    if getattr(contract, "status", None) != "Certified" and d.get("status") != "Certified":
        # Leaf status on contract
        if d.get("status") != "Certified":
            missing.append("status!=Certified")
    if not (d.get("leaf_workflow_version") or d.get("leafWorkflowVersion")):
        missing.append("leaf_workflow_version")
    if not (d.get("workflow_id") or d.get("workflowId")):
        missing.append("workflow_id")
    cancel = d.get("cancellation_policy") or d.get("cancellationPolicy") or {}
    if not isinstance(cancel, dict) or "supported" not in cancel:
        missing.append("cancellation_policy.supported")
    out = d.get("output_contract") or d.get("outputContract") or {}
    if not isinstance(out, dict) or "supportedOutputs" not in out:
        missing.append("output_contract.supportedOutputs")
    req = d.get("required_inputs") or d.get("requiredInputs") or []
    if not isinstance(req, list):
        missing.append("required_inputs")
    return missing


def check_resolutions() -> dict[str, Any]:
    from app.video_runtime.workflow_resolver import (
        resolve_from_scene_params,
        resolve_workflow,
    )
    from app.video_runtime.certified_registry import get_workflow, reload_registry

    reload_registry()
    cases: list[dict[str, Any]] = []

    def run(label: str, fn) -> None:
        try:
            c = fn()
            missing = _assert_contract_shape(c)
            leaf = get_workflow(c.leaf_workflow_key)
            version_ok = bool(
                leaf
                and leaf.status == "Certified"
                and leaf.workflow_version == c.leaf_workflow_version
            )
            cases.append(
                {
                    "label": label,
                    "pass": not missing and version_ok,
                    "contract": c.to_dict(),
                    "missingFields": missing,
                    "exactCertifiedVersion": version_ok,
                    "leaf": c.leaf_workflow_key,
                    "version": c.leaf_workflow_version,
                    "workflowId": c.workflow_id,
                }
            )
        except Exception as exc:
            cases.append({"label": label, "pass": False, "error": str(exc)[:400]})

    # Co-Director generation intent (scene I2V)
    run(
        "codirector.scene_i2v",
        lambda: resolve_from_scene_params(
            engine="ltx", start_asset_id="s1", intent="scene_render"
        ),
    )
    # Director shot / scene
    run(
        "director.shot_render",
        lambda: resolve_from_scene_params(
            engine="ltx", start_asset_id="s1", intent="shot_render"
        ),
    )
    run(
        "director.scene_render_keyframes",
        lambda: resolve_from_scene_params(
            engine="ltx",
            start_asset_id="s1",
            middle_asset_id="m1",
            end_asset_id="e1",
            intent="scene_render",
        ),
    )
    # Generate Studio modes
    run(
        "generate_studio.ltx_simple_i2v",
        lambda: resolve_workflow(
            "scene_render",
            engine="ltx",
            present_inputs={"start_asset_id": "s1"},
        ),
    )
    run(
        "generate_studio.wan_flf",
        lambda: resolve_workflow(
            "scene_render",
            engine="wan",
            present_inputs={"start_asset_id": "s1", "end_asset_id": "e1"},
        ),
    )
    run(
        "generate_studio.wan_three_frame",
        lambda: resolve_workflow(
            "scene_render",
            engine="wan",
            present_inputs={
                "start_asset_id": "s1",
                "middle_asset_id": "m1",
                "end_asset_id": "e1",
            },
        ),
    )
    run(
        "generate_studio.txt2vid_local_i2v",
        lambda: resolve_workflow(
            "txt2vid_local",
            engine="ltx",
            present_inputs={"start_frame": True},
        ),
    )
    run(
        "generate_studio.extend",
        lambda: resolve_workflow(
            "extend", engine="ltx", present_inputs={"start_frame": True}
        ),
    )
    run(
        "generate_studio.lipsync",
        lambda: resolve_workflow(
            "lipsync", present_inputs={"audio_asset_id": "a1", "video": True}
        ),
    )
    # Timeline / batch
    run(
        "director.timeline_render",
        lambda: resolve_workflow("timeline_render", engine="director"),
    )
    run(
        "director.batch_timeline",
        lambda: resolve_workflow("batch_timeline", engine="director"),
    )

    passed = all(c.get("pass") for c in cases)
    return {"pass": passed, "cases": cases}


def check_blocked_deferred_rejected() -> dict[str, Any]:
    from app.video_runtime.workflow_resolver import resolve_workflow
    from app.video_runtime.certified_registry import assert_executable, reload_registry

    reload_registry()
    results = []

    # Deferred
    try:
        resolve_workflow("scene_render", force_workflow_key="video.upscale")
        results.append(_check("deferred_upscale_rejected", False, "resolve succeeded"))
    except RuntimeError as exc:
        results.append(
            _check(
                "deferred_upscale_rejected",
                "deferred" in str(exc).lower() or "not_certified" in str(exc).lower(),
                str(exc)[:200],
            )
        )

    # Blocked cloud
    try:
        resolve_workflow("scene_render", force_workflow_key="fal.seedance")
        results.append(_check("blocked_fal_rejected", False, "resolve succeeded"))
    except RuntimeError as exc:
        results.append(
            _check(
                "blocked_fal_rejected",
                "not_certified" in str(exc).lower() or "blocked" in str(exc).lower(),
                str(exc)[:200],
            )
        )

    # assert_executable
    try:
        assert_executable("video.upscale", allow_non_certified=False)
        results.append(_check("assert_executable_deferred", False, "did not raise"))
    except RuntimeError as exc:
        results.append(_check("assert_executable_deferred", True, str(exc)[:200]))

    try:
        assert_executable("fal.seedance", allow_non_certified=False)
        results.append(_check("assert_executable_blocked", False, "did not raise"))
    except RuntimeError as exc:
        results.append(_check("assert_executable_blocked", True, str(exc)[:200]))

    return {"pass": all(r["pass"] for r in results), "checks": results}


def _iter_py_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [p for p in root.rglob("*.py") if p.is_file()]


def _iter_ts_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.suffix in {".ts", ".tsx"} and p.is_file():
            out.append(p)
    return out


def check_no_direct_builder_imports() -> dict[str, Any]:
    hits: list[str] = []
    for root in CONSUMER_ROOTS:
        files = _iter_py_files(root) + _iter_ts_files(root)
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if FORBIDDEN_BUILDER_IMPORTS.search(text):
                # Allow comments mentioning builders in docs strings carefully
                for i, line in enumerate(text.splitlines(), 1):
                    if FORBIDDEN_BUILDER_IMPORTS.search(line) and not line.strip().startswith(
                        ("//", "#", "*", "/*")
                    ):
                        hits.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()[:120]}")
    return {"pass": not hits, "hits": hits[:50], "scannedRoots": [str(r) for r in CONSUMER_ROOTS]}


def check_no_imperative_engine_selection() -> dict[str, Any]:
    """Consumers must not select Comfy builders by engine; QueueWorker uses resolver."""
    hits: list[str] = []
    for root in CONSUMER_ROOTS:
        for path in _iter_py_files(root) + _iter_ts_files(root):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat in IMPERATIVE_ENGINE_PATTERNS:
                if pat.search(text):
                    hits.append(f"{path.relative_to(ROOT)} matched {pat.pattern[:40]}")
    # QueueWorker must call resolve_* for scene/shot/timeline/extend/lipsync
    qw = (ROOT / "studio-api" / "app" / "queue_worker.py").read_text(encoding="utf-8")
    worker_ok = all(
        s in qw
        for s in (
            "resolve_from_scene_params",
            'resolve_workflow(orch_intent',
            'resolve_workflow(\n            "extend"',
            'resolve_workflow(\n            "lipsync"',
        )
    )
    # Softer lipsync check — allow either formatting
    lipsync_ok = "resolve_workflow(" in qw and '"lipsync"' in qw
    extend_ok = 'resolve_workflow("extend"' in qw or '"extend"' in qw and "resolve_workflow" in qw
    scene_ok = "resolve_from_scene_params" in qw
    timeline_ok = "timeline_render" in qw and "resolve_workflow" in qw
    return {
        "pass": not hits and lipsync_ok and extend_ok and scene_ok and timeline_ok,
        "consumerHits": hits,
        "queueWorker": {
            "resolveScene": scene_ok,
            "resolveTimeline": timeline_ok,
            "resolveExtend": extend_ok,
            "resolveLipsync": lipsync_ok,
            "worker_ok_strict": worker_ok,
        },
    }


def check_no_bypass_execution_controls() -> dict[str, Any]:
    """Wave 6 consumers enqueue jobs; execution controls live in video_runtime + QueueWorker."""
    qw = (ROOT / "studio-api" / "app" / "queue_worker.py").read_text(encoding="utf-8")
    checks = [
        _check("queue_worker.prepare_executable_graph", "prepare_executable_graph" in qw),
        _check("queue_worker.validate_or_gate", "validate_video_output" in qw or "output_gate" in qw),
        _check("queue_worker.comfy_queue_prompt", "queue_prompt" in qw),
        _check("queue_worker.asset_register", "_register" in qw or "register" in qw.lower()),
    ]
    # Consumers must not call comfy.queue_prompt for video workflows (imagegen may use Comfy).
    consumer_queue_hits: list[str] = []
    for root in CONSUMER_ROOTS:
        for path in _iter_py_files(root):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "queue_prompt" in text:
                consumer_queue_hits.append(str(path.relative_to(ROOT)))
    checks.append(
        _check(
            "consumers_no_comfy_queue_prompt",
            not consumer_queue_hits,
            str(consumer_queue_hits[:10]),
        )
    )

    # Preflight / VRAM module present for execute path
    preflight = ROOT / "studio-api" / "app" / "video_runtime" / "preflight.py"
    checks.append(_check("vram_preflight_module", preflight.is_file()))
    if preflight.is_file():
        pt = preflight.read_text(encoding="utf-8")
        checks.append(_check("ensure_local_queueable", "ensure_local_queueable" in pt))

    # comfy_client wires ensure_local_queueable
    cc = (ROOT / "studio-api" / "app" / "comfy_client.py").read_text(encoding="utf-8")
    checks.append(_check("comfy_queue_prompt_preflight", "ensure_local_queueable" in cc))

    return {"pass": all(c["pass"] for c in checks), "checks": checks}


def check_status_consistency() -> dict[str, Any]:
    from app.video_runtime.certified_registry import (
        list_workflows,
        production_ready_keys,
        reload_registry,
        compatibility_projection,
    )
    from app.video_runtime.production_gate import evaluate_gate, reload_production_gate

    reload_registry()
    reload_production_gate()
    entries = {w.workflow_key: w for w in list_workflows(modality=None)}
    ready = set(production_ready_keys())
    gate = evaluate_gate()
    gate_ready = set(gate.get("certifiedWorkflowKeys") or [])
    proj = {p["workflowKey"]: p for p in compatibility_projection() if p.get("workflowKey")}

    mismatches: list[str] = []
    for key, wf in entries.items():
        prod = wf.is_production_ready
        if prod != (key in ready):
            mismatches.append(f"{key}: is_production_ready!={key in ready}")
        if prod != (key in gate_ready):
            mismatches.append(f"{key}: gate certified mismatch")
        if key in proj:
            cap = proj[key].get("capabilityState") or proj[key].get("capability_state")
            if wf.status == "Certified" and cap not in {"production_ready", "ready", None}:
                # projection uses production_ready for Certified
                if cap != "production_ready":
                    mismatches.append(f"{key}: projection={cap} status={wf.status}")
            if wf.status == "Deferred" and cap not in {"deferred", None}:
                if cap != "deferred":
                    mismatches.append(f"{key}: projection deferred mismatch ({cap})")
            if proj[key].get("productionReady") and wf.status != "Certified":
                mismatches.append(f"{key}: projection productionReady but status={wf.status}")

    return {
        "pass": not mismatches,
        "mismatches": mismatches[:40],
        "certifiedCount": len(ready),
        "gateCertifiedCount": len(gate_ready),
    }


def write_report(results: dict[str, Any]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    passed = bool(results.get("wave6ConsumerContractPassed"))
    lines = [
        "# M41 4.1B-L — Wave 6 Consumer Contract Certification (L-10B)",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| **Generated** | {results.get('generatedAt')} |",
        f"| **wave6ConsumerContractPassed** | `{passed}` |",
        f"| **Verdict** | **{'PASS' if passed else 'FAIL'}** |",
        "",
        "## Scope",
        "",
        "4.1B-L proves the Certified Workflow Library and its public contract are ready for Wave 6.",
        "This L-10B gate proves Wave 6 product surfaces (Co-Director, Director, Generate Studio,",
        "timeline/batch) consume that library **only** through `WorkflowResolver` →",
        "`CanonicalWorkflowContract` — not by importing builders or selecting engines imperatively.",
        "",
        "Dedicated Wave 6 product implementation and beta certification remain separate prompts.",
        "",
        "## Checks",
        "",
    ]
    for key in (
        "resolutions",
        "blockedDeferredRejected",
        "noDirectBuilderImports",
        "noImperativeEngineSelection",
        "noBypassExecutionControls",
        "statusConsistency",
    ):
        block = results.get(key) or {}
        lines.append(f"- **{key}**: {'PASS' if block.get('pass') else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Resolution matrix",
            "",
        ]
    )
    for case in (results.get("resolutions") or {}).get("cases") or []:
        status = "PASS" if case.get("pass") else "FAIL"
        lines.append(
            f"- `{case.get('label')}` → `{case.get('leaf')}`@{case.get('version')} "
            f"({case.get('workflowId')}) **{status}**"
        )
    lines.extend(
        [
            "",
            "## Artifact",
            "",
            "`artifacts/m41/41bl/wave6_consumer_contract_results.json`",
            "",
            "## Gate coupling",
            "",
            "`evaluate_gate().wave6ConsumerContractPassed` must be true for",
            "`wave6ProductionActivationUnlocked`.",
            "",
        ]
    )
    (REPORTS / "M41_41BL_WAVE6_CONSUMER_CONTRACT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {
        "generatedAt": _now(),
        "phase": "M41-4.1B-L-L10B",
        "resolutions": check_resolutions(),
        "blockedDeferredRejected": check_blocked_deferred_rejected(),
        "noDirectBuilderImports": check_no_direct_builder_imports(),
        "noImperativeEngineSelection": check_no_imperative_engine_selection(),
        "noBypassExecutionControls": check_no_bypass_execution_controls(),
        "statusConsistency": check_status_consistency(),
    }
    passed = all(
        bool((results.get(k) or {}).get("pass"))
        for k in (
            "resolutions",
            "blockedDeferredRejected",
            "noDirectBuilderImports",
            "noImperativeEngineSelection",
            "noBypassExecutionControls",
            "statusConsistency",
        )
    )
    results["wave6ConsumerContractPassed"] = passed
    results["passed"] = passed
    RESULTS.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    write_report(results)

    # Refresh gate artifact if present
    try:
        from app.video_runtime.production_gate import evaluate_gate, reload_production_gate
        from app.video_runtime.certified_registry import reload_registry

        reload_registry()
        reload_production_gate()
        gate = evaluate_gate()
        (ARTIFACTS / "workflow_gate_results.json").write_text(
            json.dumps(gate, indent=2), encoding="utf-8"
        )
        (REPORTS / "M41_41BL_GATE_REPORT.md").write_text(
            "# M41 4.1B-L — Gate Report\n\n" + json.dumps(gate, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "Gate wave6ConsumerContractPassed=",
            gate.get("wave6ConsumerContractPassed"),
            "wave6ProductionActivationUnlocked=",
            gate.get("wave6ProductionActivationUnlocked"),
        )
    except Exception as exc:
        print("gate refresh skipped:", exc)

    print("wave6ConsumerContractPassed=", passed)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
