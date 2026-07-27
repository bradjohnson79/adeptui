"""SpecialistMessage bus — extends M2.11; does not fork orchestration runtime."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import SpecialistMessage
from .db import ensure_m214_tables
from .honesty import default_honesty
from .store import M214Store, _jid, _now

# Required exchanges from plan
REQUIRED_EXCHANGES: tuple[tuple[str, str], ...] = (
    ("storyteller", "sound-producer"),
    ("sound-producer", "storyteller"),
    ("sound-producer", "cinematographer"),
    ("sound-producer", "editor"),
    ("virtual-production-coordinator", "storyteller"),
    ("virtual-production-coordinator", "sound-producer"),
    ("virtual-production-coordinator", "cinematographer"),
    ("continuity-analyst", "storyteller"),
    ("continuity-analyst", "sound-producer"),
    ("continuity-analyst", "cinematographer"),
)


def send_message(
    db: Session,
    *,
    project_id: str,
    from_specialist: str,
    to_specialist: str,
    body: str,
    scene_id: str = "",
    kind: str = "note",
    requires_response: bool = False,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    msg = SpecialistMessage(
        project_id=project_id,
        scene_id=scene_id,
        from_specialist=from_specialist,
        to_specialist=to_specialist,
        kind=kind,
        body=body,
        requires_response=requires_response,
        payload=payload or {},
    )
    db.execute(
        text(
            "INSERT INTO m214_specialist_messages "
            "(id, project_id, scene_id, from_specialist, to_specialist, kind, body, "
            "requires_response, responded, payload_json, created_at) "
            "VALUES (:id, :pid, :sid, :frm, :to, :kind, :body, :req, 0, :payload, :ts)"
        ),
        {
            "id": msg.id,
            "pid": project_id,
            "sid": scene_id,
            "frm": from_specialist,
            "to": to_specialist,
            "kind": kind,
            "body": body,
            "req": 1 if requires_response else 0,
            "payload": _jid(msg.payload),
            "ts": _now(),
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="production_team.message.send",
        action="send",
        project_id=project_id,
        payload={"messageId": msg.id, "from": from_specialist, "to": to_specialist},
    )
    return msg.to_dict()


def list_messages(db: Session, project_id: str) -> list[dict[str, Any]]:
    ensure_m214_tables()
    rows = db.execute(
        text(
            "SELECT id, from_specialist, to_specialist, kind, body, requires_response, responded, payload_json "
            "FROM m214_specialist_messages WHERE project_id = :pid ORDER BY created_at"
        ),
        {"pid": project_id},
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r[0],
                "from_specialist": r[1],
                "to_specialist": r[2],
                "kind": r[3],
                "body": r[4],
                "requires_response": bool(r[5]),
                "responded": bool(r[6]),
                "payload": json.loads(r[7] or "{}"),
            }
        )
    return out


def ensure_required_exchanges(db: Session, project_id: str, scene_id: str = "") -> list[dict[str, Any]]:
    """Seed required department exchanges if missing (honest scaffolds)."""
    existing = {(m["from_specialist"], m["to_specialist"]) for m in list_messages(db, project_id)}
    created: list[dict[str, Any]] = []
    for frm, to in REQUIRED_EXCHANGES:
        if (frm, to) in existing:
            continue
        created.append(
            send_message(
                db,
                project_id=project_id,
                scene_id=scene_id,
                from_specialist=frm,
                to_specialist=to,
                body=f"Required exchange scaffold: {frm} -> {to}",
                kind="handoff",
                requires_response=True,
                payload={"required": True, "honesty": default_honesty()},
            )
        )
    return created
