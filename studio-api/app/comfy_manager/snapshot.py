"""Build one Comfy Manager snapshot from the live job table and Comfy HTTP."""

from __future__ import annotations

import json
from typing import Any

from .operations import (
    _prompt_ids,
    correlate_queue,
    header_from_parts,
    interpret_comfy_history,
    job_view,
    normalize_error,
)


def _loads(raw: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_snapshot(db: Any) -> dict[str, Any]:
    from ..comfy_client import comfy
    from ..comfy_health import authoritative_comfy_health
    from ..db import Job, Project
    from ..queue_worker import job_queue
    from runtime_supervisor.process import process_command_line

    health = authoritative_comfy_health(timeout_sec=3.0)
    stats_status = health.get("httpStatus")
    stats = health.get("stats") if isinstance(health.get("stats"), dict) else {}
    queue_status, queue = comfy.read_queue(timeout=3.0)
    history_status, _history_probe = comfy.read_history(timeout=2.0)
    reachable = bool(health.get("healthy"))
    pids = list(health.get("pids") or [])
    pid = health.get("pid")
    command = ""
    if pid:
        try:
            command = process_command_line(pid)
        except Exception:
            command = ""
    command_expected = "comfy" in command.lower() or "main.py" in command.lower()
    device = {}
    if health.get("gpu") or health.get("vramTotal") or health.get("vramFree"):
        device = {"name": health.get("gpu"), "vram_total": health.get("vramTotal"), "vram_free": health.get("vramFree")}

    rows = db.query(Job).order_by(Job.updated_at.desc()).limit(40).all()
    projects = {
        project.id: project.name
        for project in db.query(Project).filter(Project.id.in_([row.project_id for row in rows] or [""])).all()
    } if rows else {}
    adept_prompts = {str(row.comfy_prompt_id) for row in rows if row.comfy_prompt_id}
    running_ids = _prompt_ids(queue.get("queue_running") or [])
    pending_ids = _prompt_ids(queue.get("queue_pending") or [])
    prepared = []
    for row in rows:
        prepared.append(
            {
                "id": row.id,
                "project_id": row.project_id,
                "scene_id": row.scene_id,
                "kind": row.kind,
                "status": row.status,
                "stage": row.stage,
                "progress": row.progress,
                "message": row.message,
                "comfy_prompt_id": row.comfy_prompt_id,
                "output_path": row.output_path,
                "params": _loads(row.params_json),
                "history": _loads(row.history_json),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )
    history_by_prompt: dict[str, dict[str, Any] | None] = {}
    lookups = 0
    for item in prepared:
        prompt_id = str(item.get("comfy_prompt_id") or "")
        status = str(item.get("status") or "")
        needs_history = bool(prompt_id) and (
            (status in {"running", "processing", "failed"} and prompt_id not in running_ids and prompt_id not in pending_ids)
            or (status == "failed")
        )
        if not needs_history or prompt_id in history_by_prompt or lookups >= 8:
            continue
        code, payload = comfy.read_history(prompt_id, timeout=2.0)
        history_by_prompt[prompt_id] = interpret_comfy_history(payload, prompt_id) if code == 200 else None
        lookups += 1
    jobs = [
        job_view(
            item,
            project_name=str(projects.get(item["project_id"]) or ""),
            queue_running=running_ids,
            queue_pending=pending_ids,
            comfy_reachable=reachable,
            comfy_history=history_by_prompt.get(str(item.get("comfy_prompt_id") or "")),
        )
        for item in prepared
    ]
    stalled = [job for job in jobs if job["stall"] == "stalled"]
    newest = jobs[0] if jobs else None
    newest_problem = (newest or {}).get("problem") or {}
    latest_problem = None
    if newest and newest.get("status") in {"failed", "interrupted"} and newest_problem.get("code") not in {None, "UNKNOWN"}:
        latest_problem = newest_problem.get("code")
    header = header_from_parts(
        reachable=reachable,
        pid=pid if command_expected else pid,
        command_expected=bool(command_expected or not pid),
        running=len(queue.get("queue_running") or []),
        pending=len(queue.get("queue_pending") or []),
        stalled_jobs=len(stalled),
        latest_problem=latest_problem,
        vram_total=device.get("vram_total"),
        vram_free=device.get("vram_free"),
        gpu_name=device.get("name"),
        submissions_paused=bool(job_queue.adept_submissions_paused),
    )
    if not reachable:
        header["state"] = "COMFY_UNAVAILABLE"
        header["label"] = "Comfy unavailable"
    queue_rows = correlate_queue(queue if queue_status == 200 else None, adept_prompts)
    for item in queue_rows:
        match = next((job for job in jobs if job["comfyPromptId"] == item["promptId"]), None)
        if match:
            item["source"] = match["source"]
            item["projectName"] = match["projectName"]
            item["adeptJobId"] = match["adeptJobId"]
            item["model"] = match["model"]
    problems = []
    for job in jobs:
        if job["stall"] in {"possible", "stalled"} or job.get("problem"):
            problem = job.get("problem") or normalize_error(job.get("message") or "")
            if job["stall"] == "possible":
                problem = {
                    **problem,
                    "summary": "Possible stall — Comfy still has this job",
                    "likelyCause": "Progress has gone quiet, and the prompt is still running. A long video step can look like this.",
                    "nextAction": "Refresh status. Interrupt only if it stays quiet after the stage should have moved.",
                }
            elif job["stall"] == "stalled":
                problem = {
                    **problem,
                    "summary": "Stalled — the job is not moving in Comfy",
                    "likelyCause": "Adept still marks it active, and Comfy no longer has a running prompt for it.",
                    "nextAction": "Refresh status, then cancel and retry if the original request is still valid.",
                }
            problems.append({"job": job, "whatHappened": problem["summary"], "likelyCause": problem["likelyCause"], "nextAction": problem["nextAction"], "technical": problem.get("technical") or job.get("message") or ""})
    return {
        "header": header,
        "jobs": jobs,
        "active": [job for job in jobs if job["status"] in {"queued", "running", "processing", "cancelling"}],
        "queue": queue_rows,
        "history": jobs,
        "problems": problems,
        "diagnostics": {
            "healthHttp": stats_status,
            "queueHttp": queue_status,
            "historyHttp": history_status,
            "healthOwner": "ComfyClient.read_system_stats",
            "pid": pid,
            "listenerCount": len(pids),
            "command": command[:300],
            "commandExpected": command_expected,
            "progressChannel": "This screen rereads the Adept job on a short interval. It does not open a second Comfy socket.",
            "nodeCatalogue": "Refresh reads health and queue. The node catalogue stays with the existing readiness owner.",
            "submissionsPaused": bool(job_queue.adept_submissions_paused),
            "comfyRestarted": False,
        },
        "cleanup": {"items": [], "bytes": 0, "note": "No temporary file was proven safe to remove. Library, published media, models, and references are left untouched."},
    }
