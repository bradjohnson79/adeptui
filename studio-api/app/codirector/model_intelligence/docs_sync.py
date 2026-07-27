"""Documentation sync proposals — never auto-activate pack changes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional


def register_source(
    *,
    model_id: str,
    url: str,
    label: str = "",
    retrieved_at: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "modelId": model_id,
        "url": url,
        "label": label or url,
        "retrievedAt": retrieved_at or datetime.utcnow().isoformat() + "Z",
        "reviewedAt": None,
        "status": "registered",
    }


def propose_pack_update(
    *,
    model_id: str,
    current_version: str,
    proposed_version: str,
    diff_summary: str,
    source_urls: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Return a reviewable proposal. Does not write pack files."""
    return {
        "proposalId": str(uuid.uuid4()),
        "modelId": model_id,
        "currentVersion": current_version,
        "proposedVersion": proposed_version,
        "diffSummary": diff_summary[:4000],
        "sourceUrls": list(source_urls or []),
        "requiresReview": True,
        "autoActivate": False,
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "status": "PENDING_REVIEW",
        "note": "External documentation must not alter live provider behavior without validation and approval.",
    }


def sanitize_downloaded_doc(text: str) -> str:
    """Treat downloaded docs as untrusted — strip injection-looking patterns."""
    banned = ("!!python", "{{", "{%", "<script", "os.system", "subprocess")
    out = text or ""
    for token in banned:
        out = out.replace(token, "")
    return out[:20000]
