"""Snapshot load, save, and bootstrap helpers for conversation intelligence."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ...db import CoDirectorConversation, Project
from .schemas import ProjectDirectorState, ProjectIntelligenceSnapshot, WikiCandidate

_SETTINGS_KEY = "projectIntelligence"


def _loads_json(value: str, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return default


def _load_project_settings(project: Project) -> dict[str, Any]:
    data = _loads_json(getattr(project, "settings_json", "") or "{}", {})
    return data if isinstance(data, dict) else {}


def _load_conversation_messages(db: Session, project_id: str) -> list[dict[str, Any]]:
    row = db.get(CoDirectorConversation, project_id)
    if not row:
        return []
    data = _loads_json(row.messages_json or "[]", [])
    return data if isinstance(data, list) else []


def _truncate_message(message: dict[str, Any]) -> dict[str, Any]:
    content = str(message.get("content") or "").strip()
    if len(content) > 280:
        content = content[:277].rstrip() + "..."
    item = {
        "role": str(message.get("role") or "user"),
        "content": content,
    }
    if message.get("id"):
        item["id"] = str(message["id"])
    return item


def _fallback_snapshot(project_id: str) -> ProjectIntelligenceSnapshot:
    return ProjectIntelligenceSnapshot(
        projectId=project_id,
        title="Untitled Project",
        director=ProjectDirectorState(
            currentGoal="Name the project and define its creative direction.",
            currentTask="Open the conversation.",
            recommendedNextStep="Choose a project title or describe the story you want to create.",
            creativeStage="Project Creation",
            creativeSubstate="Naming",
            revision=0,
        ),
        currentStage="Project Creation",
        currentSubstate="Naming",
    )


def _section_entries(payload: dict[str, Any], section_name: str) -> list[dict[str, Any]]:
    sections = payload.get("sections") or {}
    section = sections.get(section_name) or {}
    entries = section.get("entries") or []
    return [entry for entry in entries if isinstance(entry, dict)]


def _text_list(entries: list[dict[str, Any]], *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for entry in entries:
        text = str(entry.get("text") or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _merge_unique(first: list[str], second: list[str], *, limit: int = 12) -> list[str]:
    out: list[str] = []
    for item in [*first, *second]:
        cleaned = str(item or "").strip()
        if cleaned and cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _wiki_candidates_from_wiki(payload: dict[str, Any]) -> list[WikiCandidate]:
    entries: list[WikiCandidate] = []
    sections = payload.get("sections") or {}
    for section_name, section in sections.items():
        rows = section.get("entries") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            state = str(row.get("state") or "reference-only")
            if state not in {
                "confirmed",
                "proposed",
                "unresolved",
                "approved",
                "rejected",
                "superseded",
                "reference-only",
            }:
                state = "reference-only"
            entries.append(
                WikiCandidate(
                    id=str(row.get("id") or f"{section_name}-{len(entries) + 1}"),
                    text=text,
                    state=state,
                    section=str(section_name),
                )
            )
    return entries


def load_snapshot(db: Session, project_id: str) -> ProjectIntelligenceSnapshot:
    """Load the stored project intelligence snapshot from project settings."""

    project = db.get(Project, project_id)
    if not project:
        return _fallback_snapshot(project_id)

    settings = _load_project_settings(project)
    payload = settings.get(_SETTINGS_KEY)
    if not isinstance(payload, dict):
        return _fallback_snapshot(project_id)

    try:
        snapshot = ProjectIntelligenceSnapshot.model_validate(payload)
    except Exception:
        return _fallback_snapshot(project_id)

    if not snapshot.projectId:
        snapshot.projectId = project_id
    if not snapshot.title:
        snapshot.title = project.name or "Untitled Project"
    if snapshot.director.creativeStage != (snapshot.currentStage or snapshot.director.creativeStage):
        snapshot.director.creativeStage = snapshot.currentStage or snapshot.director.creativeStage
        snapshot.director.creativeSubstate = snapshot.currentSubstate
    return snapshot


def save_snapshot(db: Session, snapshot: ProjectIntelligenceSnapshot) -> None:
    """Persist a snapshot into project.settings_json and increment its revision."""

    project = db.get(Project, snapshot.projectId)
    if not project:
        return

    settings = _load_project_settings(project)
    snapshot.revision += 1
    snapshot.director.revision = max(snapshot.director.revision, snapshot.revision)
    settings[_SETTINGS_KEY] = snapshot.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    if hasattr(db, "add"):
        db.add(project)
    if hasattr(db, "commit"):
        db.commit()
    if hasattr(db, "refresh"):
        try:
            db.refresh(project)
        except Exception:
            pass


def build_tier1_snapshot(
    db: Session,
    project_id: str,
    messages: list[dict[str, Any]],
) -> ProjectIntelligenceSnapshot:
    """Build a lightweight merged snapshot from project, wiki, conversation, and stored state."""

    project = db.get(Project, project_id)
    base = load_snapshot(db, project_id)
    if not project:
        return base

    conversation_messages = messages or _load_conversation_messages(db, project_id)
    recent_messages = [_truncate_message(item) for item in conversation_messages[-12:] if isinstance(item, dict)]

    title = (project.name or base.title or "Untitled Project").strip() or "Untitled Project"
    project_format = (getattr(project, "primary_project_type", "") or "").strip() or base.format
    objective = (getattr(project, "description", "") or "").strip() or base.currentObjective

    wiki_payload: dict[str, Any] = {}
    try:
        from ..wiki import build_project_wiki

        result = build_project_wiki(db, project_id)
        if isinstance(result, dict):
            wiki_payload = result
    except Exception:
        wiki_payload = {}

    known_details = _text_list(_section_entries(wiki_payload, "knownDetails"), limit=6)
    production_decisions = _text_list(_section_entries(wiki_payload, "productionDecisions"), limit=6)
    open_questions = _text_list(_section_entries(wiki_payload, "openQuestions"), limit=6)
    creative_foundation = _text_list(_section_entries(wiki_payload, "creativeFoundation"), limit=6)
    character_notes = _text_list(_section_entries(wiki_payload, "characters"), limit=6)
    story_notes = _text_list(_section_entries(wiki_payload, "storyAndEpisodes"), limit=6)

    key_characters = _merge_unique(base.keyCharacters, character_notes, limit=6)
    confirmed_facts = _merge_unique(base.confirmedFacts, known_details + production_decisions, limit=12)
    unresolved_ideas = _merge_unique(base.unresolvedIdeas, creative_foundation + story_notes, limit=10)
    questions = _merge_unique(base.openQuestions, open_questions, limit=8)

    wiki_knowledge = _wiki_candidates_from_wiki(wiki_payload)
    knowledge_entries = base.knowledgeEntries or wiki_knowledge

    snapshot = base.model_copy(deep=True)
    snapshot.title = title
    snapshot.format = project_format or None
    snapshot.currentObjective = objective or None
    snapshot.confirmedFacts = confirmed_facts
    snapshot.keyCharacters = key_characters
    snapshot.recentDecisions = _merge_unique(base.recentDecisions, production_decisions, limit=8)
    snapshot.openQuestions = questions
    snapshot.unresolvedIdeas = unresolved_ideas
    snapshot.currentStoryScope = base.currentStoryScope or story_notes[0] if story_notes else base.currentStoryScope
    snapshot.recentMessages = recent_messages
    snapshot.knowledgeEntries = knowledge_entries
    snapshot.director.creativeStage = snapshot.currentStage or snapshot.director.creativeStage
    snapshot.director.creativeSubstate = snapshot.currentSubstate or snapshot.director.creativeSubstate
    return snapshot
