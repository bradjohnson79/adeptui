"""Developer-only workflow export for a Timeline batch (Phase 4).

Builds the REAL request + ComfyUI graph for a batch through the same mapping
the queue worker uses (prompt/duration→frames snap/clamp, plan dims/fps,
seed fallback, contract resolution, build_leaf_graph, prepare_executable_graph)
but NEVER queues or executes anything. Writes inspection artifacts under
data/runtime/exports/ so a developer can load the exact API graph into
ComfyUI and audit the fingerprint contract:

  timeline_<scene>_<batch>_<provider>_workflow.json     (graph in loadable form)
  timeline_<scene>_<batch>_<provider>_api.json          (exact API graph)
  timeline_<scene>_<batch>_<provider>_bindings.json     (dynamic bindings report)
  timeline_<scene>_<batch>_<provider>_fingerprints.json (topology/legacy hashes + match)

Env-gated by ADEPT_TIMELINE_WORKFLOW_EXPORT=1 (developer only).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset, Project
from ..video_runtime.fingerprints import (
    graph_hash,
    topology_hash,
    validate_dynamic_bindings,
)
from ..video_runtime.workflow_execute import build_leaf_graph, prepare_executable_graph
from ..video_runtime.workflow_resolver import resolve_from_scene_params
from . import store
from .contracts import SceneTimelineMaster
from .generation.request_builder import build_timeline_generation_request
from .orchestrator import create_execution_snapshot

_EXPORT_ENV = "ADEPT_TIMELINE_WORKFLOW_EXPORT"


def export_enabled() -> bool:
    return os.environ.get(_EXPORT_ENV, "").strip() == "1"


class WorkflowExportError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _intended_comfy_image_name(db: Session, project_id: str, asset_id: str | None) -> str | None:
    """Filename the queue worker would upload to ComfyUI for this asset.

    Export mode never uploads — the bindings report marks the reference as
    intended-only.
    """
    if not asset_id:
        return None
    asset = db.get(Asset, asset_id)
    if asset is None or asset.project_id != project_id:
        return None
    name = getattr(asset, "filename", None) or getattr(asset, "name", None)
    if not name:
        path = getattr(asset, "path", None) or getattr(asset, "file_path", None)
        name = Path(path).name if path else None
    return name


def export_batch_workflow(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
) -> dict[str, Any]:
    project = db.get(Project, project_id)
    scene = store.get_scene(db, project_id, scene_id)
    if project is None or scene is None:
        raise WorkflowExportError("NOT_FOUND", "Project or scene not found.")
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        raise WorkflowExportError("MASTER_UNAVAILABLE", str(payload.get("error") or "master unavailable"))
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if batch is None:
        raise WorkflowExportError("BATCH_NOT_FOUND", f"Batch {batch_id} not found.")

    # Prefer the staged immutable snapshot (sequential chain); otherwise build
    # an ephemeral in-memory one — export NEVER mutates master state.
    snapshot = master.executionSnapshots.get(batch.pendingSnapshotId or "")
    snapshot_origin = "staged"
    if snapshot is None:
        snapshot = create_execution_snapshot(batch)
        snapshot_origin = "ephemeral"

    request = build_timeline_generation_request(
        project_id=project_id, scene_id=scene_id, batch=batch, snapshot=snapshot
    )
    if request.generatorId != "ltx-local":
        raise WorkflowExportError(
            "EXPORT_UNSUPPORTED_PROVIDER",
            f"Workflow export currently supports the local Comfy LTX path only "
            f"(batch generator={request.generatorId!r}). MiniMax H3 uses its own "
            "adapter and has no ComfyUI graph.",
        )

    # --- Mirror queue_worker._build_and_run_scene param mapping exactly ---
    from ..aspect_fps import resolve_scene_dims, resolve_scene_fps
    from ..engine_recommend import resolve_engine_id
    from ..vram_profiles import clamp_frames, resolve_render_plan

    negative = request.negativePrompt or project.negative_prompt or ""
    seed = scene.seed if scene.seed >= 0 else project.seed
    plan = resolve_render_plan(project)
    sw, sh = resolve_scene_dims(project, scene)
    sfps = resolve_scene_fps(project, scene)
    if plan.vram_gb < 32:
        width, height, plan_fps = min(sw, plan.width), min(sh, plan.height), min(sfps, plan.fps)
    else:
        width, height, plan_fps = sw, sh, sfps
    steps = plan.steps
    resolved_engine = resolve_engine_id(scene.engine, project, scene)

    frames = max(9, int(round(float(request.duration) * plan_fps)))
    length = max(9, ((frames - 1) // 8) * 8 + 1)
    length, frame_clamped = clamp_frames(length, plan)

    contract = resolve_from_scene_params(
        engine=resolved_engine,
        start_asset_id=request.startImageAssetId or scene.start_asset_id,
        middle_asset_id=scene.middle_asset_id,
        end_asset_id=request.endImageAssetId or scene.end_asset_id,
        audio_asset_id=scene.audio_asset_id,
        wants_ingredients=False,
        paid_fal_approved=False,
        intent="scene_render",
    )

    start_name = _intended_comfy_image_name(db, project_id, request.startImageAssetId)
    if contract.leaf_workflow_key in {"ltx.simple_i2v", "ltx.scene"} and not start_name:
        raise WorkflowExportError(
            "START_FRAME_REQUIRED",
            "Local LTX requires a start frame (I2V only). Attach a start image to the batch.",
        )
    end_name = _intended_comfy_image_name(db, project_id, request.endImageAssetId)

    filename_prefix = f"studio/{project.id[:8]}_{scene.index}/batch_{batch.id[:8]}"
    graph = build_leaf_graph(
        contract,
        settings=settings,
        positive=request.prompt,
        negative=negative,
        width=width,
        height=height,
        length=length,
        fps=plan_fps,
        seed=seed,
        start_image=start_name,
        end_image=end_name,
        steps=steps,
        filename_prefix=filename_prefix,
    )
    # Runs the canonical fingerprint contract: topology gate (Certified entries)
    # + dynamic bindings validation. Raises on true topology drift.
    prepared = prepare_executable_graph(contract, graph, enforce_certified_fingerprint=True)

    from ..video_runtime.certified_registry import get_workflow

    leaf = get_workflow(contract.leaf_workflow_key)
    certified_topology = leaf.fingerprints.topology_hash if leaf else None
    certified_legacy = leaf.fingerprints.graph_hash if leaf else None
    actual_topology = topology_hash(prepared)
    actual_legacy = graph_hash(prepared)
    bindings = validate_dynamic_bindings(prepared)
    bindings_report = dict(bindings)
    bindings_report["loadImageReference"] = {
        "value": start_name,
        "uploadedInExportMode": False,
    }

    exports_dir = Path(settings.data_dir) / "runtime" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    stem = f"timeline_{scene_id}_{batch.id[:8]}_{request.generatorId}"

    workflow_path = exports_dir / f"{stem}_workflow.json"
    api_path = exports_dir / f"{stem}_api.json"
    bindings_path = exports_dir / f"{stem}_bindings.json"
    fingerprints_path = exports_dir / f"{stem}_fingerprints.json"

    # Builders emit API-format graphs; ComfyUI can import this directly via
    # "Load (API Format)". A separate UI-format workflow is not produced.
    workflow_path.write_text(json.dumps(prepared, indent=2), encoding="utf-8")
    api_path.write_text(json.dumps(prepared, indent=2), encoding="utf-8")
    bindings_path.write_text(json.dumps(bindings_report, indent=2), encoding="utf-8")
    fingerprints_report = {
        "workflowKey": contract.leaf_workflow_key,
        "workflowVersion": contract.leaf_workflow_version,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "topologyHash": {"certified": certified_topology, "actual": actual_topology},
        "legacyGraphHash": {"certified": certified_legacy, "actual": actual_legacy},
        "topologyMatch": (certified_topology is None) or (actual_topology == certified_topology),
        "bindingsValid": bindings["ok"],
        "bindingsErrors": bindings["errors"],
        "paramMapping": {
            "prompt": request.prompt,
            "negative": negative,
            "seed": seed,
            "width": width,
            "height": height,
            "fps": plan_fps,
            "requestedDuration": request.duration,
            "framesSnapped": length,
            "frameClamped": frame_clamped,
            "steps": steps,
            "filenamePrefix": filename_prefix,
            "snapshotOrigin": snapshot_origin,
            "executionSnapshotId": snapshot.id,
        },
    }
    fingerprints_path.write_text(json.dumps(fingerprints_report, indent=2), encoding="utf-8")

    return {
        "batchBlockId": batch.id,
        "generatorId": request.generatorId,
        "workflowKey": contract.leaf_workflow_key,
        "topologyMatch": fingerprints_report["topologyMatch"],
        "bindingsValid": bindings["ok"],
        "artifacts": {
            "workflow": str(workflow_path),
            "api": str(api_path),
            "bindings": str(bindings_path),
            "fingerprints": str(fingerprints_path),
        },
    }
