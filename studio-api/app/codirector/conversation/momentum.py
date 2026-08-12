"""Conversation Momentum Engine — creative partner continuity across sessions."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

_MOMENTUM_KEY = "creativeMomentum"

CreativeEnergy = Literal["LOW", "STEADY", "HIGH"]


class CreativeMomentumState(BaseModel):
    projectId: str
    creativeEnergy: CreativeEnergy = "STEADY"
    currentObjective: str = "Continue discovering the project."
    openQuestion: str | None = None
    emotionalThread: str | None = None
    developmentStage: str = "discovery"
    nextNaturalTopic: str | None = None
    lastSessionSummary: str = ""
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    revision: int = 1


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


def load_momentum(db: Session, project_id: str) -> CreativeMomentumState | None:
    from app.db import Project

    project = db.get(Project, project_id)
    if not project:
        return None
    raw = _settings(project).get(_MOMENTUM_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return CreativeMomentumState.model_validate(raw)
    except Exception:  # noqa: BLE001
        return None


def save_momentum(db: Session, state: CreativeMomentumState) -> None:
    from app.db import Project

    project = db.get(Project, state.projectId)
    if not project:
        return
    settings = _settings(project)
    state.updatedAt = datetime.now(timezone.utc).isoformat()
    settings[_MOMENTUM_KEY] = state.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()


def _energy_for(message: str) -> CreativeEnergy:
    words = len((message or "").split())
    if words >= 80 or re.search(r"\b(excited|love|can't wait|breakthrough)\b", message or "", re.I):
        return "HIGH"
    if words < 12:
        return "LOW"
    return "STEADY"


def update_momentum_from_turn(
    db: Session,
    *,
    project_id: str,
    user_message: str,
    assistant_reply: str,
    development_stage: str | None = None,
) -> CreativeMomentumState:
    """Background update after streaming — never call on the TTFT critical path."""
    prior = load_momentum(db, project_id)
    state = prior or CreativeMomentumState(projectId=project_id)
    state.revision = int(state.revision or 0) + 1
    state.creativeEnergy = _energy_for(user_message)
    if development_stage:
        state.developmentStage = development_stage

    lower = (user_message or "").lower()
    # Objective: grounded snippet without mechanical "Continue developing:" prefix.
    snippet = " ".join((user_message or "").strip().split())[:160]
    if len(snippet) >= 24:
        state.currentObjective = snippet
    # Open question heuristic from assistant or user.
    q = None
    for text in (assistant_reply, user_message):
        m = re.search(r"([^.?!]{12,160}\?)", text or "")
        if m:
            q = m.group(1).strip()
            break
    state.openQuestion = q
    if re.search(r"\b(afraid|grief|lonely|hope|wonder|awe)\b", lower):
        state.emotionalThread = "Emotional stakes around belonging and truth."
    elif re.search(r"\b(memory|evidence|court|testimony)\b", lower):
        state.emotionalThread = "Tension between memory, evidence, and agency."
    else:
        state.emotionalThread = state.emotionalThread or "Creative curiosity and discovery."

    # Next natural topic — keep partner-like, not menu-like.
    if "encounter" in lower or "first meeting" in lower:
        state.nextNaturalTopic = "what that first encounter costs them personally"
    elif "character" in lower or re.search(r"\b(korri|kyung)\b", lower):
        state.nextNaturalTopic = "how the central character reacts next"
    elif "world" in lower or "rule" in lower:
        state.nextNaturalTopic = "how a world rule shows up in one concrete scene"
    else:
        state.nextNaturalTopic = state.nextNaturalTopic or "the next beat of the story thread"

    # Varied, grounded resume — never invent history; fingerprint to avoid identical repeats.
    variants = [
        "Last time, we were beginning to uncover {objective}.{q_clause}{topic_clause}",
        "When we left off, the thread was {objective}.{q_clause}{topic_clause}",
        "We had been sitting with {objective}.{q_clause}{topic_clause}",
    ]
    idx = int(state.revision or 1) % len(variants)
    q_clause = f" An open question remained: {state.openQuestion}." if state.openQuestion else ""
    topic_clause = (
        f" A natural place to return is {state.nextNaturalTopic}."
        if state.nextNaturalTopic
        else ""
    )
    objective = (state.currentObjective or "the story").rstrip(".")
    if len(objective) > 140:
        objective = objective[:137] + "…"
    summary = variants[idx].format(
        objective=objective,
        q_clause=q_clause,
        topic_clause=topic_clause,
    )
    # Prefer at most one open question OR topic, not both stacked heavily.
    if state.openQuestion and state.nextNaturalTopic and idx % 2 == 0:
        summary = variants[idx].format(
            objective=objective,
            q_clause=q_clause,
            topic_clause="",
        )
    state.lastSessionSummary = summary[:480]
    save_momentum(db, state)
    return state


def momentum_prompt_block(state: CreativeMomentumState | None) -> str:
    if state is None:
        return ""
    return "\n".join(
        [
            "Creative momentum (compact):",
            f"- Energy: {state.creativeEnergy}",
            f"- Objective: {state.currentObjective}",
            f"- Open question: {state.openQuestion or '(none)'}",
            f"- Emotional thread: {state.emotionalThread or '(none)'}",
            f"- Stage: {state.developmentStage}",
            f"- Next natural topic: {state.nextNaturalTopic or '(follow the creator)'}",
        ]
    )


def resume_greeting(state: CreativeMomentumState | None) -> str | None:
    if state is None or not (state.lastSessionSummary or "").strip():
        return None
    base = state.lastSessionSummary.strip()
    # Soft redirect invitation — vary closing so it never feels canned.
    closers = (
        "We can pick up there, or go somewhere else entirely.",
        "Happy to resume that thread — or follow whatever is on your mind now.",
        "Tell me if that still feels right, or redirect me.",
    )
    closer = closers[int(state.revision or 0) % len(closers)]
    return f"{base} {closer}"
