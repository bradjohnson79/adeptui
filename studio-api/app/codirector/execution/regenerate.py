"""Targeted regeneration — submit a new job for a single child (spec §43).

Spec §43: "Regenerate only requested frame/assets. Keep rest of collection intact."
Spec §21: "Retry must submit a real targeted new job. Frame 1/2/4 remain unchanged.
Only failed/requested frame is regenerated."
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from .contracts import ChildJobStatus, ExecutionPlan, ExecutionStatus
from .pack_store import load_pack, save_pack

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def regenerate_child_job(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    child_index: int,
    user_instructions: str = "",
) -> Optional[ExecutionPlan]:
    """Regenerate a single child job by index.

    Submits a real new job via the capability handler and replaces the child in the
    pack. Sibling frames remain untouched (spec §43).
    """
    plan = load_pack(db, project_id, execution_id)
    if not plan:
        return None

    child = next((c for c in plan.child_jobs if c.child_index == child_index), None)
    if child is None:
        return None

    # Resolve the handler for this capability.
    capability_id = plan.capability
    if capability_id == "storyboard.generate":
        capability_id = "storyboard.regenerate_frame"

    from ..capabilities.registry import get_capability, HandlerKind
    cap = get_capability(capability_id)
    if cap is None or cap.handler_kind != HandlerKind.CAPABILITY_HANDLER:
        return None

    import importlib
    module_name = capability_id.replace(".", "_")
    module_path = f"app.codirector.capabilities.handlers.{module_name}"
    try:
        module = importlib.import_module(module_path)
        handle = module.handle
    except Exception as exc:
        logger.error("Failed to load regen handler %s: %s", module_path, exc)
        return None

    import inspect
    sig = inspect.signature(handle)
    accepted = set(sig.parameters.keys())

    meta = child.metadata or {}

    all_kwargs = {
        "db": db,
        "project_id": project_id,
        "execution_id": execution_id,
        "frame_index": child_index,
        "frame_metadata": meta,
        "reference_asset_id": (plan.attachment_asset_ids or [None])[0] if plan.attachment_asset_ids else None,
        "visual_style": "",
        "user_instructions": user_instructions,
    }
    handler_kwargs = {k: v for k, v in all_kwargs.items() if k in accepted}

    try:
        result = handle(**handler_kwargs)
    except Exception as exc:
        logger.exception("Regen handler %s failed", capability_id)
        # Mark the child as failed.
        child.status = ChildJobStatus.FAILED
        child.error = f"REGEN_ERROR: {exc}"
        save_pack(db, project_id, plan)
        return plan

    # Replace the child with the new job.
    new_children = result.get("child_jobs", [])
    if new_children:
        nc = new_children[0]
        child.job_id = nc.get("job_id", child.job_id)
        child.label = nc.get("label", child.label)
        child.status = ChildJobStatus(nc.get("status", "queued"))
        child.asset_id = nc.get("asset_id")
        child.error = nc.get("error")
        child.progress = 0.0
        child.stage = "queued"
        child.metadata = nc.get("metadata", meta)

    # Reset the pack to a non-terminal state so polling resumes.
    if plan.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
        plan.status = ExecutionStatus.RUNNING
    plan.recompute_progress()
    save_pack(db, project_id, plan)

    return plan
