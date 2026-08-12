"""Canonical Wave 3 retrieval envelopes.

Handlers keep returning typed domain dicts. `execute_read` wraps those into
`RetrievalResult` so conversational + Project Content consumers share one shape
without forcing every internal caller to migrate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

DEFAULT_PAGE_LIMIT = 25
MAX_PAGE_LIMIT = 100

RetrievalStatus = Literal["success", "partial", "empty", "failed"]

SourceType = Literal[
    "project",
    "script",
    "scene",
    "character",
    "production_bible",
    "asset",
    "plan",
    "proposal",
    "job",
    "continuity",
    "workspace",
    "system",
]


class RetrievalEvidence(BaseModel):
    sourceType: SourceType
    sourceId: str
    sourceName: Optional[str] = None
    repository: str
    version: Optional[str] = None
    updatedAt: Optional[str] = None


class RetrievalWarning(BaseModel):
    code: str
    message: str
    section: Optional[str] = None


class RetrievalPagination(BaseModel):
    cursor: Optional[str] = None
    nextCursor: Optional[str] = None
    total: Optional[int] = None
    limit: int = DEFAULT_PAGE_LIMIT
    hasMore: bool = False
    appliedFilters: dict[str, Any] = Field(default_factory=dict)
    returnedCount: int = 0


class RetrievalResult(BaseModel):
    requestId: Optional[str] = None
    toolId: str
    toolVersion: str = "1"
    projectId: Optional[str] = None
    status: RetrievalStatus = "success"
    summary: str = ""
    data: Any = None
    evidence: list[RetrievalEvidence] = Field(default_factory=list)
    pagination: Optional[RetrievalPagination] = None
    warnings: list[RetrievalWarning] = Field(default_factory=list)
    retrievedAt: str = ""
    availableSections: list[str] = Field(default_factory=list)
    unavailableSections: list[str] = Field(default_factory=list)


def clamp_limit(raw: Any, *, default: int = DEFAULT_PAGE_LIMIT) -> int:
    try:
        n = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        n = default
    return max(1, min(MAX_PAGE_LIMIT, n))


def _infer_status(data: Any, warnings: list[RetrievalWarning]) -> RetrievalStatus:
    if warnings and any(w.code.endswith("_UNAVAILABLE") or w.code == "RETRIEVAL_PARTIAL" for w in warnings):
        if data in (None, {}, []):
            return "partial"
        return "partial"
    if data is None:
        return "empty"
    if isinstance(data, (list, tuple, set)) and len(data) == 0:
        return "empty"
    if isinstance(data, dict):
        # Common list payloads: {items: []}, {scenes: []}, {proposals: []}
        for key in ("items", "scenes", "scripts", "characters", "assets", "proposals", "jobs", "plans", "findings", "entries"):
            if key in data and isinstance(data[key], list) and len(data[key]) == 0 and len(data.keys()) <= 4:
                return "empty"
    return "success"


def _default_summary(tool_id: str, status: RetrievalStatus, data: Any) -> str:
    if status == "empty":
        return f"No records returned by `{tool_id}`."
    if status == "partial":
        return f"Partial retrieval from `{tool_id}` — some sources were unavailable."
    if status == "failed":
        return f"Retrieval failed for `{tool_id}`."
    if isinstance(data, list):
        return f"`{tool_id}` returned {len(data)} record(s)."
    if isinstance(data, dict):
        for key in ("items", "scenes", "scripts", "characters", "assets", "proposals", "jobs", "plans", "findings", "entries"):
            if isinstance(data.get(key), list):
                return f"`{tool_id}` returned {len(data[key])} {key}."
    return f"`{tool_id}` completed successfully."


def wrap_handler_result(
    *,
    tool_id: str,
    tool_version: str | int,
    project_id: Optional[str],
    request_id: Optional[str],
    raw: Any,
) -> dict[str, Any]:
    """Wrap a handler dict (or already-enveloped result) into the canonical shape."""

    raw_status = raw.get("status") if isinstance(raw, dict) else None
    if (
        isinstance(raw, dict)
        and isinstance(raw_status, str)
        and raw_status in {"success", "partial", "empty", "failed"}
        and "data" in raw
        and "toolId" in raw
    ):
        # Already an envelope — ensure retrievedAt/requestId.
        out = dict(raw)
        out.setdefault("requestId", request_id)
        out.setdefault("projectId", project_id)
        out.setdefault("toolVersion", str(tool_version))
        out.setdefault("retrievedAt", datetime.now(timezone.utc).isoformat())
        return out

    warnings: list[RetrievalWarning] = []
    evidence: list[RetrievalEvidence] = []
    pagination: Optional[RetrievalPagination] = None
    summary = ""
    data: Any = raw
    available: list[str] = []
    unavailable: list[str] = []

    if isinstance(raw, dict):
        if isinstance(raw.get("_warnings"), list):
            for w in raw["_warnings"]:
                if isinstance(w, dict) and w.get("code") and w.get("message"):
                    warnings.append(RetrievalWarning(**{k: w[k] for k in ("code", "message", "section") if k in w}))
        if isinstance(raw.get("_evidence"), list):
            for e in raw["_evidence"]:
                if isinstance(e, dict) and e.get("sourceType") and e.get("sourceId") and e.get("repository"):
                    evidence.append(RetrievalEvidence(**e))
        if isinstance(raw.get("_pagination"), dict):
            pagination = RetrievalPagination(**raw["_pagination"])
        summary = str(raw.get("_summary") or "")
        available = list(raw.get("_availableSections") or [])
        unavailable = list(raw.get("_unavailableSections") or [])
        # Domain payload: strip meta keys
        data = {k: v for k, v in raw.items() if not str(k).startswith("_")}
        if len(data) == 1 and "data" in data:
            data = data["data"]

    status = _infer_status(data, warnings)
    if unavailable and status == "success":
        status = "partial"
    if not summary:
        summary = _default_summary(tool_id, status, data)

    result = RetrievalResult(
        requestId=request_id,
        toolId=tool_id,
        toolVersion=str(tool_version),
        projectId=project_id,
        status=status,
        summary=summary,
        data=data,
        evidence=evidence,
        pagination=pagination,
        warnings=warnings,
        retrievedAt=datetime.now(timezone.utc).isoformat(),
        availableSections=available,
        unavailableSections=unavailable,
    )
    return result.model_dump(mode="json")
