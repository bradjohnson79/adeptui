"""Comfy Manager reads the existing Adept job owner and the live Comfy bridge.

It does not submit generations, own a second queue, or restart ComfyUI.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

SOURCE_BY_KIND = {
    "imagegen": "Image Generator",
    "imagegen_edit": "Image Generator",
    "multi_angle": "Image Generator",
    "render_shot": "Timeline",
    "render_scene": "Timeline",
    "batch_timeline": "Timeline",
    "txt2vid": "Timeline",
    "video_extend": "Timeline",
    "media_retake": "Timeline",
    "character_sheet": "Character Creator",
    "lipsync": "Voice",
    "dual_lipsync": "Voice",
    "performance_retake": "Voice",
}

ACTIVE_STATUSES = {"queued", "running", "processing", "cancelling", "claimed"}
PROBLEM_STATUSES = {"failed", "cancel_failed_runtime_active", "interrupted"}
VIDEO_KINDS = {"render_shot", "render_scene", "batch_timeline", "txt2vid", "video_extend", "magi_upscale", "magi_final_render"}
# Matches ComfyClient.PROMPT_GONE_GRACE_SEC. A live prompt is never confirmed stalled.
RECONCILE_GRACE_SEC = 45.0
USER_STATUS = {
    "done": "Completed",
    "running": "Running",
    "processing": "Running",
    "queued": "Queued",
    "claimed": "Queued",
    "failed": "Failed",
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
    "interrupted": "Interrupted",
    "cancelling": "Cancelling",
}


def source_label(kind: str, params: dict[str, Any] | None = None) -> str:
    body = params or {}
    purpose = str(body.get("purpose") or "")
    if purpose == "environment_reference_sheet":
        return "Environment Creator"
    if "storyboard" in purpose or str(body.get("origin") or "") == "storyboard":
        return "Storyboard"
    text = str(kind or "")
    if text.startswith("magi_"):
        return "MAGI"
    return SOURCE_BY_KIND.get(text, text.replace("_", " ").title() or "Adept")


def workspace_for(source: str) -> str | None:
    return {
        "Image Generator": "imagegen",
        "Storyboard": "storyboard",
        "Timeline": "timeline",
        "MAGI": "magi",
        "Character Creator": "characters",
        "Environment Creator": "environment",
        "Voice": "voice",
    }.get(source)


def _is_result_missing(low: str) -> bool:
    phrases = (
        "expected result missing",
        "output file missing",
        "no output image",
        "no output video",
        "expected artifact not found",
        "output artifact not found",
        "could not locate the expected output",
    )
    return any(phrase in low for phrase in phrases)


def status_label(status: str) -> str:
    text = str(status or "")
    return USER_STATUS.get(text.lower(), text)


def normalize_error(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    low = text.lower()
    if "out of memory" in low or "cuda out of memory" in low or "vram" in low:
        summary, cause, action = (
            "GPU memory exhausted during generation",
            "The workflow asked for more VRAM than is free.",
            "Wait for the current job to finish, then retry. Do not restart Comfy from here.",
        )
        code = "VRAM_OOM"
    elif "node" in low and ("not found" in low or "missing" in low or "unknown" in low):
        summary, cause, action = (
            "A required Comfy node is unavailable",
            "The workflow names a node this ComfyUI install does not have.",
            "Open Setup and review the component. Do not guess a replacement node.",
        )
        code = "NODE_MISSING"
    elif "latent" in low or "patch" in low or ("dimension" in low and ("invalid" in low or "incompatible" in low)):
        summary, cause, action = (
            "Output dimensions are incompatible with this workflow",
            "The requested size does not match what the workflow can run.",
            "Retry only after the original request is still valid. Do not change the size silently.",
        )
        code = "DIMENSIONS"
    elif "model" in low and "missing" in low:
        summary, cause, action = (
            "A required model is missing",
            "ComfyUI could not load the checkpoint, LoRA, or VAE named by the job.",
            "Retry stays unavailable until that model is present.",
        )
        code = "MODEL_MISSING"
    elif _is_result_missing(low):
        summary, cause, action = (
            "Generation completed without the expected output",
            "Comfy finished or exited the workflow, but Adept could not locate the expected output artifact.",
            "Do not treat this as a successful image. Retry only if the original request is still valid.",
        )
        code = "RESULT_MISSING"
    elif text:
        summary, cause, action = (
            "Comfy reported an execution error",
            "The render stopped before a result was registered.",
            "Read the technical detail, then retry only if the original request is still valid.",
        )
        code = "EXECUTION"
    else:
        summary, cause, action = ("No error text was recorded", "The job ended without a message.", "Refresh status.")
        code = "UNKNOWN"
    return {"code": code, "summary": summary, "likelyCause": cause, "nextAction": action, "technical": text[:2000]}


def _prompt_ids(rows: list[Any]) -> set[str]:
    found: set[str] = set()
    for item in rows or []:
        if isinstance(item, (list, tuple)) and len(item) > 1:
            found.add(str(item[1]))
    return found


def correlate_queue(queue: dict[str, Any] | None, adept_prompt_ids: set[str]) -> list[dict[str, Any]]:
    payload = queue or {}
    rows: list[dict[str, Any]] = []
    for lane, key in (("running", "queue_running"), ("pending", "queue_pending")):
        for item in payload.get(key) or []:
            prompt_id = str(item[1]) if isinstance(item, (list, tuple)) and len(item) > 1 else ""
            if not prompt_id:
                continue
            owned = prompt_id in adept_prompt_ids
            rows.append({
                "lane": lane,
                "promptId": prompt_id,
                "ownership": "adept" if owned else "external",
                "label": "Adept" if owned else "External / Unknown",
            })
    return rows


def stall_level(
    *,
    status: str,
    kind: str,
    telemetry_stalled: bool,
    prompt_running: bool,
    prompt_pending: bool,
    history_done: bool,
    comfy_reachable: bool,
) -> str:
    """possible | stalled | none. Long sampling with a live prompt is not stalled."""
    active = str(status or "").lower() in ACTIVE_STATUSES or str(status or "").lower() == "running"
    if not active or history_done:
        return "none"
    if not comfy_reachable and str(status or "").lower() == "running":
        return "stalled"
    if telemetry_stalled and prompt_running:
        return "possible"
    if telemetry_stalled and not prompt_running and not prompt_pending:
        return "stalled"
    _ = kind
    return "none"


def classify_header(
    *,
    reachable: bool,
    running: int,
    pending: int,
    stalled: int,
    latest_problem: str | None,
) -> str:
    if not reachable:
        return "COMFY_UNAVAILABLE"
    if stalled:
        return "JOB_STALLED"
    if latest_problem == "VRAM_OOM" and running == 0:
        return "VRAM_OOM"
    if latest_problem in {"NODE_MISSING", "DIMENSIONS", "EXECUTION", "MODEL_MISSING", "RESULT_MISSING"} and running == 0:
        return "WORKFLOW_ERROR"
    if pending >= 3:
        return "QUEUE_BACKLOG"
    if running >= 0 and running > 0:
        return "BUSY"
    return "HEALTHY"


def referenced_asset_ids(params: dict[str, Any]) -> list[str]:
    found: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            found.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                add(item)

    for key in (
        "referenceAssetIds",
        "plannedReferenceAssetIds",
        "assetId",
        "imageAssetId",
        "startFrameAssetId",
        "sceneAssetId",
        "sourceAssetId",
    ):
        add(params.get(key))
    for key in ("references", "referenceEntities"):
        block = params.get(key)
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict):
                    add(item.get("assetId") or item.get("id"))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def retry_blockers(
    *,
    project_exists: bool,
    params: dict[str, Any],
    present_asset_ids: set[str],
    status: str,
) -> str | None:
    if str(status or "").lower() not in {"failed", "cancelled", "canceled", "interrupted"}:
        return "Retry is available after a failed or cancelled job."
    if not project_exists:
        return "Retry unavailable — the project is missing."
    if not params:
        return "Retry unavailable — the original request was not saved."
    missing = [asset_id for asset_id in referenced_asset_ids(params) if asset_id not in present_asset_ids]
    if missing:
        return "Retry unavailable — required reference missing"
    generator = str(params.get("generatorId") or params.get("model") or params.get("checkpoint") or "")
    if params.get("modelMissing") or (generator == "" and params.get("requireModel") is True):
        return "Retry unavailable — the model from the original request is missing."
    return None


def interpret_comfy_history(payload: Any, prompt_id: str) -> dict[str, Any]:
    """Read one Comfy history document. Missing prompt is present=False, not a success."""
    if not isinstance(payload, dict) or not prompt_id:
        return {"present": False, "completed": False, "hasOutputs": False}
    entry = payload.get(prompt_id)
    if not isinstance(entry, dict) and ("status" in payload or "outputs" in payload):
        entry = payload
    if not isinstance(entry, dict):
        return {"present": False, "completed": False, "hasOutputs": False}
    status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
    status_str = str(status.get("status_str") or "").lower()
    completed = bool(status.get("completed")) or status_str in {"success", "completed"}
    outputs = entry.get("outputs")
    has_outputs = isinstance(outputs, dict) and any(bool(value) for value in outputs.values())
    return {"present": True, "completed": completed, "hasOutputs": has_outputs}


def _age_seconds(updated_at: str | None) -> float | None:
    if not updated_at:
        return None
    text = str(updated_at).replace("Z", "")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is not None:
        stamp = stamp.replace(tzinfo=None)
    return max(0.0, (datetime.utcnow() - stamp).total_seconds())


def reconcile_state(
    *,
    status: str,
    prompt_running: bool,
    prompt_pending: bool,
    telemetry_stalled: bool,
    comfy_reachable: bool,
    history_present: bool | None,
    history_completed: bool,
    history_has_outputs: bool,
    output_present: bool,
    age_sec: float | None,
    kind: str = "",
) -> dict[str, Any]:
    """Compare Adept state with Comfy queue and history. Telemetry is not required."""
    state = str(status or "").lower()
    normal = {"relation": "normal", "stall": "none", "label": "", "resultMissing": False}

    if state in {"running", "processing"} and prompt_running:
        return {**normal, "stall": "possible" if telemetry_stalled else "none"}

    if state in {"queued", "claimed"} and not prompt_running:
        return normal

    if state in {"running", "processing"} and prompt_pending:
        return normal

    output_ok = bool(output_present or history_has_outputs)
    if state in {"running", "processing"} and history_completed and output_ok:
        return {
            "relation": "mismatch",
            "stall": "none",
            "label": "State mismatch — awaiting reconciliation",
            "resultMissing": False,
        }
    if state in {"running", "processing"} and history_completed and not output_ok:
        return {
            "relation": "result_missing",
            "stall": "none",
            "label": "Generation completed without the expected output",
            "resultMissing": True,
        }

    prompt_gone = not prompt_running and not prompt_pending and history_present is False
    if state in {"running", "processing"} and prompt_gone:
        settled = telemetry_stalled or (age_sec is not None and age_sec >= RECONCILE_GRACE_SEC)
        if not comfy_reachable or settled:
            return {
                "relation": "stalled",
                "stall": "stalled",
                "label": "Stalled — lost execution",
                "resultMissing": False,
            }
        return normal

    if state == "done" and prompt_running:
        return {
            "relation": "mismatch",
            "stall": "none",
            "label": "State mismatch — Adept completed while Comfy is still running",
            "resultMissing": False,
        }
    if state in {"cancelled", "canceled"} and prompt_running:
        return {
            "relation": "mismatch",
            "stall": "none",
            "label": "State mismatch — Adept cancelled while Comfy is still running",
            "resultMissing": False,
        }
    if state == "failed" and history_completed:
        return {
            "relation": "mismatch",
            "stall": "none",
            "label": "State mismatch — Adept failed while Comfy completed",
            "resultMissing": False,
        }

    level = stall_level(
        status=state,
        kind=kind,
        telemetry_stalled=telemetry_stalled,
        prompt_running=prompt_running,
        prompt_pending=prompt_pending,
        history_done=state == "done",
        comfy_reachable=comfy_reachable,
    )
    if level == "stalled":
        return {"relation": "stalled", "stall": "stalled", "label": "Stalled — the job is not moving in Comfy", "resultMissing": False}
    if level == "possible":
        return {"relation": "possible", "stall": "possible", "label": "Possible stall — Comfy still has this job", "resultMissing": False}
    return normal


def job_view(
    row: dict[str, Any],
    *,
    project_name: str,
    queue_running: set[str],
    queue_pending: set[str],
    comfy_reachable: bool,
    comfy_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    history = row.get("history") if isinstance(row.get("history"), dict) else {}
    tel = history.get("progressTelemetry") if isinstance(history.get("progressTelemetry"), dict) else {}
    prompt_id = str(row.get("comfy_prompt_id") or "")
    source = source_label(str(row.get("kind") or ""), params)
    observed = comfy_history if isinstance(comfy_history, dict) else None
    reconciliation = reconcile_state(
        status=str(row.get("status") or ""),
        prompt_running=bool(prompt_id) and prompt_id in queue_running,
        prompt_pending=bool(prompt_id) and prompt_id in queue_pending,
        telemetry_stalled=bool(tel.get("stalled")),
        comfy_reachable=comfy_reachable,
        history_present=None if observed is None else bool(observed.get("present")),
        history_completed=bool(observed and observed.get("completed")),
        history_has_outputs=bool(observed and observed.get("hasOutputs")),
        output_present=bool(str(row.get("output_path") or "").strip()),
        age_sec=_age_seconds(row.get("updated_at")),
        kind=str(row.get("kind") or ""),
    )
    level = reconciliation["stall"]
    raw_status = str(row.get("status") or "")
    error = normalize_error(str(row.get("message") or "")) if raw_status in PROBLEM_STATUSES else None
    if reconciliation["resultMissing"]:
        error = normalize_error(str(row.get("message") or "") or "expected result missing: no output image")
        if error["code"] != "RESULT_MISSING":
            error = normalize_error("expected result missing: no output image")
            error["technical"] = str(row.get("message") or error["technical"])
    elif reconciliation["relation"] == "mismatch":
        error = {
            "code": "STATE_MISMATCH",
            "summary": reconciliation["label"],
            "likelyCause": "Adept and Comfy disagree. This screen does not mark the job successful.",
            "nextAction": "Reconcile status. Completion still requires the expected output.",
            "technical": str(row.get("message") or raw_status),
        }
    width = params.get("width")
    height = params.get("height")
    return {
        "adeptJobId": row.get("id"),
        "projectId": row.get("project_id"),
        "projectName": project_name or "Project",
        "sceneId": row.get("scene_id"),
        "shotId": params.get("shotId") or params.get("shot_id"),
        "source": source,
        "workspace": workspace_for(source),
        "kind": row.get("kind"),
        "model": params.get("generatorId") or params.get("model") or params.get("checkpoint") or "",
        "workflow": params.get("workflowKey") or params.get("workflow") or "",
        "comfyPromptId": prompt_id,
        "status": raw_status,
        "statusLabel": status_label(raw_status),
        "stage": row.get("stage") or "",
        "reconciliation": reconciliation["relation"],
        "reconciliationLabel": reconciliation["label"],
        "resultMissing": reconciliation["resultMissing"],
        "progress": row.get("progress") or 0,
        "message": row.get("message") or "",
        "elapsedSec": tel.get("elapsedActiveTime"),
        "lastProgressAt": tel.get("lastProgressAt"),
        "currentNode": tel.get("currentNode"),
        "width": width,
        "height": height,
        "durationSec": params.get("durationSec") or params.get("duration"),
        "megapixels": params.get("megapixels"),
        "stall": level,
        "problem": error,
        "outputPath": row.get("output_path") or "",
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
        "video": str(row.get("kind") or "") in VIDEO_KINDS or str(row.get("kind") or "").startswith("magi_"),
    }


def header_from_parts(
    *,
    reachable: bool,
    pid: int | None,
    command_expected: bool,
    running: int,
    pending: int,
    stalled_jobs: int,
    latest_problem: str | None,
    vram_total: int | None,
    vram_free: int | None,
    gpu_name: str | None,
    submissions_paused: bool,
) -> dict[str, Any]:
    state = classify_header(
        reachable=reachable and command_expected,
        running=running,
        pending=pending,
        stalled=stalled_jobs,
        latest_problem=latest_problem,
    )
    if reachable and not command_expected:
        state = "DISCONNECTED"
    labels = {
        "HEALTHY": "Healthy",
        "BUSY": "Busy",
        "QUEUE_BACKLOG": "Queue backlog",
        "JOB_STALLED": "Job stalled",
        "WORKFLOW_ERROR": "Workflow error",
        "VRAM_OOM": "GPU memory",
        "DISCONNECTED": "Disconnected",
        "COMFY_UNAVAILABLE": "Comfy unavailable",
    }
    return {
        "state": state,
        "label": labels.get(state, state),
        "host": "127.0.0.1:8188",
        "pid": pid,
        "running": running,
        "queued": pending,
        "vramTotal": vram_total,
        "vramFree": vram_free,
        "gpu": gpu_name,
        "submissionsPaused": submissions_paused,
        "checkedAt": datetime.utcnow().isoformat() + "Z",
    }
