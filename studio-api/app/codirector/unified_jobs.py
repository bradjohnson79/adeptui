"""Normalize Studio queue and Production Executive jobs for Co-Director."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

UNIFIED_STATUSES = frozenset(
    {
        "created",
        "awaiting_approval",
        "queued",
        "submitted",
        "processing",
        "retrieving",
        "validating",
        "persisting",
        "completed",
        "failed",
        "cancelled",
        "timed_out",
        "interrupted",
        "recovering",
    }
)

_STATUS_MAP = {
    "created": "created",
    "new": "created",
    "waiting": "queued",
    "queued": "queued",
    "submitted": "submitted",
    "running": "processing",
    "processing": "processing",
    "retrieving": "retrieving",
    "validating": "validating",
    "persisting": "persisting",
    "completed": "completed",
    "done": "completed",
    "failed": "failed",
    "blocked": "failed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "timed_out": "timed_out",
    "timeout": "timed_out",
    "interrupted": "interrupted",
    "recovering": "recovering",
    "retrying": "recovering",
    "needsreview": "awaiting_approval",
    "awaiting_approval": "awaiting_approval",
    "paused": "awaiting_approval",
}


def _value(row: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(row, Mapping) and name in row:
            return row[name]
        value = getattr(row, name, None)
        if value is not None:
            return value
    return default


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, (dict, list)) else default
    except (TypeError, json.JSONDecodeError):
        return default


def _sanitize(value: Any) -> Any:
    """Remove credential-like values while retaining useful job metadata."""
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower().replace("-", "_")
            if any(token in lowered for token in ("api_key", "apikey", "secret", "password", "credential", "token")):
                if lowered not in {"token_type"}:
                    continue
            result[key_text] = _sanitize(item)
        return result
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def sanitized_json_text(value: Any) -> str:
    """Return JSON metadata safe for inclusion in compatibility dumps."""
    return json.dumps(_sanitize(_json(value, {})), default=str)


def _status(row: Any) -> str:
    raw = str(_value(row, "status", default="created") or "created")
    stage = str(_value(row, "stage", default="") or "").lower().replace("-", "_")
    if stage in UNIFIED_STATUSES:
        return stage
    return _STATUS_MAP.get(raw.lower().replace(" ", "").replace("-", "_"), "created")


def _timestamp(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _first(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if data.get(key) is not None:
            return data[key]
    return None


def to_unified_dto(job_source: str, row: Any) -> dict[str, Any]:
    """Convert either job row into the stable, credential-free inspect contract."""
    source = "executive" if job_source == "executive" else "studio"
    if source == "executive":
        params = _json(_value(row, "payload", "payload_json", default={}), {})
        result = _json(_value(row, "result", "result_json", default={}), {})
        history: dict[str, Any] = {}
        capability = _value(row, "capabilityRequirements", "capability_requirements_json", default=[])
        capability = _json(capability, [])
        kind = _value(row, "type", default="")
        provider = _value(row, "provider", default=None)
        project_id = _value(row, "projectId", "project_id")
        timestamps = {
            "created_at": _timestamp(_value(row, "createdAt", "created_at")),
            "updated_at": _timestamp(_value(row, "updatedAt", "updated_at")),
            "started_at": _timestamp(_value(row, "startedAt", "started_at")),
            "completed_at": _timestamp(_value(row, "completedAt", "completed_at")),
        }
        error = _value(row, "errorMessage", "error_message")
    else:
        params = _json(_value(row, "params_json", default={}), {})
        history = _json(_value(row, "history_json", default={}), {})
        result = _json(_value(row, "preview_json", default={}), {})
        capability = []
        kind = _value(row, "kind", default="")
        provider = _first(history, "provider", "provider_id") if isinstance(history, Mapping) else None
        project_id = _value(row, "project_id")
        timestamps = {
            "created_at": _timestamp(_value(row, "created_at")),
            "updated_at": _timestamp(_value(row, "updated_at")),
            "started_at": None,
            "completed_at": None,
        }
        error = _value(row, "message", default=None) if _status(row) == "failed" else None

    params = _sanitize(params)
    result = _sanitize(result)
    history = _sanitize(history)
    if not isinstance(history, Mapping):
        history = {}
    input_ids = _first(params, "input_asset_ids", "inputAssetIds", "asset_ids", "assetIds") if isinstance(params, Mapping) else None
    output_ids = _first(result, "output_asset_ids", "outputAssetIds", "asset_ids", "assetIds") if isinstance(result, Mapping) else None
    progress = _value(row, "progress", default=None)
    has_fraction = isinstance(progress, (int, float)) and (progress > 0 or _status(row) == "completed")
    return {
        "job_id": _value(row, "id"),
        "project_id": project_id,
        "workspace_id": _first(params, "workspace_id", "workspaceId") if isinstance(params, Mapping) else None,
        "capability_id": _first(params, "capability_id", "capabilityId") if isinstance(params, Mapping) else kind,
        "provider": provider,
        "engine": _first(params, "engine", "engine_id", "engineId") if isinstance(params, Mapping) else None,
        "model": _first(params, "model", "model_id", "modelId") if isinstance(params, Mapping) else None,
        "operation": _first(params, "operation", "op") if isinstance(params, Mapping) else kind,
        "status": _status(row),
        "progress_mode": "fraction" if has_fraction else "state",
        "progress_value": float(progress) if has_fraction else None,
        "timestamps": timestamps,
        "provider_request_id": _first(history, "falRequestId", "fal_request_id", "request_id", "requestId"),
        "input_asset_ids": input_ids if isinstance(input_ids, list) else [],
        "output_asset_ids": output_ids if isinstance(output_ids, list) else [],
        "sanitized_parameters": params,
        "error_code": _first(history, "error_code", "errorCode", "code"),
        "sanitized_error": _sanitize(error),
        "cost_metadata": _sanitize(_first(history, "cost", "cost_metadata", "costMetadata")),
        "provenance": _sanitize(_first(history, "provenance", "source", "trace")),
        "approval_id": _first(params, "approval_id", "approvalId") if isinstance(params, Mapping) else None,
        "retry_parent_id": _first(params, "retry_parent_id", "retryParentId") if isinstance(params, Mapping) else None,
        "source": source,
    }
