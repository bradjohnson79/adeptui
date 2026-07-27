"""Sound Producer specialist: SonicConcept; coordinates music/sound designer (no new providers)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import SonicConcept
from .db import ensure_m214_tables
from .honesty import default_honesty, unbound_note
from .store import M214Store, _jid, _now


def create_sonic_concept(
    db: Session,
    *,
    project_id: str,
    scene_id: str = "",
    emotional_arc: str = "",
    mode: str = "guided",
) -> dict[str, Any]:
    ensure_m214_tables()
    if mode not in {"guided", "creative", "variation"}:
        mode = "guided"
    concept = SonicConcept(
        project_id=project_id,
        scene_id=scene_id,
        score_brief=f"Score supports arc: {emotional_arc or 'pending discovery'}",
        ambience="Sparse room tone; lean into silence before the turn",
        cues=["enter: soft pad", "turn: low pulse", "exit: residual tone"],
        dialogue_plan="Keep dialogue forward; SFX duck under key lines",
        mix_intent="Intimate close perspective; music under dialogue",
        mode=mode,
        honesty=default_honesty(),
        payload={
            "coordinatesWith": ["music-supervisor", "sound-designer"],
            "noNewProviders": True,
            "questionRule": "2-4 high-impact",
            "note": unbound_note("Sound Producer"),
        },
    )
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_sonic_concepts "
            "(id, project_id, scene_id, version, concept_json, approved, created_at, updated_at) "
            "VALUES (:id, :pid, :sid, :ver, :j, 0, :ts, :ts)"
        ),
        {
            "id": concept.id,
            "pid": project_id,
            "sid": scene_id,
            "ver": concept.version,
            "j": _jid(concept.to_dict()),
            "ts": ts,
        },
    )
    db.commit()
    for cap in (
        "sound_producer.concept.create",
        "sound_producer.score_brief.create",
        "sound_producer.ambience.plan",
        "sound_producer.cue.plan",
        "sound_producer.dialogue.plan",
        "sound_producer.mix_intent.create",
    ):
        M214Store.log_capability(db, capability_id=cap, action="create", project_id=project_id, payload={"id": concept.id})
    return concept.to_dict()


def approve_sonic_concept(db: Session, concept_id: str, *, actor: str = "user") -> dict[str, Any]:
    ensure_m214_tables()
    row = db.execute(
        text("SELECT concept_json FROM m214_sonic_concepts WHERE id = :id"),
        {"id": concept_id},
    ).fetchone()
    if not row:
        raise KeyError(concept_id)
    data = json.loads(row[0] or "{}")
    data["approved"] = True
    data.setdefault("payload", {})["approvedBy"] = actor
    db.execute(
        text("UPDATE m214_sonic_concepts SET approved = 1, concept_json = :j, updated_at = :ts WHERE id = :id"),
        {"j": _jid(data), "ts": _now(), "id": concept_id},
    )
    db.commit()
    return data
