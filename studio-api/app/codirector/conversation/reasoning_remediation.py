"""Project-safe remediation of persisted assistant messages that leaked internal reasoning."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ...db import CoDirectorConversation, CoDirectorConversationEvent, Project
from ..creator_response_gate import is_contaminated, separate_leaked_reasoning

logger = logging.getLogger("adept.codirector.reasoning_remediation")


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def remediate_project_reasoning_leaks(db: Session, project_id: str) -> dict[str, Any]:
    """Scan assistant messages; quarantine leaked reasoning; preserve creator-facing text."""
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found", "projectId": project_id}

    scanned = 0
    remediated = 0
    quarantined_full = 0
    revisions: list[dict[str, Any]] = []

    # 1) Event log (authoritative live path)
    rows = (
        db.query(CoDirectorConversationEvent)
        .filter(
            CoDirectorConversationEvent.project_id == project_id,
            CoDirectorConversationEvent.role == "assistant",
        )
        .order_by(CoDirectorConversationEvent.sequence.asc())
        .all()
    )
    for row in rows:
        scanned += 1
        content = str(getattr(row, "content", "") or "")
        if not is_contaminated(content):
            continue
        creator, internal = separate_leaked_reasoning(content)
        audit = {
            "remediatedAt": _utcnow(),
            "originalLength": len(content),
            "action": "redact" if creator else "quarantine",
            "quarantinedPreview": ((internal or content)[:240]),
        }
        if creator:
            row.content = creator
            remediated += 1
        else:
            # Preserve message slot with honest placeholder — do not delete.
            row.content = (
                "[This reply was repaired because it contained internal drafting notes. "
                "Ask me to continue and I’ll answer clearly.]"
            )
            quarantined_full += 1
            remediated += 1
        # Store quarantine preview on attachments_json sidecar (no payload_json column).
        try:
            attachments = json.loads(getattr(row, "attachments_json", "") or "[]")
        except Exception:
            attachments = []
        if not isinstance(attachments, list):
            attachments = []
        attachments.append({"kind": "reasoning_remediation", **audit})
        row.attachments_json = json.dumps(attachments[-8:])
        revisions.append(
            {
                "messageId": getattr(row, "message_id", None) or getattr(row, "id", None),
                "sequence": getattr(row, "sequence", None),
                "action": audit["action"],
            }
        )

    # 2) Legacy messages_json if present
    header = db.get(CoDirectorConversation, project_id)
    if header and header.messages_json:
        try:
            messages = json.loads(header.messages_json or "[]")
        except Exception:
            messages = []
        if isinstance(messages, list):
            changed = False
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                if str(msg.get("role") or "").lower() != "assistant":
                    continue
                scanned += 1
                content = str(msg.get("content") or "")
                if not is_contaminated(content):
                    continue
                creator, internal = separate_leaked_reasoning(content)
                if creator:
                    msg["content"] = creator
                    msg["quarantinedReasoning"] = (internal or "")[:8000]
                else:
                    msg["content"] = (
                        "[This reply was repaired because it contained internal drafting notes. "
                        "Ask me to continue and I’ll answer clearly.]"
                    )
                    msg["quarantinedReasoning"] = content[:8000]
                msg["reasoningRemediatedAt"] = _utcnow()
                remediated += 1
                changed = True
                revisions.append({"messageId": msg.get("id"), "action": "legacy_redact"})
            if changed:
                header.messages_json = json.dumps(messages)

    # Persist remediation audit on project settings
    try:
        settings = json.loads(getattr(project, "settings_json", "") or "{}")
    except Exception:
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    audit_log = settings.get("reasoningRemediationAudit")
    if not isinstance(audit_log, list):
        audit_log = []
    entry = {
        "at": _utcnow(),
        "scanned": scanned,
        "remediated": remediated,
        "quarantinedFull": quarantined_full,
        "revisions": revisions[:100],
        "gate": "EXISTING_REASONING_LEAK_REMEDIATED",
    }
    audit_log.append(entry)
    settings["reasoningRemediationAudit"] = audit_log[-20:]
    project.settings_json = json.dumps(settings)
    db.commit()

    logger.info(
        "reasoning_remediation projectId=%s scanned=%s remediated=%s",
        project_id,
        scanned,
        remediated,
    )
    return {
        "ok": True,
        "projectId": project_id,
        "scanned": scanned,
        "remediated": remediated,
        "quarantinedFull": quarantined_full,
        "revisions": revisions,
        "gate": "EXISTING_REASONING_LEAK_REMEDIATED",
        "pass": True,
    }
