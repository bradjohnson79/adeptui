"""Wave D — Co-Director memory export / import bundle."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..db import CoDirectorConversationEvent, Project
from .conversation.snapshot import load_snapshot
from .conversation_events import EventInput, append_events, conversation_to_dict, current_revision, fold_events


def _loads_json(value: str, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return default


def _event_row_to_dict(row: CoDirectorConversationEvent) -> dict[str, Any]:
    attachments = _loads_json(row.attachments_json or "[]", [])
    return {
        "sequence": row.sequence,
        "event_type": row.event_type,
        "role": row.role,
        "message_id": row.message_id,
        "client_request_id": row.client_request_id,
        "content": row.content or "",
        "message_type": row.message_type,
        "status": row.status,
        "attachments": attachments if isinstance(attachments, list) else [],
        "tool_id": row.tool_id,
        "tool_arguments": _loads_json(row.tool_arguments_json or "", None),
        "tool_result": _loads_json(row.tool_result_json or "", None),
        "request_id": row.request_id,
        "actor": row.actor,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def export_memory(db: Session, project_id: str) -> dict[str, Any]:
    """Bundle conversation, revision, wiki, intelligence, and learning for one project."""

    folded_messages = fold_events(db, project_id)
    raw_rows = (
        db.query(CoDirectorConversationEvent)
        .filter(CoDirectorConversationEvent.project_id == project_id)
        .order_by(CoDirectorConversationEvent.sequence.asc())
        .all()
    )
    raw_events = [_event_row_to_dict(r) for r in raw_rows]

    wiki: dict[str, Any] | None = None
    try:
        from .wiki import build_project_wiki

        wiki = build_project_wiki(db, project_id)
    except Exception:
        wiki = None

    project = db.get(Project, project_id)
    settings = _loads_json(getattr(project, "settings_json", "") or "{}", {}) if project else {}
    project_intelligence = settings.get("projectIntelligence") if isinstance(settings, dict) else None

    learning_json: str | None = None
    if project is not None:
        raw_learning = getattr(project, "learning_json", "") or ""
        learning_json = raw_learning if raw_learning.strip() else None

    snapshot = load_snapshot(db, project_id)

    return {
        "projectId": project_id,
        "revision": current_revision(db, project_id),
        "conversation": {
            "messages": folded_messages,
            "rawEvents": raw_events,
        },
        "wiki": wiki,
        "projectIntelligence": project_intelligence,
        "intelligenceSnapshot": snapshot.model_dump(mode="json"),
        "learning_json": learning_json,
    }


def import_memory(db: Session, project_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    """Merge conversation events by message_id; restore learning/intelligence for this project only."""

    convo = bundle.get("conversation") if isinstance(bundle.get("conversation"), dict) else {}
    raw_events = convo.get("rawEvents") or bundle.get("rawEvents") or []
    if not isinstance(raw_events, list):
        raw_events = []

    inputs: list[EventInput] = []
    for ev in raw_events:
        if not isinstance(ev, dict):
            continue
        inputs.append(
            EventInput(
                role=str(ev.get("role") or "user"),
                content=str(ev.get("content") or ""),
                event_type=str(ev.get("event_type") or "message"),
                message_id=ev.get("message_id"),
                client_request_id=ev.get("client_request_id"),
                message_type=ev.get("message_type"),
                status=ev.get("status"),
                attachments=ev.get("attachments") if isinstance(ev.get("attachments"), list) else [],
                tool_id=ev.get("tool_id"),
                tool_arguments=ev.get("tool_arguments") if isinstance(ev.get("tool_arguments"), dict) else None,
                tool_result=ev.get("tool_result") if isinstance(ev.get("tool_result"), dict) else None,
                request_id=ev.get("request_id"),
                actor=str(ev.get("actor") or "user"),
            )
        )

    batch = append_events(db, project_id, inputs) if inputs else None

    project = db.get(Project, project_id)
    restored: list[str] = []
    if project is not None:
        if bundle.get("learning_json"):
            project.learning_json = str(bundle["learning_json"])
            restored.append("learning_json")
        elif isinstance(bundle.get("learning"), str) and bundle["learning"].strip():
            project.learning_json = bundle["learning"]
            restored.append("learning_json")

        intel = bundle.get("projectIntelligence")
        if isinstance(intel, dict):
            settings = _loads_json(project.settings_json or "{}", {})
            if not isinstance(settings, dict):
                settings = {}
            settings["projectIntelligence"] = intel
            project.settings_json = json.dumps(settings, ensure_ascii=False)
            restored.append("projectIntelligence")

        db.add(project)
        db.commit()

    from ..db import CoDirectorConversation

    header = db.get(CoDirectorConversation, project_id)
    convo_dict = conversation_to_dict(db, header) if header else None

    return {
        "projectId": project_id,
        "appendedCount": batch.appended_count if batch else 0,
        "duplicateCount": batch.duplicate_count if batch else 0,
        "revision": batch.revision if batch else current_revision(db, project_id),
        "restored": restored,
        "conversation": convo_dict,
    }


__all__ = ["export_memory", "import_memory"]
