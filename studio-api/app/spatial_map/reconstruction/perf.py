"""Atlas performance trace — one click → compiler runs → Comfy prompts → retries.

Does not change generation knobs. Evidence only.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PERF_CATEGORY = "atlas_perf"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_click_id() -> str:
    return f"atlasclick_{uuid4().hex[:16]}"


def _empty_trace(click_id: str, project_id: str, source_asset_id: str = "") -> dict[str, Any]:
    return {
        "clickId": click_id,
        "projectId": project_id,
        "sourceAssetId": source_asset_id,
        "compilerExecutions": 0,
        "comfyPrompts": 0,
        "retryCount": 0,
        "jobs": [],
        "stages": [],
        "gpuSamples": [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }


def load_atlas_perf(db: Session, project_id: str, click_id: str) -> dict[str, Any] | None:
    if not click_id:
        return None
    from ..ers_persistence import _load_trait_value

    raw = _load_trait_value(db, project_id=project_id, category=PERF_CATEGORY, key=click_id)
    if not raw:
        return None
    try:
        import json

        data = json.loads(raw) if isinstance(raw, str) else raw
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("Failed to load atlas perf %s: %s", click_id, exc)
        return None


def save_atlas_perf(db: Session, project_id: str, trace: dict[str, Any]) -> dict[str, Any]:
    from ..ers_persistence import _upsert_trait

    import json

    trace["updatedAt"] = _now()
    click_id = str(trace.get("clickId") or new_click_id())
    trace["clickId"] = click_id
    _upsert_trait(
        db,
        project_id=project_id,
        category=PERF_CATEGORY,
        key=click_id,
        value=json.dumps(trace),
        provenance="atlas_perf_trace",
    )
    return trace


def ensure_atlas_perf(
    db: Session,
    project_id: str,
    click_id: str,
    *,
    source_asset_id: str = "",
) -> dict[str, Any]:
    existing = load_atlas_perf(db, project_id, click_id)
    if existing:
        if source_asset_id and not existing.get("sourceAssetId"):
            existing["sourceAssetId"] = source_asset_id
        return existing
    return save_atlas_perf(db, project_id, _empty_trace(click_id, project_id, source_asset_id))


def record_compiler_execution(
    db: Session,
    project_id: str,
    click_id: str,
    *,
    execution_id: str,
    source_asset_id: str = "",
    rebuilt_packet: bool,
    rebuilt_guide: bool,
    retry_index: int = 0,
) -> dict[str, Any]:
    trace = ensure_atlas_perf(db, project_id, click_id, source_asset_id=source_asset_id)
    trace["compilerExecutions"] = int(trace.get("compilerExecutions") or 0) + 1
    trace["retryCount"] = max(int(trace.get("retryCount") or 0), int(retry_index or 0))
    jobs = list(trace.get("jobs") or [])
    jobs.append(
        {
            "executionId": execution_id,
            "jobId": "",
            "promptId": "",
            "retryIndex": int(retry_index or 0),
            "rebuiltPacket": bool(rebuilt_packet),
            "rebuiltGuide": bool(rebuilt_guide),
        }
    )
    trace["jobs"] = jobs
    return save_atlas_perf(db, project_id, trace)


def record_stage(
    db: Session,
    project_id: str,
    click_id: str,
    name: str,
    duration_ms: float,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace = ensure_atlas_perf(db, project_id, click_id)
    stages = list(trace.get("stages") or [])
    row = {"name": name, "durationMs": round(float(duration_ms), 1), "at": _now()}
    if extra:
        row.update(extra)
    stages.append(row)
    trace["stages"] = stages
    return save_atlas_perf(db, project_id, trace)


def record_comfy_prompt(
    db: Session,
    project_id: str,
    click_id: str,
    *,
    job_id: str,
    prompt_id: str,
    execution_id: str = "",
    workflow_key: str = "",
) -> dict[str, Any]:
    trace = ensure_atlas_perf(db, project_id, click_id)
    jobs = list(trace.get("jobs") or [])
    known = {str(row.get("promptId") or "") for row in jobs if row.get("promptId")}
    attached = False
    for row in reversed(jobs):
        if execution_id and row.get("executionId") == execution_id and not row.get("promptId"):
            row["jobId"] = job_id
            row["promptId"] = prompt_id
            row["workflowKey"] = workflow_key
            attached = True
            break
        if job_id and row.get("jobId") == job_id:
            row["promptId"] = prompt_id
            row["workflowKey"] = workflow_key
            attached = True
            break
    if not attached:
        jobs.append(
            {
                "executionId": execution_id,
                "jobId": job_id,
                "promptId": prompt_id,
                "workflowKey": workflow_key,
                "retryIndex": int(trace.get("retryCount") or 0),
            }
        )
    if prompt_id and prompt_id not in known:
        trace["comfyPrompts"] = int(trace.get("comfyPrompts") or 0) + 1
    trace["jobs"] = jobs
    return save_atlas_perf(db, project_id, trace)


def sample_gpu() -> dict[str, Any]:
    sample: dict[str, Any] = {"at": _now()}
    try:
        import httpx

        res = httpx.get("http://127.0.0.1:8188/system_stats", timeout=2.0)
        if res.is_success:
            body = res.json()
            devices = body.get("devices") or []
            first = devices[0] if devices else {}
            raw = first.get("vram_free") or first.get("vramFree")
            free_mib = None
            if raw is not None:
                free_mib = float(raw) / (1024 * 1024) if float(raw) > 100_000 else float(raw)
            sample["comfy"] = {
                "device": first.get("name") or first.get("index"),
                "vram_free_mib": free_mib,
                "vram_total_mib": first.get("vram_total") or first.get("vramTotal"),
            }
    except Exception as exc:
        sample["comfyError"] = str(exc)[:180]
    try:
        import subprocess

        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if out.returncode == 0 and out.stdout.strip():
            parts = [p.strip() for p in out.stdout.strip().split(",")]
            if len(parts) >= 5:
                sample["nvidia"] = {
                    "name": parts[0],
                    "gpuUtil": float(parts[1]),
                    "memUtil": float(parts[2]),
                    "vramUsedMib": float(parts[3]),
                    "vramTotalMib": float(parts[4]),
                }
    except Exception as exc:
        sample["nvidiaError"] = str(exc)[:180]
    return sample


def record_gpu_sample(db: Session, project_id: str, click_id: str, *, label: str = "") -> dict[str, Any]:
    trace = ensure_atlas_perf(db, project_id, click_id)
    row = sample_gpu()
    if label:
        row["label"] = label
    samples = list(trace.get("gpuSamples") or [])
    samples.append(row)
    trace["gpuSamples"] = samples
    return save_atlas_perf(db, project_id, trace)


class StageTimer:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0
