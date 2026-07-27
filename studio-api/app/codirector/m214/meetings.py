"""Production meetings -> concise synthesis for user."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import ProductionMeeting
from .db import ensure_m214_tables
from .messaging import list_messages
from .store import M214Store, _jid, _now


def convene_meeting(
    db: Session,
    *,
    project_id: str,
    topic: str,
    scene_id: str = "",
    participants: Optional[list[str]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    parts = participants or [
        "storyteller",
        "sound-producer",
        "cinematographer",
        "editor",
        "virtual-production-coordinator",
        "continuity-analyst",
    ]
    msgs = list_messages(db, project_id)
    exchanges = [
        {"from": m["from_specialist"], "to": m["to_specialist"], "body": m["body"]}
        for m in msgs
        if m["from_specialist"] in parts or m["to_specialist"] in parts
    ][-12:]
    synthesis_lines = [
        f"- {e['from']} -> {e['to']}: {e['body'][:120]}" for e in exchanges[:6]
    ]
    synthesis = "Department synthesis:\n" + ("\n".join(synthesis_lines) if synthesis_lines else "- No exchanges yet")
    primary = "Approve Storyteller handoff" if not exchanges else "Review conflict synthesis and confirm next action"
    meeting = ProductionMeeting(
        project_id=project_id,
        scene_id=scene_id,
        topic=topic,
        participants=parts,
        exchanges=exchanges,
        synthesis=synthesis,
        primary_next_action=primary,
        payload={"honesty": "mocked", "userFacing": True},
    )
    db.execute(
        text(
            "INSERT INTO m214_production_meetings "
            "(id, project_id, scene_id, topic, meeting_json, created_at) "
            "VALUES (:id, :pid, :sid, :topic, :j, :ts)"
        ),
        {
            "id": meeting.id,
            "pid": project_id,
            "sid": scene_id,
            "topic": topic,
            "j": _jid(meeting.to_dict()),
            "ts": _now(),
        },
    )
    db.commit()
    M214Store.log_capability(
        db, capability_id="production_team.meeting.convene", action="convene", project_id=project_id
    )
    M214Store.log_capability(
        db, capability_id="production_team.meeting.synthesize", action="synthesize", project_id=project_id
    )
    return meeting.to_dict()
