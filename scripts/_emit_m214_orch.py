# -*- coding: utf-8 -*-
"""Emit M2.14 orchestration + media + approvals (UTF-8)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "studio-api" / "app" / "codirector" / "m214"
MIG = ROOT / "studio-api" / "app" / "migrations"


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


MESSAGING = r'''"""SpecialistMessage bus — extends M2.11; does not fork orchestration runtime."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import SpecialistMessage
from .db import ensure_m214_tables
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
                payload={"required": True, "honesty": "mocked"},
            )
        )
    return created
'''

BRIEF = r'''"""UnifiedSceneBrief revision sync."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import UnifiedSceneBrief
from .db import ensure_m214_tables
from .store import M214Store, _jid, _now


def upsert_brief(
    db: Session,
    *,
    project_id: str,
    scene_id: str = "",
    title: str = "",
    logline: str = "",
    emotional_profile_id: Optional[str] = None,
    sonic_concept_id: Optional[str] = None,
    storyteller_handoff_id: Optional[str] = None,
    primary_next_action: str = "",
    departments: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    row = db.execute(
        text("SELECT id, revision, brief_json FROM m214_unified_briefs WHERE project_id = :pid ORDER BY revision DESC"),
        {"pid": project_id},
    ).fetchone()
    revision = (row[1] + 1) if row else 1
    prev = json.loads(row[2]) if row else {}
    brief = UnifiedSceneBrief(
        id=str(__import__("uuid").uuid4()) if not row else str(__import__("uuid").uuid4()),
        project_id=project_id,
        scene_id=scene_id or prev.get("scene_id", ""),
        revision=revision,
        title=title or prev.get("title", "Untitled scene"),
        logline=logline or prev.get("logline", ""),
        emotional_profile_id=emotional_profile_id or prev.get("emotional_profile_id"),
        sonic_concept_id=sonic_concept_id or prev.get("sonic_concept_id"),
        storyteller_handoff_id=storyteller_handoff_id or prev.get("storyteller_handoff_id"),
        departments=departments or prev.get("departments") or {},
        primary_next_action=primary_next_action
        or prev.get("primary_next_action")
        or "Confirm Storyteller direction",
        approved_keys=list(prev.get("approved_keys") or []),
        payload={"extendsM211": True, "forkedRuntime": False},
    )
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_unified_briefs "
            "(id, project_id, scene_id, revision, brief_json, created_at, updated_at) "
            "VALUES (:id, :pid, :sid, :rev, :j, :ts, :ts)"
        ),
        {
            "id": brief.id,
            "pid": project_id,
            "sid": brief.scene_id,
            "rev": revision,
            "j": _jid(brief.to_dict()),
            "ts": ts,
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="production_team.brief.update",
        action="upsert",
        project_id=project_id,
        payload={"briefId": brief.id, "revision": revision},
    )
    return brief.to_dict()


def get_latest_brief(db: Session, project_id: str) -> dict[str, Any] | None:
    ensure_m214_tables()
    row = db.execute(
        text(
            "SELECT brief_json FROM m214_unified_briefs WHERE project_id = :pid ORDER BY revision DESC LIMIT 1"
        ),
        {"pid": project_id},
    ).fetchone()
    if not row:
        return None
    return json.loads(row[0] or "{}")
'''

MEETINGS = r'''"""Production meetings -> concise synthesis for user."""
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
'''

CONFLICTS = r'''"""Conflict classify + synthesize; DecisionImpact + revision propagation."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import ProductionDecisionImpact
from .db import ensure_m214_tables
from .store import M214Store, _jid, _now


def detect_conflicts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for m in messages:
        body = (m.get("body") or "").lower()
        if m.get("kind") == "conflict" or "conflict" in body or "disagree" in body:
            conflicts.append(
                {
                    "id": m.get("id"),
                    "classification": "departmental",
                    "from": m.get("from_specialist"),
                    "to": m.get("to_specialist"),
                    "summary": m.get("body"),
                    "honesty": "mocked",
                }
            )
    return conflicts


def synthesize_conflicts(conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    if not conflicts:
        return {
            "hasConflicts": False,
            "synthesis": "No active conflicts.",
            "primaryNextAction": "Continue with primary next action on the UnifiedSceneBrief.",
        }
    lines = [f"- {c['from']} vs {c['to']}: {c['summary']}" for c in conflicts]
    return {
        "hasConflicts": True,
        "synthesis": "Conflicts require user direction:\n" + "\n".join(lines),
        "primaryNextAction": "Choose a conflict resolution in Approval Center",
        "conflicts": conflicts,
    }


def calculate_impact(
    db: Session,
    *,
    project_id: str,
    decision_id: str,
    decision_summary: str,
    scene_id: str = "",
    affected_departments: Optional[list[str]] = None,
    previously_approved: Optional[list[str]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    affected = affected_departments or ["storyteller", "sound-producer", "cinematographer"]
    approved = previously_approved or ["story", "bible"]
    # Preserve unaffected approvals
    revalidate = [d for d in affected if d not in {"continuity-analyst"}]
    preserved = [a for a in approved if a not in revalidate]
    impact = ProductionDecisionImpact(
        project_id=project_id,
        scene_id=scene_id,
        decision_id=decision_id,
        decision_summary=decision_summary,
        affected_departments=affected,
        revalidate_keys=revalidate,
        preserved_approvals=preserved,
        impact_summary=f"Decision impacts {', '.join(affected)}; preserved approvals: {', '.join(preserved) or 'none'}",
        payload={"silentMutation": False, "extendsM211Decisions": True},
    )
    db.execute(
        text(
            "INSERT INTO m214_decision_impacts "
            "(id, project_id, scene_id, decision_id, impact_json, created_at) "
            "VALUES (:id, :pid, :sid, :did, :j, :ts)"
        ),
        {
            "id": impact.id,
            "pid": project_id,
            "sid": scene_id,
            "did": decision_id,
            "j": _jid(impact.to_dict()),
            "ts": _now(),
        },
    )
    db.commit()
    M214Store.log_capability(
        db, capability_id="production_team.impact.calculate", action="calculate", project_id=project_id
    )
    M214Store.log_capability(
        db, capability_id="production_team.decision.propagate", action="propagate", project_id=project_id
    )
    M214Store.log_capability(
        db, capability_id="production_team.state.revalidate", action="revalidate", project_id=project_id
    )
    return impact.to_dict()
'''

MOTIFS = r'''"""Production motifs across visual / sonic / narrative."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import ProductionMotif
from .db import ensure_m214_tables
from .store import _jid, _now


def create_motif(
    db: Session,
    *,
    project_id: str,
    name: str,
    kind: str = "visual",
    description: str = "",
    scene_id: str = "",
    linked_media_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    motif = ProductionMotif(
        project_id=project_id,
        scene_id=scene_id,
        name=name,
        kind=kind,
        description=description,
        linked_media_ids=linked_media_ids or [],
    )
    db.execute(
        text(
            "INSERT INTO m214_production_motifs "
            "(id, project_id, scene_id, name, kind, motif_json, created_at) "
            "VALUES (:id, :pid, :sid, :name, :kind, :j, :ts)"
        ),
        {
            "id": motif.id,
            "pid": project_id,
            "sid": scene_id,
            "name": name,
            "kind": kind,
            "j": _jid(motif.to_dict()),
            "ts": _now(),
        },
    )
    db.commit()
    return motif.to_dict()
'''

MEDIA = r'''"""Media cards, grouping, contextual refs; M2.13 preview when available (no fake 3D)."""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m214_tables
from .store import M214Store, _jid, _now


def create_media_card(
    db: Session,
    *,
    project_id: str,
    kind: str,
    title: str,
    scene_id: str = "",
    group_key: str = "",
    honesty: str = "mocked",
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    if honesty not in {"mocked", "real", "fixture"}:
        honesty = "mocked"
    row_id = str(uuid4())
    media = {
        "id": row_id,
        "projectId": project_id,
        "sceneId": scene_id,
        "kind": kind,
        "title": title,
        "groupKey": group_key or kind,
        "honesty": honesty,
        "status": "draft",
        "payload": payload or {},
        "fake3d": False,
    }
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_media_cards "
            "(id, project_id, scene_id, kind, title, group_key, honesty, status, media_json, created_at, updated_at) "
            "VALUES (:id, :pid, :sid, :kind, :title, :gk, :hon, 'draft', :j, :ts, :ts)"
        ),
        {
            "id": row_id,
            "pid": project_id,
            "sid": scene_id,
            "kind": kind,
            "title": title,
            "gk": group_key or kind,
            "hon": honesty,
            "j": _jid(media),
            "ts": ts,
        },
    )
    db.commit()
    M214Store.log_capability(
        db, capability_id="codirector.media.list", action="create", project_id=project_id, payload={"id": row_id}
    )
    return media


def list_media(db: Session, project_id: str) -> list[dict[str, Any]]:
    ensure_m214_tables()
    rows = db.execute(
        text(
            "SELECT media_json FROM m214_media_cards WHERE project_id = :pid ORDER BY created_at"
        ),
        {"pid": project_id},
    ).fetchall()
    return [json.loads(r[0] or "{}") for r in rows]


def group_media(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = item.get("groupKey") or item.get("kind") or "other"
        groups.setdefault(key, []).append(item)
    return groups


_REF_PATTERNS = [
    (re.compile(r"\bsecond\s+image\b", re.I), "image", 1),
    (re.compile(r"\bfirst\s+image\b", re.I), "image", 0),
    (re.compile(r"\bnewest\s+video\b", re.I), "video", -1),
    (re.compile(r"\blatest\s+audio\b", re.I), "audio", -1),
    (re.compile(r"\benvironment\s+preview\b", re.I), "environment_preview", 0),
]


def resolve_contextual_ref(text_ref: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for pat, kind, idx in _REF_PATTERNS:
        if not pat.search(text_ref or ""):
            continue
        filtered = [i for i in items if i.get("kind") == kind]
        if not filtered:
            return None
        if idx == -1:
            return filtered[-1]
        if 0 <= idx < len(filtered):
            return filtered[idx]
    return None


def hitchhiker_smoke_media(db: Session, project_id: str) -> dict[str, Any]:
    """Create labeled mocked media for hitchhiker smoke test."""
    cards = [
        create_media_card(
            db,
            project_id=project_id,
            kind="image",
            title="Hitchhiker thumb — MOCKED",
            honesty="mocked",
            payload={"label": "MOCKED", "premise": "hitchhiker"},
        ),
        create_media_card(
            db,
            project_id=project_id,
            kind="video",
            title="Hitchhiker beat video — MOCKED",
            honesty="mocked",
            payload={"label": "MOCKED", "premise": "hitchhiker"},
        ),
        create_media_card(
            db,
            project_id=project_id,
            kind="audio",
            title="Road ambience bed — MOCKED",
            honesty="mocked",
            payload={"label": "MOCKED", "premise": "hitchhiker"},
        ),
        create_media_card(
            db,
            project_id=project_id,
            kind="storyboard",
            title="Hitchhiker panels — MOCKED",
            honesty="mocked",
            payload={"label": "MOCKED", "premise": "hitchhiker"},
        ),
        create_media_card(
            db,
            project_id=project_id,
            kind="environment_preview",
            title="M2.13 preview slot (no fake 3D)",
            honesty="fixture",
            payload={"m213PreviewIfAvailable": True, "fake3d": False, "label": "FIXTURE"},
        ),
    ]
    return {"projectId": project_id, "cards": cards, "honesty": "mocked", "fake3d": False}
'''

SESSION = r'''"""Session restore: project, scene, media, stage, approvals, blockers, next action."""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .brief import get_latest_brief
from .db import ensure_m214_tables
from .media import list_media
from .store import M214Store, _jid, _now


def save_snapshot(db: Session, project_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    ensure_m214_tables()
    row = db.execute(
        text("SELECT id FROM m214_session_snapshots WHERE project_id = :pid"),
        {"pid": project_id},
    ).fetchone()
    ts = _now()
    payload = {**snapshot, "projectId": project_id, "updatedAt": ts}
    if row:
        db.execute(
            text(
                "UPDATE m214_session_snapshots SET snapshot_json = :j, updated_at = :ts WHERE project_id = :pid"
            ),
            {"j": _jid(payload), "ts": ts, "pid": project_id},
        )
        row_id = row[0]
    else:
        row_id = str(uuid4())
        db.execute(
            text(
                "INSERT INTO m214_session_snapshots (id, project_id, snapshot_json, created_at, updated_at) "
                "VALUES (:id, :pid, :j, :ts, :ts)"
            ),
            {"id": row_id, "pid": project_id, "j": _jid(payload), "ts": ts},
        )
    db.commit()
    return {"id": row_id, "projectId": project_id}


def restore_session(db: Session, project_id: str) -> dict[str, Any]:
    ensure_m214_tables()
    stage = M214Store.get_stage(db, project_id)
    brief = get_latest_brief(db, project_id)
    media = list_media(db, project_id)
    row = db.execute(
        text("SELECT snapshot_json FROM m214_session_snapshots WHERE project_id = :pid"),
        {"pid": project_id},
    ).fetchone()
    snap = json.loads(row[0]) if row else {}
    M214Store.log_capability(
        db, capability_id="codirector.project.resume", action="restore", project_id=project_id
    )
    return {
        "projectId": project_id,
        "stage": stage,
        "brief": brief,
        "media": media,
        "approvals": snap.get("approvals") or {},
        "blockers": snap.get("blockers") or [],
        "primaryNextAction": (brief or {}).get("primary_next_action")
        or snap.get("primaryNextAction")
        or "Start idea-first discovery",
        "snapshot": snap,
        "m212FeedbackHooks": {
            "emitOnPreference": True,
            "autoSystemPromote": False,
        },
    }
'''

APPROVALS = r'''"""Unified Approval Center aggregation (story, bible, env, blocking, camera, lighting, media, timeline, export)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .store import M214Store


APPROVAL_CATEGORIES: tuple[str, ...] = (
    "story",
    "bible",
    "environment",
    "blocking",
    "camera",
    "lighting",
    "media",
    "timeline",
    "export",
)


def approval_center(
    db: Session,
    project_id: str,
    *,
    pending: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Aggregate pending approvals; does not silently approve anything."""
    items = []
    source = pending or {}
    for cat in APPROVAL_CATEGORIES:
        entry = source.get(cat) or {"status": "none", "items": []}
        items.append(
            {
                "category": cat,
                "status": entry.get("status", "none"),
                "items": entry.get("items") or [],
                "wires": {
                    "proposalCard": True,
                    "m211Decisions": True,
                    "m213Gates": cat in {"environment", "blocking", "camera", "lighting"},
                },
            }
        )
    M214Store.log_capability(
        db,
        capability_id="production_team.readiness.evaluate",
        action="approval_center",
        project_id=project_id,
    )
    pending_count = sum(1 for i in items if i["status"] in {"pending", "blocked"})
    return {
        "projectId": project_id,
        "categories": items,
        "pendingCount": pending_count,
        "primaryNextAction": "Review pending approvals" if pending_count else "No pending approvals",
        "silentApproval": False,
        "honesty": "scaffolded",
    }
'''

PLAN_UI = r'''"""Production-plan visualization (idea -> delivery stages)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .kinds import PROJECT_STAGES
from .store import M214Store


def production_plan_view(db: Session, project_id: str) -> dict[str, Any]:
    stage_info = M214Store.get_stage(db, project_id)
    current = stage_info.get("stage") or "idea"
    stages = []
    reached = True
    for s in PROJECT_STAGES:
        if s == current:
            status = "current"
            reached = False
        elif reached:
            status = "complete"
        else:
            status = "upcoming"
        stages.append({"id": s, "status": status})
    return {
        "projectId": project_id,
        "currentStage": current,
        "stages": stages,
        "path": "idea -> discovery -> treatment -> screenplay -> previs -> production -> post -> delivery",
        "honesty": "scaffolded",
    }
'''

MIGRATION = r'''"""M017: Co-Director M2.14 Unified Experience tables."""
from __future__ import annotations

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0017"
CHECKSUM_SOURCE = "M017:codirector-unified-experience:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS m214_attachment_interpretations (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        attachment_id VARCHAR(64) NOT NULL,
        classified_kind VARCHAR(64) NOT NULL DEFAULT 'unknown',
        confidence REAL NOT NULL DEFAULT 0,
        summary TEXT NOT NULL DEFAULT '',
        status VARCHAR(32) NOT NULL DEFAULT 'proposed',
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m214_attach_project ON m214_attachment_interpretations (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m214_emotional_profiles (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        version INTEGER NOT NULL DEFAULT 1,
        profile_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_storyteller_handoffs (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        version INTEGER NOT NULL DEFAULT 1,
        handoff_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_sonic_concepts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        version INTEGER NOT NULL DEFAULT 1,
        concept_json TEXT NOT NULL DEFAULT '{}',
        approved INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_specialist_messages (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        from_specialist VARCHAR(64) NOT NULL,
        to_specialist VARCHAR(64) NOT NULL,
        kind VARCHAR(32) NOT NULL DEFAULT 'note',
        body TEXT NOT NULL DEFAULT '',
        requires_response INTEGER NOT NULL DEFAULT 0,
        responded INTEGER NOT NULL DEFAULT 0,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m214_msg_project ON m214_specialist_messages (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m214_unified_briefs (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        revision INTEGER NOT NULL DEFAULT 1,
        brief_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_production_meetings (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        topic TEXT NOT NULL DEFAULT '',
        meeting_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_decision_impacts (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        decision_id VARCHAR(64),
        impact_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_production_motifs (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        name VARCHAR(128) NOT NULL DEFAULT '',
        kind VARCHAR(32) NOT NULL DEFAULT 'visual',
        motif_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_project_stages (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL UNIQUE,
        stage VARCHAR(32) NOT NULL DEFAULT 'idea',
        stage_json TEXT NOT NULL DEFAULT '{}',
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_media_cards (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        scene_id VARCHAR(64),
        kind VARCHAR(32) NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        group_key VARCHAR(64),
        honesty VARCHAR(16) NOT NULL DEFAULT 'mocked',
        status VARCHAR(32) NOT NULL DEFAULT 'draft',
        media_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_m214_media_project ON m214_media_cards (project_id)",
    """
    CREATE TABLE IF NOT EXISTS m214_session_snapshots (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS m214_capability_invokes (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36),
        capability_id VARCHAR(128) NOT NULL,
        action VARCHAR(64) NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL
    )
    """,
]


def apply(connection: Connection) -> None:
    for stmt in _DDL:
        connection.exec_driver_sql(stmt)


MIGRATION = Migration(
    revision=REVISION,
    description="Add M2.14 Co-Director Unified Experience tables",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes="Additive. Drop m214_* tables to reverse.",
    reversible=False,
)
'''


def main() -> None:
    w(PKG / "messaging.py", MESSAGING)
    w(PKG / "brief.py", BRIEF)
    w(PKG / "meetings.py", MEETINGS)
    w(PKG / "conflicts.py", CONFLICTS)
    w(PKG / "motifs.py", MOTIFS)
    w(PKG / "media.py", MEDIA)
    w(PKG / "session.py", SESSION)
    w(PKG / "approvals.py", APPROVALS)
    w(PKG / "plan_view.py", PLAN_UI)
    w(MIG / "m017_codirector_unified_experience.py", MIGRATION)
    print("orch emit complete")


if __name__ == "__main__":
    main()
