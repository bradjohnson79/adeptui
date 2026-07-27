"""Storyteller specialist services: EmotionalSceneProfile + handoff."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import EmotionalSceneProfile, StorytellerHandoff
from .db import ensure_m214_tables
from .store import M214Store, _jid, _now


def analyze_scene(
    db: Session,
    *,
    project_id: str,
    scene_id: str = "",
    idea: str = "",
    mode: str = "guided",
) -> dict[str, Any]:
    ensure_m214_tables()
    if mode not in {"guided", "creative", "variation"}:
        mode = "guided"
    questions = [
        "What does the character want in this beat?",
        "What do they fear will happen if they fail?",
    ]
    if mode == "creative":
        questions.append("Should we lean poetic, grounded, or heightened?")
    if mode == "variation":
        questions.append("Which variation axis matters most: tone, stakes, or point of view?")
    questions = questions[:4]
    profile = EmotionalSceneProfile(
        project_id=project_id,
        scene_id=scene_id,
        emotional_arc="spark -> tension -> turn" if idea else "to be discovered",
        subtext="Unspoken need beneath dialogue",
        tone="intimate" if mode == "guided" else "exploratory",
        stakes="personal",
        character_beats=[{"beat": "want", "note": idea or "pending"}],
        unknowns=["location specificity", "time of day"] if mode == "guided" else [],
        questions=questions,
        mode=mode,
        honesty="mocked",
        payload={"sourceIdea": idea, "questionRule": "2-4 high-impact"},
    )
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_emotional_profiles "
            "(id, project_id, scene_id, version, profile_json, approved, created_at, updated_at) "
            "VALUES (:id, :pid, :sid, :ver, :j, 0, :ts, :ts)"
        ),
        {
            "id": profile.id,
            "pid": project_id,
            "sid": scene_id,
            "ver": profile.version,
            "j": _jid(profile.to_dict()),
            "ts": ts,
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="storyteller.scene.analyze",
        action="analyze",
        project_id=project_id,
        payload={"profileId": profile.id, "mode": mode},
    )
    return profile.to_dict()


def create_handoff(
    db: Session,
    *,
    project_id: str,
    profile_id: str,
    scene_id: str = "",
    direction_summary: str = "",
    format_guidance: str = "short scene",
) -> dict[str, Any]:
    ensure_m214_tables()
    handoff = StorytellerHandoff(
        project_id=project_id,
        scene_id=scene_id,
        profile_id=profile_id,
        direction_summary=direction_summary or "Pending user confirmation of emotional direction.",
        format_guidance=format_guidance,
        progressive_depth="medium",
        approved=False,
        payload={"approvalAware": True, "silentMutation": False},
    )
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_storyteller_handoffs "
            "(id, project_id, scene_id, version, handoff_json, approved, created_at, updated_at) "
            "VALUES (:id, :pid, :sid, :ver, :j, 0, :ts, :ts)"
        ),
        {
            "id": handoff.id,
            "pid": project_id,
            "sid": scene_id,
            "ver": handoff.version,
            "j": _jid(handoff.to_dict()),
            "ts": ts,
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="storyteller.handoff.create",
        action="create",
        project_id=project_id,
        payload={"handoffId": handoff.id},
    )
    return handoff.to_dict()


def approve_handoff(db: Session, handoff_id: str, *, actor: str = "user") -> dict[str, Any]:
    ensure_m214_tables()
    row = db.execute(
        text("SELECT handoff_json FROM m214_storyteller_handoffs WHERE id = :id"),
        {"id": handoff_id},
    ).fetchone()
    if not row:
        raise KeyError(handoff_id)
    import json

    data = json.loads(row[0] or "{}")
    data["approved"] = True
    data.setdefault("payload", {})["approvedBy"] = actor
    db.execute(
        text(
            "UPDATE m214_storyteller_handoffs SET approved = 1, handoff_json = :j, updated_at = :ts WHERE id = :id"
        ),
        {"j": _jid(data), "ts": _now(), "id": handoff_id},
    )
    db.commit()
    return data
