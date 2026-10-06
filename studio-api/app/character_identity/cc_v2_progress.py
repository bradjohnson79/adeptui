"""Backend-truth progress for Character Creator V2 jobs and compose.

Never invent a creeping percentage. Use the provider number when present;
otherwise stay on a deterministic stage floor.
"""

from __future__ import annotations

from typing import Any

from ..db import Job

STAGE_FLOORS: dict[str, int] = {
    "preparing": 10,
    "submitting": 20,
    "queued": 25,
    "generating": 25,
    "saving": 95,
    "ready": 100,
}

VIEW_STAGE_LABELS: dict[str, dict[str, str]] = {
    "front": {
        "preparing": "Preparing Front…",
        "submitting": "Submitting Front…",
        "queued": "Front queued…",
        "generating": "Generating Front…",
        "saving": "Saving Front…",
        "ready": "Front Ready",
        "failed": "Front Generation Failed",
    },
    "back": {
        "preparing": "Preparing Back…",
        "submitting": "Submitting Back workflow…",
        "queued": "Back waiting its turn…",
        "generating": "GPU is working on Back…",
        "saving": "Saving Back…",
        "ready": "Back Ready",
        "failed": "Back Generation Failed",
    },
    "closeup": {
        "preparing": "Preparing Close-up…",
        "submitting": "Submitting Close-up…",
        "queued": "Close-up queued…",
        "generating": "Generating Close-up…",
        "saving": "Saving Close-up…",
        "ready": "Close-up Ready",
        "failed": "Close-up Generation Failed",
    },
    "side": {
        "preparing": "Preparing Side…",
        "submitting": "Submitting Side…",
        "queued": "Side waiting its turn…",
        "generating": "GPU is working on Side…",
        "saving": "Saving Side…",
        "ready": "Side Ready",
        "failed": "Side Generation Failed",
    },
    "three_quarter": {
        "preparing": "Preparing 3/4…",
        "submitting": "Submitting 3/4…",
        "queued": "3/4 waiting its turn…",
        "generating": "GPU is working on 3/4…",
        "saving": "Saving 3/4…",
        "ready": "3/4 Ready",
        "failed": "3/4 Generation Failed",
    },
    "back": {
        "preparing": "Preparing Back…",
        "submitting": "Submitting Back…",
        "queued": "Back waiting its turn…",
        "generating": "GPU is working on Back…",
        "saving": "Saving Back…",
        "ready": "Back Ready",
        "failed": "Back Generation Failed",
    },
}

SHEET_STAGES: tuple[tuple[int, str, str], ...] = (
    (10, "validate", "Validating approved assets"),
    (25, "load_front", "Preparing Front"),
    (40, "load_back", "Preparing Back"),
    (55, "layout", "Resolving layout"),
    (70, "json_table", "Formatting Character JSON"),
    (85, "compose", "Composing 21:9 layout"),
    (95, "save", "Saving to Library"),
    (100, "ready", "Character Sheet Ready"),
)

VISION_STAGES: dict[str, str] = {
    "none": "",
    "analyzing": "Co-Director is studying the Front view…",
    "analyzing_both": "Co-Director is updating character details from both views…",
    "saving": "Saving Visual Lock…",
    "ready": "Character Active",
    "failed": "Co-Director could not finish this step",
}


def _as_percent(raw: Any) -> int | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return 0
    if value <= 1:
        return int(round(value * 100))
    return min(100, int(round(value)))


def _job_provider_id(job: Job) -> str | None:
    from .visual_sheet import _job_params

    params = _job_params(job)
    for key in (
        "providerJobId",
        "hostedRequestId",
        "kieTaskId",
        "falRequestId",
        "requestId",
    ):
        value = str(params.get(key) or "").strip()
        if value:
            return value
    return str(job.comfy_prompt_id or "").strip() or None


def map_job_progress(
    job: Job | None,
    *,
    view: str,
    has_output: bool,
    approved: bool = False,
) -> dict[str, Any]:
    labels = VIEW_STAGE_LABELS.get(view) or VIEW_STAGE_LABELS["front"]
    if job is None:
        if approved or has_output:
            return {
                "percent": 100,
                "stage": "ready",
                "label": labels["ready"],
                "source": "stage",
                "jobId": None,
                "providerJobId": None,
            }
        return {
            "percent": 0,
            "stage": "idle",
            "label": "",
            "source": "stage",
            "jobId": None,
            "providerJobId": None,
        }

    status = str(job.status or "").strip().lower()
    provider_job_id = _job_provider_id(job)
    measured = _as_percent(job.progress)
    job_stage = str(job.stage or "").strip().lower()

    if approved and has_output:
        return {
            "percent": 100,
            "stage": "ready",
            "label": labels["ready"],
            "source": "job",
            "jobId": job.id,
            "providerJobId": provider_job_id,
        }

    if status in {"failed", "error", "cancelled"}:
        frozen = measured if measured is not None and measured < 100 else None
        return {
            "percent": frozen,
            "stage": "failed",
            "label": labels["failed"],
            "source": "job",
            "jobId": job.id,
            "providerJobId": provider_job_id,
        }

    if status == "done" and has_output:
        return {
            "percent": 100,
            "stage": "ready",
            "label": labels["ready"],
            "source": "job",
            "jobId": job.id,
            "providerJobId": provider_job_id,
        }

    if status == "done" and not has_output:
        return {
            "percent": STAGE_FLOORS["saving"],
            "stage": "saving",
            "label": labels["saving"],
            "source": "stage",
            "jobId": job.id,
            "providerJobId": provider_job_id,
        }

    if measured is not None and measured > 0 and status in {"running", "starting", "queued"}:
        percent = min(90, max(STAGE_FLOORS["generating"], measured)) if status != "done" else measured
        if status in {"queued", "starting"} and not job.comfy_prompt_id and measured < STAGE_FLOORS["queued"]:
            percent = max(percent, STAGE_FLOORS["queued"])
        return {
            "percent": min(99, percent) if not has_output else 100,
            "stage": "generating" if status == "running" else (job_stage or "queued"),
            "label": labels["generating"] if status == "running" else labels.get(job_stage) or labels["queued"],
            "source": "provider",
            "jobId": job.id,
            "providerJobId": provider_job_id,
        }

    if not job.comfy_prompt_id and status in {"queued", "starting"}:
        stage = "preparing" if status == "starting" or not job_stage else "queued"
        if status == "queued":
            stage = "preparing" if not str(job.message or "").strip() else "queued"
        return {
            "percent": STAGE_FLOORS[stage],
            "stage": stage,
            "label": labels[stage],
            "source": "stage",
            "jobId": job.id,
            "providerJobId": provider_job_id,
        }

    if job.comfy_prompt_id and status == "queued":
        return {
            "percent": STAGE_FLOORS["queued"],
            "stage": "queued",
            "label": labels["queued"],
            "source": "stage",
            "jobId": job.id,
            "providerJobId": provider_job_id,
        }

    if status in {"running", "starting"}:
        return {
            "percent": STAGE_FLOORS["generating"],
            "stage": "generating",
            "label": labels["generating"],
            "source": "stage",
            "jobId": job.id,
            "providerJobId": provider_job_id,
        }

    return {
        "percent": STAGE_FLOORS["submitting"],
        "stage": "submitting",
        "label": labels["submitting"],
        "source": "stage",
        "jobId": job.id,
        "providerJobId": provider_job_id,
    }


def sheet_progress(percent: int, stage: str, label: str, *, error: str | None = None) -> dict[str, Any]:
    return {
        "status": "failed" if error else ("ready" if percent >= 100 else "composing"),
        "progress": {
            "percent": percent,
            "stage": stage,
            "label": label,
            "source": "compose",
        },
        "error": error,
    }


def vision_progress(stage: str, *, error: str | None = None) -> dict[str, Any]:
    key = str(stage or "none")
    return {
        "stage": key,
        "label": VISION_STAGES.get(key) or "",
        "percent": None,
        "error": error,
        "source": "vision",
    }
