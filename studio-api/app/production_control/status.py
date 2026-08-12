"""Aggregate system health for Production Control Dock."""

from __future__ import annotations

from typing import Any

from ..config import settings
from ..codirector.config_store import load_config
from .migration import migration_stamp


def _queue_counts() -> dict[str, Any]:
    try:
        from ..queue_worker import job_queue

        if hasattr(job_queue, "stats"):
            return job_queue.stats()
    except Exception:
        pass
    try:
        from ..db import Job, SessionLocal

        db = SessionLocal()
        try:
            queued = db.query(Job).filter(Job.status == "queued").count()
            running = db.query(Job).filter(Job.status == "running").count()
            return {"queued": queued, "running": running, "source": "db"}
        finally:
            db.close()
    except Exception:
        return {"queued": None, "running": None, "source": "unavailable"}


def aggregate_status() -> dict[str, Any]:
    """Best-effort health snapshot — no secrets."""
    api_online = True
    gpu: dict[str, Any] = {"status": "Unknown", "cuda": None, "device": None}
    codirector: dict[str, Any] = {"configured": False, "model": None, "endpoint": None}
    hosted: dict[str, Any] = {"providers": [], "preferred": None}
    audio_local: dict[str, Any] = {}

    try:
        from ..audio_studio.provider_resolver import local_runtime_status

        audio_local = local_runtime_status()
        ace = audio_local.get("ACE-Step") or {}
        if ace.get("cuda"):
            gpu = {
                "status": "Ready",
                "cuda": True,
                "device": ace.get("device"),
                "accelerator": ace.get("accelerator"),
            }
        elif ace.get("ready"):
            gpu = {"status": "CPU-only detected", "cuda": False, "device": ace.get("device")}
    except Exception as exc:
        audio_local = {"error": str(exc)}

    try:
        cfg = load_config()
        codirector = {
            "configured": bool(cfg.get("endpoint")),
            "model": cfg.get("selectedModel") or cfg.get("primaryModel"),
            "endpoint": cfg.get("endpoint"),
        }
    except Exception:
        pass

    try:
        from ..hosted_providers.preferences import load_preferences
        from ..hosted_providers.registry import list_providers

        prefs = load_preferences()
        providers = []
        for p in list_providers():
            providers.append(
                {
                    "providerId": p.get("provider_id"),
                    "credentialState": p.get("credentialState"),
                    "recommended": p.get("recommended"),
                }
            )
        hosted = {"providers": providers, "preferred": prefs.get("preferredProvider")}
    except Exception:
        pass

    queue = _queue_counts()
    active_runtime = None
    if audio_local.get("ACE-Step", {}).get("ready"):
        active_runtime = "ACE-Step"
    elif audio_local.get("MMAudio", {}).get("ready"):
        active_runtime = "MMAudio"

    from .store import get_user_preferences

    user = get_user_preferences()
    preferred = hosted.get("preferred")
    hosted_connected = any(
        (p.get("credentialState") in ("verified", "connected")) for p in (hosted.get("providers") or [])
    )
    return {
        "ok": True,
        "apiOnline": api_online,
        "runtimeSource": user.runtimeSource,
        "localAvailable": True,
        "apiAvailable": hosted_connected or bool(preferred),
        "hostedProviderConnected": hosted_connected,
        "activeHostedProviderId": preferred,
        "gpu": gpu,
        "codirector": codirector,
        "hosted": hosted,
        "audioLocal": audio_local,
        "queueSummary": {
            "gpuQueued": int(queue.get("queued") or 0),
            "hostedQueued": 0,
            "active": int(queue.get("running") or 0),
        },
        "healthRows": [
            {"id": "api", "label": "Beta API", "status": "Available" if api_online else "Unavailable"},
            {"id": "gpu", "label": "GPU", "status": gpu.get("status") or "Unknown", "detail": gpu.get("device")},
            {
                "id": "ace",
                "label": "ACE-Step",
                "status": "Available" if (audio_local.get("ACE-Step") or {}).get("cuda") else "Requires Setup",
                "detail": (audio_local.get("ACE-Step") or {}).get("message"),
            },
            {
                "id": "mmaudio",
                "label": "MMAudio",
                "status": "Available" if (audio_local.get("MMAudio") or {}).get("cuda") else "Requires Setup",
                "detail": (audio_local.get("MMAudio") or {}).get("message"),
            },
            {
                "id": "codirector",
                "label": "Co-Director LLM",
                "status": "Available" if codirector.get("model") else "Requires Setup",
                "detail": codirector.get("model"),
            },
            {
                "id": "hosted",
                "label": "Hosted Provider",
                "status": "Available" if hosted_connected else "Requires Setup",
                "detail": preferred,
            },
        ],
        "queue": queue,
        "activeRuntime": active_runtime,
        "dataDir": str(settings.data_dir),
        "migration": migration_stamp(),
        "mock": False,
    }
