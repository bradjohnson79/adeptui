"""DownloadOperation / InstallPlan models (no secrets)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from ..models import strip_secrets
from .phases import is_terminal


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_op_id() -> str:
    return f"dl_{uuid.uuid4().hex[:16]}"


def new_plan_id() -> str:
    return f"plan_{uuid.uuid4().hex[:12]}"


def new_install_id() -> str:
    return f"inst_{uuid.uuid4().hex[:16]}"


FAILURE_CATEGORIES = frozenset(
    {
        "network_unavailable",
        "authentication_required",
        "permission_denied",
        "rate_limited",
        "source_missing",
        "artifact_missing",
        "source_changed",
        "checksum_mismatch",
        "archive_invalid",
        "disk_full",
        "destination_unwritable",
        "cancelled",
        "process_crashed",
        "provider_error",
        "validation_failed",
        "unknown",
    }
)


def empty_progress(artifacts_total: int = 0) -> dict[str, Any]:
    return {
        "bytesDownloaded": 0,
        "bytesTotal": None,
        "percent": 0.0,
        "speedBytesPerSecond": None,
        "etaSeconds": None,
        "currentArtifact": None,
        "artifactsCompleted": 0,
        "artifactsTotal": artifacts_total,
    }


def empty_capabilities(*, can_pause: bool = False, can_resume: bool = False) -> dict[str, Any]:
    return {
        "canPause": bool(can_pause),
        "canResume": bool(can_resume),
        "canCancel": True,
        "supportsRangeRequests": bool(can_resume),
    }


def normalize_artifact(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    remote = str(raw.get("remotePath") or raw.get("remote_path") or raw.get("path") or "").strip()
    if not remote:
        return None
    dest = str(
        raw.get("destinationRelativePath")
        or raw.get("destination_relative_path")
        or remote
    ).strip()
    return {
        "artifactId": str(raw.get("artifactId") or raw.get("artifact_id") or f"art_{uuid.uuid4().hex[:10]}"),
        "remotePath": remote,
        "destinationRelativePath": dest,
        "expectedSize": raw.get("expectedSize") if raw.get("expectedSize") is not None else raw.get("expected_size"),
        "expectedChecksum": raw.get("expectedChecksum") or raw.get("expected_checksum"),
        "downloadUrl": raw.get("downloadUrl") or raw.get("download_url"),
        "role": raw.get("role"),
    }


def create_install_plan(
    *,
    component_id: str,
    source_id: str | None,
    provider_id: str,
    artifacts: list[dict[str, Any]],
    destination_root: str,
    source_fingerprint: str | None = None,
    source_revision: str | None = None,
    estimated_download_bytes: int | None = None,
    estimated_extracted_bytes: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_artifacts = []
    for item in artifacts:
        art = normalize_artifact(item)
        if art:
            clean_artifacts.append(art)
    download_bytes = estimated_download_bytes
    if download_bytes is None:
        total = 0
        known = False
        for art in clean_artifacts:
            if art.get("expectedSize") is not None:
                total += int(art["expectedSize"])
                known = True
        download_bytes = total if known else None
    extracted = estimated_extracted_bytes
    if extracted is None and download_bytes is not None:
        extracted = int(download_bytes * 1.15)
    required = None
    if download_bytes is not None and extracted is not None:
        required = int(download_bytes + extracted + max(64 * 1024 * 1024, int(download_bytes * 0.1)))
    fingerprint = source_fingerprint or hashlib.sha256(
        f"{provider_id}|{source_id}|{source_revision}|{destination_root}|{[a['remotePath'] for a in clean_artifacts]}".encode()
    ).hexdigest()[:24]
    return strip_secrets(
        {
            "id": new_plan_id(),
            "componentId": component_id,
            "sourceId": source_id,
            "providerId": provider_id,
            "artifacts": clean_artifacts,
            "destinationRoot": destination_root,
            "estimatedDownloadBytes": download_bytes,
            "estimatedExtractedBytes": extracted,
            "requiredFreeBytes": required,
            "sourceFingerprint": fingerprint,
            "sourceRevision": source_revision,
            "verificationRequirements": {},
            "conflicts": [],
            "immutable": False,
            "createdAt": utc_now(),
            "metadata": dict(metadata or {}),
        }
    )


def create_operation(
    plan: dict[str, Any],
    *,
    priority: int = 100,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifacts = list(plan.get("artifacts") or [])
    now = utc_now()
    op = {
        "id": new_op_id(),
        "componentId": plan["componentId"],
        "sourceId": plan.get("sourceId"),
        "installPlanId": plan["id"],
        "providerId": plan.get("providerId"),
        "selectedArtifacts": artifacts,
        "plan": {**plan, "immutable": True},
        "phase": "queued",
        "priority": int(priority),
        "queuePosition": None,
        "progress": empty_progress(len(artifacts)),
        "paths": {
            "stagingDirectory": None,
            "finalDestination": plan.get("destinationRoot"),
        },
        "capabilities": capabilities or empty_capabilities(),
        "retry": {"count": 0, "maxAttempts": 3, "lastAttemptAt": None},
        "failure": None,
        "attempts": [],
        "recovery": None,
        "createdAt": now,
        "startedAt": None,
        "updatedAt": now,
        "completedAt": None,
        "cancelRequested": False,
        "pauseRequested": False,
    }
    if plan.get("estimatedDownloadBytes") is not None:
        op["progress"]["bytesTotal"] = plan["estimatedDownloadBytes"]
    return strip_secrets(op)


def normalize_operation(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    op_id = str(raw.get("id") or "").strip()
    component_id = str(raw.get("componentId") or raw.get("component_id") or "").strip()
    if not op_id or not component_id:
        return None
    phase = str(raw.get("phase") or "queued")
    progress = raw.get("progress") if isinstance(raw.get("progress"), dict) else empty_progress()
    return strip_secrets(
        {
            "id": op_id,
            "componentId": component_id,
            "sourceId": raw.get("sourceId") or raw.get("source_id"),
            "installPlanId": raw.get("installPlanId") or raw.get("install_plan_id"),
            "providerId": raw.get("providerId") or raw.get("provider_id"),
            "selectedArtifacts": list(raw.get("selectedArtifacts") or raw.get("selected_artifacts") or []),
            "plan": raw.get("plan") if isinstance(raw.get("plan"), dict) else {},
            "phase": phase,
            "priority": int(raw.get("priority") or 100),
            "queuePosition": raw.get("queuePosition") if raw.get("queuePosition") is not None else raw.get("queue_position"),
            "progress": progress,
            "paths": raw.get("paths") if isinstance(raw.get("paths"), dict) else {},
            "capabilities": raw.get("capabilities")
            if isinstance(raw.get("capabilities"), dict)
            else empty_capabilities(),
            "retry": raw.get("retry") if isinstance(raw.get("retry"), dict) else {"count": 0, "maxAttempts": 3},
            "failure": raw.get("failure"),
            "attempts": list(raw.get("attempts") or []),
            "recovery": raw.get("recovery"),
            "createdAt": raw.get("createdAt") or raw.get("created_at") or utc_now(),
            "startedAt": raw.get("startedAt") or raw.get("started_at"),
            "updatedAt": raw.get("updatedAt") or raw.get("updated_at") or utc_now(),
            "completedAt": raw.get("completedAt") or raw.get("completed_at"),
            "cancelRequested": bool(raw.get("cancelRequested") or raw.get("cancel_requested")),
            "pauseRequested": bool(raw.get("pauseRequested") or raw.get("pause_requested")),
            "terminal": is_terminal(phase),
        }
    )


def make_failure(
    category: str,
    message: str,
    *,
    phase: str | None = None,
    details: dict[str, Any] | None = None,
    recoverable: bool = True,
    recommended_action: str | None = None,
) -> dict[str, Any]:
    cat = category if category in FAILURE_CATEGORIES else "unknown"
    return strip_secrets(
        {
            "category": cat,
            "message": message,
            "phase": phase,
            "details": dict(details or {}),
            "recoverable": recoverable,
            "recommendedAction": recommended_action,
            "at": utc_now(),
        }
    )


def public_operation(op: dict[str, Any]) -> dict[str, Any]:
    """API-safe view (still no secrets; paths may be summarized)."""
    clean = normalize_operation(op)
    if not clean:
        return {}
    # Avoid leaking full machine paths excessively — keep for now for Open Folder; FE can summarize
    return clean
