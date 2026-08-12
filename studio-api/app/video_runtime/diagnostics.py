"""Aggregated Video Runtime diagnostics for the operator dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .compatibility_registry import catalog_as_dict, list_entries, missing_nodes
from .vram_safety import _free_vram_gb


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _avg_render_seconds(db: Any) -> dict[str, float | None]:
    """Average completed job duration by engine family from Job rows."""
    from ..db import Job

    rows = (
        db.query(Job)
        .filter(Job.status.in_(("completed", "complete", "succeeded")))
        .order_by(Job.updated_at.desc())
        .limit(200)
        .all()
    )
    buckets: dict[str, list[float]] = {"ltx": [], "wan": [], "fal": [], "lipsync": []}
    for job in rows:
        created = job.created_at
        updated = job.updated_at
        if not created or not updated:
            continue
        secs = (updated - created).total_seconds()
        if secs <= 0 or secs > 86_400:
            continue
        kind = (job.kind or "").lower()
        msg = (job.message or "").lower()
        engine = ""
        try:
            import json

            params = json.loads(job.params_json or "{}")
            if isinstance(params, dict):
                vr = params.get("videoRuntime") or {}
                engine = str(vr.get("engine") or params.get("engine") or "").lower()
        except Exception:  # noqa: BLE001
            engine = ""
        if "lipsync" in kind:
            buckets["lipsync"].append(secs)
        elif engine.startswith("fal") or "fal" in msg:
            buckets["fal"].append(secs)
        elif "wan" in engine or "wan" in msg:
            buckets["wan"].append(secs)
        elif "ltx" in engine or "ltx" in msg or kind.startswith("render"):
            buckets["ltx"].append(secs)

    def avg(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 1) if vals else None

    return {k: avg(v) for k, v in buckets.items()}


async def build_diagnostics(db: Any | None = None) -> dict[str, Any]:
    from ..comfy_client import comfy
    from ..comfy_health import comfy_health, model_component_states
    from ..vram_profiles import query_gpu_stats

    health = await comfy_health()
    gpu = query_gpu_stats()
    free_gb = _free_vram_gb()

    node_types: set[str] | None = None
    try:
        catalogue = await comfy.get_object_info()
        if isinstance(catalogue, dict) and catalogue:
            node_types = {str(k) for k in catalogue}
    except Exception:  # noqa: BLE001
        node_types = None

    # Registry-relative missing nodes across production_ready local entries
    missing_total = 0
    if node_types is not None:
        for entry in list_entries():
            if entry.capability_state != "production_ready" or entry.provider_kind.value != "local":
                continue
            miss = missing_nodes(entry, node_types) or []
            missing_total += len(miss)

    models = model_component_states()
    model_map = {m["componentId"]: m for m in models}

    def present(cid: str) -> bool:
        item = model_map.get(cid)
        return bool(item and item.get("present"))

    queue_running = 0
    queue_pending = 0
    try:
        q = await comfy.get_queue()
        queue_running = len(q.get("queue_running") or [])
        queue_pending = len(q.get("queue_pending") or [])
    except Exception:  # noqa: BLE001
        pass

    studio_running = 0
    studio_waiting = 0
    peak_vram = None
    averages: dict[str, float | None] = {"ltx": None, "wan": None, "fal": None, "lipsync": None}
    if db is not None:
        from ..db import Job

        studio_running = db.query(Job).filter(Job.status == "running").count()
        studio_waiting = db.query(Job).filter(Job.status == "queued").count()
        averages = _avg_render_seconds(db)

    gpu_name = None
    if gpu.get("ok") and gpu.get("gpus"):
        gpu_name = gpu["gpus"][0].get("name")
        used = gpu["gpus"][0].get("memory_used_mib")
        if isinstance(used, (int, float)):
            peak_vram = round(float(used) / 1024.0, 2)

    devices = health.get("devices") or []
    if gpu_name is None and devices:
        gpu_name = devices[0].get("name")

    overall = "Excellent"
    if not health.get("reachable"):
        overall = "Unavailable"
    elif health.get("status") == "degraded" or missing_total or health.get("missingModelComponentIds"):
        overall = "Degraded"
    elif queue_running + studio_running > 1:
        overall = "Busy"

    wiring = _wave6_wiring_unlocked()
    production = _wave6_production_unlocked()

    return {
        "comfyui": {
            "connected": bool(health.get("reachable")),
            "version": health.get("version"),
            "baseUrl": health.get("baseUrl"),
            "status": health.get("status"),
            "message": health.get("message"),
        },
        "gpu": {
            "name": gpu_name,
            "availableGb": free_gb,
            "currentGb": peak_vram,
            "peakGb": peak_vram,
        },
        "nodeInventory": {
            "installed": health.get("nodeTypeCount") or (len(node_types) if node_types else 0),
            "missingVsRegistry": missing_total,
        },
        "modelInventory": {
            "wan": present("wan_models"),
            "ltx": present("ltx_checkpoint"),
            "zimage": present("zimage_models"),
            "icLora": present("ltx23_ic_lora_ingredients"),
        },
        "queue": {
            "comfyRunning": queue_running,
            "comfyWaiting": queue_pending,
            "studioRunning": studio_running,
            "studioWaiting": studio_waiting,
        },
        "averageRenderSeconds": averages,
        "vram": {
            "currentGb": peak_vram,
            "availableGb": free_gb,
            "peakGb": peak_vram,
        },
        "health": overall,
        "compatibilityCatalog": catalog_as_dict(),
        "checkedAt": _now(),
        "wave6WiringUnlocked": wiring,
        "wave6ProductionActivationUnlocked": production,
        "wave6MediaExecutionUnlocked": production,  # legacy alias = production only
        "phase": "M41-4.1A",
    }


def _cert_text() -> str:
    from pathlib import Path

    cert = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "release-gate"
        / "m41"
        / "M41_41A_VIDEO_RUNTIME_CERTIFICATION_REPORT.md"
    )
    if not cert.is_file():
        return ""
    return cert.read_text(encoding="utf-8", errors="ignore")


def _wave6_wiring_unlocked() -> bool:
    """Wave 6 *wiring* may begin on CONDITIONAL GO or full GO."""
    text = _cert_text()
    return "CONDITIONAL GO" in text or (
        "**GO" in text and "Video Runtime & Generation Infrastructure complete" in text
    )


def _wave6_production_unlocked() -> bool:
    """Production activation requires full GO after live cancel/VRAM/playback cert."""
    text = _cert_text()
    if "CONDITIONAL GO" in text:
        return False
    return "**GO" in text and "Video Runtime & Generation Infrastructure complete" in text


def _wave6_unlocked() -> bool:
    """Legacy alias: production activation unlock only."""
    return _wave6_production_unlocked()


def engine_to_workflow_key(engine: str | None) -> str | None:
    e = (engine or "").lower().strip()
    mapping = {
        "ltx": "ltx.simple_i2v",
        "wan": "wan.first_last_frame",
        "fal_seedance": "fal.seedance",
        "fal_kling": "fal.kling",
        "fal_veo": "fal.veo",
        "fal_runway": "fal.runway",
    }
    return mapping.get(e)
