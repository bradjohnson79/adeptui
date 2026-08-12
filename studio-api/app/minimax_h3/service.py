"""Service helpers for the MiniMax H3 planning surface."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from ..db import SessionLocal
from .contracts import AdeptMiniMaxH3Request, H3GenerationPlan, utc_now
from .planner import build_plan
from .preflight import evaluate_plan, evaluate_request
from .private_access import assert_private_owner_access, private_local_enabled
from .provenance import build_receipt
from .route_a_adapter import RouteARuntimeAdapter, import_output_to_project_library
from .store import load_plan, save_plan


# In-memory registry of running jobs keyed by (project_id, plan_id) so we can
# prevent duplicate submits for the same plan while one is already running.
_RUNNING_JOBS: dict[tuple[str, str], dict[str, Any]] = {}
_RUNNING_LOCK = threading.Lock()


def prepare_plan(request: AdeptMiniMaxH3Request) -> H3GenerationPlan:
    plan = build_plan(request)
    plan.preflight = evaluate_request(request)
    plan.fallbackOffer = plan.preflight.fallbackOffer
    plan.status = plan.preflight.status
    plan.provenance.append(build_receipt(plan, fallback_status="offered" if plan.fallbackOffer else "not_requested"))
    save_plan(plan)
    return plan


def get_plan(project_id: str, plan_id: str) -> H3GenerationPlan | None:
    return load_plan(project_id, plan_id)


def preflight(plan: H3GenerationPlan, *, approval_id: str | None = None) -> H3GenerationPlan:
    plan.preflight = evaluate_plan(plan, approval_id=approval_id)
    plan.fallbackOffer = plan.preflight.fallbackOffer
    plan.status = plan.preflight.status
    plan.updatedAt = utc_now()
    save_plan(plan)
    return plan


def request_fallback_ltx(project_id: str, plan_id: str, *, accepted_by: str = "creator") -> H3GenerationPlan:
    plan = _require_plan(project_id, plan_id)
    if plan.fallbackOffer is None:
        plan = preflight(plan)
    if plan.fallbackOffer is not None:
        plan.fallbackOffer.accepted = True
        plan.fallbackOffer.acceptedBy = accepted_by
        plan.fallbackOffer.acceptedAt = utc_now()
    plan.updatedAt = utc_now()
    plan.provenance.append(build_receipt(plan, fallback_status="accepted"))
    save_plan(plan)
    return plan


def cancel(project_id: str, plan_id: str, *, reason: str | None = None) -> H3GenerationPlan:
    plan = _require_plan(project_id, plan_id)
    plan.status = "cancelled"
    plan.updatedAt = utc_now()
    plan.provenance.append({"capturedAt": utc_now(), "action": "cancel", "reason": reason})
    # Interrupt the runtime job if one is running for this plan.
    with _RUNNING_LOCK:
        running = _RUNNING_JOBS.get((project_id, plan_id))
    if running:
        adapter: RouteARuntimeAdapter = running["adapter"]
        state = running["state"]
        try:
            adapter.cancel(state)
        except Exception:
            pass
    save_plan(plan)
    return plan


def retry(project_id: str, plan_id: str, *, approval_id: str | None = None) -> H3GenerationPlan:
    plan = _require_plan(project_id, plan_id)
    plan.status = "retry_requested"
    plan.updatedAt = utc_now()
    plan = preflight(plan, approval_id=approval_id)
    plan.provenance.append(build_receipt(plan, approval_id=approval_id))
    save_plan(plan)
    return plan


def readiness() -> dict[str, Any]:
    """Probe the isolated Route A runtime readiness for the owner-only path."""
    if not private_local_enabled():
        return {
            "ok": False,
            "ready": False,
            "privateLocalEnabled": False,
            "creatorStatus": "MiniMax H3 private local access is disabled.",
            "profile": None,
        }
    snap = assert_private_owner_access()
    adapter = RouteARuntimeAdapter()
    raw = adapter.readiness()
    # Sanitize: the raw health block exposes ComfyUI internals (version, package
    # list, argv with paths) that must never reach the creator-facing API. Keep
    # only a plain-language gpu name plus the creator-facing readiness fields.
    health = raw.get("health") or {}
    gpu_name = health.get("gpu") if isinstance(health, dict) else None
    result = {
        "ok": bool(raw.get("ok")),
        "ready": bool(raw.get("ready")),
        "creatorStatus": raw.get("creatorStatus"),
        "gpu": gpu_name,
        "missingFiles": raw.get("missingFiles") or [],
        "missingNodes": raw.get("missingNodes") or [],
        "profile": raw.get("profile"),
        "modelRootConfigured": bool(raw.get("modelRootConfigured")),
        "privateLocalEnabled": snap["privateLocalEnabled"],
        "ownerOnly": snap["ownerOnly"],
        "access": snap,
    }
    return result


def access_snapshot() -> dict[str, Any]:
    from .private_access import access_snapshot as _snap
    return _snap()


def get_job(project_id: str, job_id: str) -> dict[str, Any]:
    """Load a persisted job state from disk."""
    from .store import project_dir, read_json
    payload = read_json(project_dir(project_id) / "jobs" / f"{job_id}.json", None)
    if not isinstance(payload, dict):
        return {"ok": False, "status": "missing", "message": "MiniMax H3 job not found."}
    # Surface running state from the in-memory registry when present.
    with _RUNNING_LOCK:
        running = _RUNNING_JOBS.get((project_id, payload.get("planId", "")))
    if running and running["state"].job_id == job_id:
        st = running["state"]
        payload["status"] = st.status
        payload["stage"] = st.stage
        payload["cancelled"] = st.cancelled
    return {"ok": True, "job": payload}


def create_job_or_block(project_id: str, plan_id: str, *, approval_id: str | None = None) -> dict[str, object]:
    plan = _require_plan(project_id, plan_id)
    plan = preflight(plan, approval_id=approval_id)
    if plan.preflight is None:
        return {"ok": False, "status": "blocked", "message": "MiniMax H3 preflight could not be completed honestly."}
    if plan.preflight.status == "needs_approval":
        return {
            "ok": False,
            "status": "needs_approval",
            "planId": plan.planId,
            "message": "MiniMax H3 will not switch to a hosted lane until the creator gives explicit approval.",
            "preflight": plan.preflight.model_dump(mode="json"),
        }
    if plan.preflight.status == "blocked":
        return {
            "ok": False,
            "status": "blocked",
            "planId": plan.planId,
            "message": plan.preflight.blockers[0] if plan.preflight.blockers else "MiniMax H3 is blocked.",
            "preflight": plan.preflight.model_dump(mode="json"),
            "fallbackOffer": plan.fallbackOffer.model_dump(mode="json") if plan.fallbackOffer else None,
        }

    # Ready path — private owner-only Route A T2VA. Prevent duplicate submits
    # for the same plan while one is already running.
    key = (project_id, plan_id)
    with _RUNNING_LOCK:
        existing = _RUNNING_JOBS.get(key)
    if existing and existing["state"].status in {"queued", "running"} and not existing["state"].cancelled:
        return {
            "ok": False,
            "status": "duplicate",
            "planId": plan.planId,
            "jobId": existing["state"].job_id,
            "message": "A MiniMax H3 generation is already running for this plan.",
        }

    # Enforce private owner access gate before touching the runtime.
    try:
        assert_private_owner_access()
    except PermissionError as exc:
        return {
            "ok": False,
            "status": "blocked",
            "planId": plan.planId,
            "message": str(exc),
        }

    adapter = RouteARuntimeAdapter()
    if plan.request.mode == "one-frame":
        start_asset_id = next(
            (
                str(item.assetId).strip()
                for item in plan.request.referenceAssignments
                if item.role == "start" and str(item.assetId).strip()
            ),
            "",
        )
        if not start_asset_id:
            return {
                "ok": False,
                "status": "blocked",
                "planId": plan.planId,
                "message": "Add a starting frame before MiniMax H3 image-to-video.",
            }
        start_path = _resolve_project_asset_path(project_id, start_asset_id)
        if start_path is None:
            return {
                "ok": False,
                "status": "blocked",
                "planId": plan.planId,
                "message": "The starting frame could not be found in this project.",
            }
        state = adapter.submit_i2va(
            project_id=project_id,
            plan_id=plan_id,
            prompt=plan.request.prompt,
            start_image_path=start_path,
            seed=424242,
            start_image_asset_id=start_asset_id,
        )
    elif plan.request.mode == "text-to-video":
        state = adapter.submit_t2va(
            project_id=project_id,
            plan_id=plan_id,
            prompt=plan.request.prompt,
            seed=424242,
        )
    else:
        return {
            "ok": False,
            "status": "blocked",
            "planId": plan.planId,
            "message": (
                "MiniMax H3 Route A refused this mode. "
                "Only text-to-video and one-frame image-to-video are executable."
            ),
        }
    if state.status != "running":
        return {
            "ok": False,
            "status": "failed",
            "planId": plan.planId,
            "jobId": state.job_id,
            "errorCode": state.error_code,
            "message": state.error_message or "MiniMax H3 failed to start.",
        }

    plan.status = "ready"
    plan.updatedAt = utc_now()
    plan.provenance.append(
        {
            "capturedAt": utc_now(),
            "action": "submit",
            "jobId": state.job_id,
            "promptId": state.prompt_id,
            "lane": "private-local-route-a",
        }
    )
    save_plan(plan)

    with _RUNNING_LOCK:
        _RUNNING_JOBS[key] = {"adapter": adapter, "state": state}

    # Poll in a background thread so the request returns promptly with a
    # job id; the UI polls GET /jobs/{project_id}/{job_id} for progress.
    def _runner() -> None:
        try:
            final_state = adapter.poll(state, timeout_sec=900.0)
            _finalize_job(final_state, plan)
        except Exception as exc:  # pragma: no cover - defensive
            state.status = "failed"
            state.error_code = "H3_JOB_FAILED"
            state.error_message = repr(exc)
            state.ended_at = time.time()
            adapter._persist_job(state)
        finally:
            with _RUNNING_LOCK:
                _RUNNING_JOBS.pop(key, None)

    thread = threading.Thread(target=_runner, name=f"h3-job-{state.job_id[:8]}", daemon=True)
    thread.start()

    return {
        "ok": True,
        "status": "running",
        "planId": plan.planId,
        "jobId": state.job_id,
        "stage": state.stage,
        "message": "MiniMax H3 generation started on the Experimental Private Profile.",
        "provenance": {
            "modelId": "minimax-h3-route-a-local",
            "displayName": "MiniMax H3",
            "provider": "MiniMax",
            "engine": "MiniMax H3",
            "deployment": "private-local",
            "access": "owner-only",
            "runtime": "route-a",
            "apiUsed": False,
            "ltxUsed": False,
            "profile": "Experimental Private Profile",
            "retake": bool(getattr(plan.request, "retake", False)),
            "sourceTakeId": getattr(plan.request, "sourceTakeId", None),
            "deltaInstruction": getattr(plan.request, "deltaInstruction", None),
            "originalPrompt": getattr(plan.request, "originalPrompt", None) or plan.request.prompt,
            "projectId": plan.projectId,
            "shotId": (plan.request.timelineContext.shotId if plan.request.timelineContext else None),
            "sceneId": (plan.request.timelineContext.sceneId if plan.request.timelineContext else None),
        },
    }


def _finalize_job(state: Any, plan: H3GenerationPlan) -> None:
    """Import the validated output into the project library and attempt a
    Timeline take placement when a sceneId is present."""
    if state.status != "completed" or not state.output_path:
        return
    try:
        db = SessionLocal()
        try:
            receipt = import_output_to_project_library(
                project_id=state.project_id,
                source_mp4=Path(state.output_path),
                tag="minimax-h3",
                db=db,
            )
            state.media = {**(state.media or {}), "libraryImport": receipt}
            state.provenance = {
                **(state.provenance or {}),
                "libraryAssetId": receipt.get("assetId"),
                "apiUsed": False,
                "ltxUsed": False,
            }
            adapter = RouteARuntimeAdapter()
            adapter._persist_job(state)
            # Attempt Timeline take placement when sceneId present.
            scene_id = plan.request.timelineContext.sceneId if plan.request.timelineContext else None
            timeline_receipt = None
            if scene_id:
                timeline_receipt = _place_on_timeline(db, state.project_id, scene_id, receipt)
            if timeline_receipt is None:
                timeline_receipt = {
                    "placed": False,
                    "instructions": (
                        "Library asset registered. Open the project Library and use Place on "
                        "Timeline to drop the MiniMax H3 take onto a scene."
                    ),
                }
            state.provenance = {
                **(state.provenance or {}),
                "timelineImport": timeline_receipt,
            }
            adapter._persist_job(state)
        finally:
            db.close()
    except Exception:
        # Library/Timeline placement failures must not erase the generation.
        return


def _place_on_timeline(db: Any, project_id: str, scene_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    """Place the imported video asset onto a scene as its output take.

    TIMELINE_BATCH_ISOLATION: when the receipt carries a batchBlockId
    (timelineContext.shotId), the W46 batch completion path owns clip
    placement via apply_shared_completion. Do NOT write scene.output_path
    here for Timeline batches — that would race batch-level binding and
    collapse multi-batch output to a single scene-level file.
    """
    from ..db import Asset, Scene
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        return {"placed": False, "instructions": "Scene not found; asset remains in the Library."}
    asset_id = receipt.get("assetId")
    asset = db.get(Asset, asset_id) if asset_id else None
    if not asset:
        return {"placed": False, "instructions": "Asset not found; placement skipped."}
    batch_block_id = receipt.get("shotId")
    if batch_block_id:
        # W46 owns placement for this batch; leave scene.output_path untouched.
        return {
            "placed": False,
            "deferredToBatch": True,
            "batchBlockId": batch_block_id,
            "sceneId": scene_id,
            "assetId": asset_id,
            "instructions": "Batch output registered; W46 batch completion will place it.",
        }
    scene.output_path = asset.path
    db.commit()
    return {
        "placed": True,
        "sceneId": scene_id,
        "assetId": asset_id,
        "outputPath": asset.path,
    }


def _resolve_project_asset_path(project_id: str, asset_id: str) -> Path | None:
    """Resolve a project-owned asset file path. Fail closed on cross-project ids."""
    from ..db import Asset

    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if not asset or asset.project_id != project_id or not asset.path:
            return None
        path = Path(asset.path)
        return path if path.is_file() else None
    finally:
        db.close()


def _require_plan(project_id: str, plan_id: str) -> H3GenerationPlan:
    plan = load_plan(project_id, plan_id)
    if plan is None:
        raise ValueError("MiniMax H3 plan not found.")
    return plan
