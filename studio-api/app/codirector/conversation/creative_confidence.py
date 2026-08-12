"""Lean Creative Confidence — longitudinal project patterns (Phase 1)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

_CONF_KEY = "creativeConfidence"


class CreativeConfidenceSnapshot(BaseModel):
    projectId: str
    strongestPatterns: list[str] = Field(default_factory=list)
    weakestPatterns: list[str] = Field(default_factory=list)
    recurringThemes: list[str] = Field(default_factory=list)
    originalIdeas: list[str] = Field(default_factory=list)
    creatorExcitementSignals: list[str] = Field(default_factory=list)
    evidenceTurnIds: list[str] = Field(default_factory=list)
    insightReady: bool = False
    revision: int = 1
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _settings(project: Any) -> dict[str, Any]:
    raw = getattr(project, "settings_json", None)
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def load_confidence(db: Session, project_id: str) -> CreativeConfidenceSnapshot | None:
    from app.db import Project

    project = db.get(Project, project_id)
    if not project:
        return None
    raw = _settings(project).get(_CONF_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return CreativeConfidenceSnapshot.model_validate(raw)
    except Exception:  # noqa: BLE001
        return None


def save_confidence(db: Session, snap: CreativeConfidenceSnapshot) -> None:
    from app.db import Project

    project = db.get(Project, snap.projectId)
    if not project:
        return
    settings = _settings(project)
    snap.updatedAt = datetime.now(timezone.utc).isoformat()
    settings[_CONF_KEY] = snap.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()


def _uniq_append(items: list[str], value: str, *, limit: int = 8) -> list[str]:
    v = value.strip()
    if not v:
        return items
    out = [x for x in items if x.lower() != v.lower()]
    out.insert(0, v[:160])
    return out[:limit]


def update_confidence_from_turn(
    db: Session,
    *,
    project_id: str,
    user_message: str,
    turn_id: str,
) -> CreativeConfidenceSnapshot | None:
    """Background only. Skip tiny acknowledgements."""
    text = (user_message or "").strip()
    if len(text.split()) < 28:
        return load_confidence(db, project_id)

    snap = load_confidence(db, project_id) or CreativeConfidenceSnapshot(projectId=project_id)
    snap.revision = int(snap.revision or 0) + 1
    snap.evidenceTurnIds = _uniq_append(snap.evidenceTurnIds, turn_id, limit=24)
    lower = text.lower()

    if re.search(r"\b(quiet|conversation|talk|whisper|listen)\b", lower):
        snap.strongestPatterns = _uniq_append(
            snap.strongestPatterns, "Quiet conversational scenes carry distinctive weight"
        )
    if re.search(r"\b(action|chase|explosion|battle)\b", lower):
        snap.weakestPatterns = _uniq_append(
            snap.weakestPatterns, "Large action set-pieces may be less central than intimate scenes"
        )
    if re.search(r"\b(memory|evidence|truth|testimony)\b", lower):
        snap.recurringThemes = _uniq_append(snap.recurringThemes, "Memory as contested truth / evidence")
    if re.search(r"\b(original|unlike|haven't seen|fresh)\b", lower):
        snap.originalIdeas = _uniq_append(snap.originalIdeas, text[:140])
    if re.search(r"\b(love|excited|this is it|favorite|can't wait)\b", lower):
        snap.creatorExcitementSignals = _uniq_append(snap.creatorExcitementSignals, text[:140])

    snap.insightReady = len(snap.evidenceTurnIds) >= 3 and (
        len(snap.strongestPatterns) + len(snap.recurringThemes) >= 2
    )
    save_confidence(db, snap)
    return snap


def confidence_insight(snap: CreativeConfidenceSnapshot | None) -> str | None:
    if snap is None or not snap.insightReady:
        return None
    if not snap.strongestPatterns:
        return None
    pattern = snap.strongestPatterns[0]
    theme = snap.recurringThemes[0] if snap.recurringThemes else None
    line = f"One pattern that keeps showing up: {pattern.rstrip('.')}."
    if theme:
        line += f" It connects to a recurring theme around {theme.rstrip('.')}."
    line += " That seems to be where this project becomes most distinctive."
    return line


def confidence_prompt_block(snap: CreativeConfidenceSnapshot | None) -> str:
    if snap is None:
        return ""
    lines = ["Creative confidence (compact, evidence-gated):"]
    if snap.strongestPatterns:
        lines.append("- Strongest: " + "; ".join(snap.strongestPatterns[:2]))
    if snap.recurringThemes:
        lines.append("- Themes: " + "; ".join(snap.recurringThemes[:2]))
    if snap.insightReady:
        lines.append("- Insight ready: yes (use sparingly, never as flattery)")
    return "\n".join(lines) if len(lines) > 1 else ""
