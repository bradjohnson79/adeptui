"""Result-aware conversation context — Workstream H, spec §42.

After an execution completes, Co-Director needs to know that phrases like
"number 3", "the second one", or "that frame" refer to Frame 3 / Frame 2 of
the current result set. This module builds a compact, project-isolated
context block from the most recent completed execution pack and exposes it
to the context enrichment path.

Contract:
    build_result_context(db, project_id, execution_id) -> dict

The returned dict is intentionally small and frontend-safe. It includes:
  - execution_id
  - capability (e.g. storyboard.generate)
  - result_asset_ids with child indices/labels
  - collection_id (when results are grouped)
  - status (so callers can detect partial completion)

Guarded imports: this module imports the Workstream C pack store lazily and
tolerates ImportError. When the pack store is absent, build_result_context
returns an empty dict (no context injected) — never raises.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def _pack_store_available() -> bool:
    try:
        import importlib

        mod = importlib.import_module("app.codirector.execution.pack_store")  # type: ignore
        return mod is not None
    except Exception:  # noqa: BLE001
        return False


def _get_execution_plan(db: Session, execution_id: str):
    if not execution_id:
        return None
    try:
        from .pack_store import get_execution  # type: ignore[attr-defined]

        return get_execution(db, execution_id)
    except Exception:  # noqa: BLE001
        return None


def _get_last_completed_execution(db: Session, project_id: str):
    if not project_id:
        return None
    try:
        from .pack_store import (  # type: ignore[attr-defined]
            get_last_completed_execution_for_project,
        )

        return get_last_completed_execution_for_project(db, project_id)
    except Exception:  # noqa: BLE001
        return None


def build_result_context(
    db: Session,
    project_id: str,
    execution_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build a result-aware context dict for the next conversation turn.

    When `execution_id` is provided, that specific execution is used. When it
    is omitted, the most recent completed execution for the project is used.

    Returns an empty dict when:
      - the pack store is unavailable (Workstream C not landed);
      - no execution can be resolved;
      - the resolved execution is not terminal (still running).

    This NEVER raises — context enrichment is best-effort.
    """
    if not project_id:
        return {}
    if not _pack_store_available():
        return {}

    plan = None
    if execution_id:
        plan = _get_execution_plan(db, execution_id)
    if plan is None:
        plan = _get_last_completed_execution(db, project_id)
    if plan is None:
        return {}

    # Only inject context for terminal executions. A running execution's
    # result set is incomplete and referencing "number 3" mid-flight would be
    # misleading.
    if not bool(getattr(plan, "is_terminal", False)):
        return {}

    child_jobs = list(getattr(plan, "child_jobs", []) or [])
    result_asset_ids = list(getattr(plan, "result_asset_ids", []) or [])

    # Build an index of child → asset/label so "number 3" can be resolved to
    # the third child's asset. Use child_index (Frame N) when present; fall
    # back to list position.
    indexed_results: list[dict[str, Any]] = []
    for i, child in enumerate(child_jobs):
        idx = getattr(child, "child_index", None)
        if idx is None:
            idx = i
        asset_id = getattr(child, "asset_id", None)
        if not asset_id:
            continue
        indexed_results.append(
            {
                "index": idx,
                "label": getattr(child, "label", "") or f"Item {idx + 1}",
                "asset_id": asset_id,
                "status": str(getattr(child, "status", "") or "").lower(),
            }
        )

    # If child jobs didn't carry asset_ids but result_asset_ids are present,
    # index those directly so the creator can still reference "number 3".
    if not indexed_results and result_asset_ids:
        for i, asset_id in enumerate(result_asset_ids):
            indexed_results.append(
                {
                    "index": i,
                    "label": f"Item {i + 1}",
                    "asset_id": asset_id,
                    "status": "completed",
                }
            )

    return {
        "execution_id": getattr(plan, "execution_id", "") or "",
        "capability": getattr(plan, "capability", "") or "",
        "status": str(getattr(plan, "status", "") or "").lower(),
        "collection_id": getattr(plan, "collection_id", None),
        "result_asset_ids": result_asset_ids,
        "indexed_results": indexed_results,
        "completed": int(getattr(plan, "completed_children", 0) or 0),
        "total": int(getattr(plan, "total_children", 0) or 0),
    }


def result_context_block(db: Session, project_id: str) -> str:
    """Return a short prompt block describing the most recent result set.

    Injected by context_enrichment.py into the next conversation turn so
    Co-Director can resolve "number 3" → Frame 3 of the current result set
    (spec §42). Empty string when no completed execution exists or the pack
    store is unavailable.
    """
    ctx = build_result_context(db, project_id)
    if not ctx:
        return ""
    capability = ctx.get("capability") or ""
    indexed = ctx.get("indexed_results") or []
    if not indexed:
        return ""
    lines: list[str] = []
    lines.append(
        "Recent execution result (creator may refer to these by number — "
        f"e.g. \"number 3\" means the third item below):"
    )
    if capability:
        lines.append(f"- Capability: {capability}")
    if ctx.get("collection_id"):
        lines.append(f"- Collection: {ctx['collection_id']}")
    for item in indexed[:12]:
        idx = item.get("index", 0)
        label = item.get("label", "")
        status = item.get("status", "")
        suffix = f" [{status}]" if status and status != "completed" else ""
        lines.append(f"  {idx + 1}. {label}{suffix}")
    if len(indexed) > 12:
        lines.append(f"  …and {len(indexed) - 12} more")
    return "\n".join(lines)
