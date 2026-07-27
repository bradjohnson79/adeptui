# -*- coding: utf-8 -*-
"""Emit M2.14 service modules + migration (UTF-8)."""
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


DB = r'''"""Ensure M2.14 tables exist (migration + runtime safety)."""
from __future__ import annotations

from sqlalchemy.engine import Engine

from ...db import engine as default_engine
from ...migrations import DEFAULT_REGISTRY, MigrationRunner

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


def ensure_m214_tables(engine: Engine | None = None) -> None:
    eng = engine or default_engine
    try:
        MigrationRunner(DEFAULT_REGISTRY, eng).apply_pending()
    except Exception:
        pass
    with eng.begin() as conn:
        for stmt in _DDL:
            conn.exec_driver_sql(stmt)
'''

STORE = r'''"""Persistence helpers for M2.14 unified experience."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m214_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _jid(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class M214Store:
    @staticmethod
    def log_capability(
        db: Session,
        *,
        capability_id: str,
        action: str,
        project_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        ensure_m214_tables()
        row_id = str(uuid4())
        db.execute(
            text(
                "INSERT INTO m214_capability_invokes "
                "(id, project_id, capability_id, action, payload_json, created_at) "
                "VALUES (:id, :pid, :cid, :action, :payload, :ts)"
            ),
            {
                "id": row_id,
                "pid": project_id,
                "cid": capability_id,
                "action": action,
                "payload": _jid(payload or {}),
                "ts": _now(),
            },
        )
        db.commit()
        return {"id": row_id, "capabilityId": capability_id, "action": action}

    @staticmethod
    def upsert_stage(db: Session, project_id: str, stage: str, extra: Optional[dict] = None) -> dict:
        ensure_m214_tables()
        ts = _now()
        row = db.execute(
            text("SELECT id FROM m214_project_stages WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        payload = {"stage": stage, **(extra or {})}
        if row:
            db.execute(
                text(
                    "UPDATE m214_project_stages SET stage = :stage, stage_json = :j, updated_at = :ts "
                    "WHERE project_id = :pid"
                ),
                {"stage": stage, "j": _jid(payload), "ts": ts, "pid": project_id},
            )
            row_id = row[0]
        else:
            row_id = str(uuid4())
            db.execute(
                text(
                    "INSERT INTO m214_project_stages (id, project_id, stage, stage_json, updated_at) "
                    "VALUES (:id, :pid, :stage, :j, :ts)"
                ),
                {"id": row_id, "pid": project_id, "stage": stage, "j": _jid(payload), "ts": ts},
            )
        db.commit()
        return {"id": row_id, "projectId": project_id, "stage": stage}

    @staticmethod
    def get_stage(db: Session, project_id: str) -> dict[str, Any]:
        ensure_m214_tables()
        row = db.execute(
            text("SELECT id, stage, stage_json FROM m214_project_stages WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if not row:
            return {"projectId": project_id, "stage": "idea", "payload": {}}
        return {
            "id": row[0],
            "projectId": project_id,
            "stage": row[1],
            "payload": json.loads(row[2] or "{}"),
        }

    @staticmethod
    def save_json_row(
        db: Session,
        table: str,
        columns: dict[str, Any],
    ) -> str:
        ensure_m214_tables()
        row_id = columns.get("id") or str(uuid4())
        columns = {**columns, "id": row_id}
        cols = ", ".join(columns.keys())
        binds = ", ".join(f":{k}" for k in columns)
        db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({binds})"), columns)
        db.commit()
        return row_id
'''

ATTACHMENTS = r'''"""Attachment classify / interpret / confirm (content-based, proposals until approved)."""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import AttachmentInterpretation
from .db import ensure_m214_tables
from .store import M214Store, _jid, _now

# Content signals (not filename alone)
_KIND_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("screenplay", (r"\bINT\.", r"\bEXT\.", r"FADE IN", r"CUT TO:", r"\bV\.O\.")),
    ("treatment", (r"\btreatment\b", r"\blogline\b", r"\bact\s+[i1]\b", r"\btheme\b")),
    ("storyboard", (r"\bstoryboard\b", r"\bpanel\s+\d+", r"\bframe\s+\d+")),
    ("sketch", (r"\bsketch\b", r"\bdoodle\b", r"\brough\b")),
    ("notes", (r"\bnotes?\b", r"\btodo\b", r"\bbeat\b")),
]


def _signals_from_text(text_body: str) -> list[str]:
    found: list[str] = []
    for kind, patterns in _KIND_PATTERNS:
        for pat in patterns:
            if re.search(pat, text_body, re.IGNORECASE):
                found.append(f"{kind}:{pat}")
    return found


def classify_content(
    *,
    text_body: str = "",
    mime_type: str = "",
    filename: str = "",
) -> tuple[str, float, list[str]]:
    """Classify by content signals; filename is a weak hint only."""
    signals = _signals_from_text(text_body or "")
    scores: dict[str, int] = {}
    for sig in signals:
        kind = sig.split(":", 1)[0]
        scores[kind] = scores.get(kind, 0) + 2
    # Weak filename hint (never sole authority)
    lower = (filename or "").lower()
    for kind, _ in _KIND_PATTERNS:
        if kind in lower:
            scores[kind] = scores.get(kind, 0) + 1
            signals.append(f"filename_hint:{kind}")
    if mime_type.startswith("image/") and "storyboard" not in scores:
        scores["reference_image"] = scores.get("reference_image", 0) + 1
        signals.append("mime:image")
    if mime_type.startswith("audio/"):
        scores["audio_reference"] = scores.get("audio_reference", 0) + 2
        signals.append("mime:audio")
    if mime_type.startswith("video/"):
        scores["video_reference"] = scores.get("video_reference", 0) + 2
        signals.append("mime:video")
    if not scores:
        return "unknown", 0.2, signals or ["no_content_signals"]
    best = max(scores.items(), key=lambda kv: kv[1])
    total = sum(scores.values())
    confidence = min(0.95, best[1] / max(total, 1))
    return best[0], confidence, signals


def interpret_attachment(
    db: Session,
    *,
    project_id: str,
    attachment_id: str,
    text_body: str = "",
    mime_type: str = "",
    filename: str = "",
) -> dict[str, Any]:
    ensure_m214_tables()
    kind, confidence, signals = classify_content(
        text_body=text_body, mime_type=mime_type, filename=filename
    )
    interp = AttachmentInterpretation(
        project_id=project_id,
        attachment_id=attachment_id,
        classified_kind=kind,
        confidence=confidence,
        summary=f"Proposed classification: {kind} (content-based; pending confirmation).",
        proposals=[
            {
                "action": "import_as",
                "kind": kind,
                "sections": ["summary", "beats"] if kind in {"treatment", "screenplay"} else ["media"],
            }
        ],
        status="proposed",
        content_signals=signals,
        honesty="mocked",
        payload={"filename": filename, "mimeType": mime_type, "secureExtractionOnly": True},
    )
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_attachment_interpretations "
            "(id, project_id, attachment_id, classified_kind, confidence, summary, status, payload_json, created_at, updated_at) "
            "VALUES (:id, :pid, :aid, :kind, :conf, :summary, :status, :payload, :ts, :ts)"
        ),
        {
            "id": interp.id,
            "pid": project_id,
            "aid": attachment_id,
            "kind": kind,
            "conf": confidence,
            "summary": interp.summary,
            "status": "proposed",
            "payload": _jid(interp.to_dict()),
            "ts": ts,
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="codirector.attachment.interpret",
        action="interpret",
        project_id=project_id,
        payload={"interpretationId": interp.id, "kind": kind},
    )
    return interp.to_dict()


def confirm_interpretation(
    db: Session,
    interpretation_id: str,
    *,
    decision: str,
    corrected_kind: Optional[str] = None,
    note: str = "",
) -> dict[str, Any]:
    """Approve / Correct / Provisional / Import sections / Merge / Cancel — proposals until approved."""
    ensure_m214_tables()
    allowed = {
        "approve": "approved",
        "correct": "corrected",
        "provisional": "provisional",
        "import_sections": "approved",
        "merge": "approved",
        "cancel": "cancelled",
    }
    if decision not in allowed:
        raise ValueError(f"Unknown decision {decision}")
    row = db.execute(
        text("SELECT payload_json FROM m214_attachment_interpretations WHERE id = :id"),
        {"id": interpretation_id},
    ).fetchone()
    if not row:
        raise KeyError(interpretation_id)
    data = json.loads(row[0] or "{}")
    status = allowed[decision]
    data["status"] = status
    if corrected_kind:
        data["classified_kind"] = corrected_kind
    data.setdefault("payload", {})["confirmationNote"] = note
    data.setdefault("payload", {})["decision"] = decision
    # Silent bible/timeline mutation forbidden — only store interpretation status.
    db.execute(
        text(
            "UPDATE m214_attachment_interpretations SET status = :status, classified_kind = :kind, "
            "payload_json = :payload, updated_at = :ts WHERE id = :id"
        ),
        {
            "status": status,
            "kind": data.get("classified_kind", "unknown"),
            "payload": _jid(data),
            "ts": _now(),
            "id": interpretation_id,
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="codirector.attachment.confirm",
        action=decision,
        project_id=data.get("project_id"),
        payload={"interpretationId": interpretation_id, "status": status},
    )
    return data
'''

IDEA_FIRST = r'''"""Idea-first Storyteller discovery + format guidance + progressive depth."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .kinds import PROJECT_STAGES
from .store import M214Store

_FORMAT_GUIDANCE = {
    "idea": "Capture the spark: who, where, emotional want. Defer format until direction emerges.",
    "discovery": "Guided discovery: 2-4 high-impact questions; propose format options without locking.",
    "treatment": "Shape a treatment: logline, tone, acts. Keep emotional arc first.",
    "screenplay": "Deepen into scene pages only after emotional direction is confirmed.",
    "previs": "Translate approved direction into visual/sonic previs cards.",
    "production": "Department brief sync; one primary next action for the user.",
    "post": "Review media, sound, and continuity against the UnifiedSceneBrief.",
    "delivery": "Final review checklist; no silent export without Approval Center.",
}


def propose_from_idea(
    db: Session,
    *,
    project_id: str,
    idea: str,
    preferred_format: str = "",
) -> dict[str, Any]:
    stage = "discovery"
    M214Store.upsert_stage(db, project_id, stage, {"idea": idea, "preferredFormat": preferred_format})
    questions = [
        "Whose emotional want drives this moment?",
        "What changes for them by the end of the scene?",
        "Should this feel intimate, epic, or somewhere between?",
    ]
    if preferred_format:
        questions.append(f"Confirm format '{preferred_format}' or explore alternatives?")
    else:
        questions.append("Do you want a short scene, treatment, or full short film?")
    M214Store.log_capability(
        db,
        capability_id="codirector.project.propose",
        action="idea_first",
        project_id=project_id,
        payload={"stage": stage},
    )
    return {
        "projectId": project_id,
        "stage": stage,
        "mode": "guided",
        "idea": idea,
        "formatGuidance": _FORMAT_GUIDANCE[stage],
        "progressiveDepth": "shallow",
        "questions": questions[:4],
        "honesty": "mocked",
        "note": "Proposals only until Storyteller handoff is approved.",
        "stages": list(PROJECT_STAGES),
    }


def advance_depth(db: Session, project_id: str, stage: str) -> dict[str, Any]:
    if stage not in PROJECT_STAGES:
        raise ValueError(f"Unknown stage {stage}")
    M214Store.upsert_stage(db, project_id, stage)
    depth = "shallow" if stage in {"idea", "discovery"} else "medium" if stage in {"treatment", "screenplay"} else "deep"
    return {
        "projectId": project_id,
        "stage": stage,
        "progressiveDepth": depth,
        "formatGuidance": _FORMAT_GUIDANCE.get(stage, ""),
        "honesty": "mocked",
    }
'''

STORYTELLER = r'''"""Storyteller specialist services: EmotionalSceneProfile + handoff."""
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
'''

SOUND = r'''"""Sound Producer specialist: SonicConcept; coordinates music/sound designer (no new providers)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import SonicConcept
from .db import ensure_m214_tables
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
        honesty="mocked",
        payload={
            "coordinatesWith": ["music-supervisor", "sound-designer"],
            "noNewProviders": True,
            "questionRule": "2-4 high-impact",
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
'''


def main() -> None:
    w(PKG / "db.py", DB)
    w(PKG / "store.py", STORE)
    w(PKG / "attachments.py", ATTACHMENTS)
    w(PKG / "idea_first.py", IDEA_FIRST)
    w(PKG / "storyteller.py", STORYTELLER)
    w(PKG / "sound_producer.py", SOUND)
    print("services emit complete")


if __name__ == "__main__":
    main()
