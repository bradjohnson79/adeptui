"""Langfuse observation. Failure here never changes the turn."""

from __future__ import annotations

import logging
import os
from typing import Any

from .redact import redact

logger = logging.getLogger(__name__)


def emit_trace(
    *,
    workflow_id: str,
    project_id: str,
    scene_id: str | None,
    model: str,
    prompt_version: str,
    user_text: str,
    tool_ids: list[str],
    receipts: list[dict[str, Any]],
    reply: str,
    failure: str | None,
) -> str:
    """Return a trace id. Missing Langfuse yields a local id and does not raise."""

    local_id = f"local:{workflow_id}"
    if not os.environ.get("LANGFUSE_PUBLIC_KEY") or not os.environ.get("LANGFUSE_SECRET_KEY"):
        return local_id
    try:
        from langfuse import Langfuse

        client = Langfuse()
        with client.start_as_current_observation(
            name="codirector_turn",
            as_type="span",
            input=redact({"user": user_text, "tools": tool_ids}),
            metadata=redact(
                {
                    "workflowId": workflow_id,
                    "projectId": project_id,
                    "sceneId": scene_id,
                    "model": model,
                    "promptVersion": prompt_version,
                    "failure": failure,
                    "receipts": receipts,
                }
            ),
        ) as span:
            span.update(output=redact({"reply": reply}))
            trace_id = getattr(span, "trace_id", None) or local_id
        client.flush()
        return str(trace_id)
    except Exception:
        logger.warning("Langfuse trace failed open for workflow %s", workflow_id, exc_info=True)
        return local_id
