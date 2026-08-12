"""Bounded Wiki maintenance health + optional light cleanup."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...db import Project
from ..conversation.snapshot import load_snapshot
from ..wiki import build_project_wiki
from .classification import classify_entity_type, extract_display_name, is_false_character_name
from .reorganize import _detect_problems


def wiki_health_report(db: Session, project_id: str) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found"}
    snapshot = load_snapshot(db, project_id)
    entries = list(snapshot.knowledgeEntries or [])
    problems = _detect_problems(entries)
    incomplete = 0
    for e in entries:
        text = (e.text or "").strip()
        if len(text) < 24:
            incomplete += 1
    false_chars = sum(
        1
        for e in entries
        if e.section == "characters" and is_false_character_name(extract_display_name(e.text or ""))
    )
    wiki = build_project_wiki(db, project_id)
    return {
        "ok": True,
        "projectId": project_id,
        "recordsReviewed": len(entries),
        "duplicatesOrAliases": sum(1 for p in problems if p.problemType == "duplicate_character"),
        "conflictsFound": sum(1 for p in problems if p.severity in {"warning", "error"}),
        "incompleteProfiles": incomplete,
        "invalidCharacterFragments": false_chars,
        "unlinkedAssets": 0,
        "pendingCreatorConfirmations": sum(1 for p in problems if p.problemType == "duplicate_character"),
        "wikiHasContent": bool(wiki.get("hasContent")),
        "tocCount": len(wiki.get("toc") or []),
        "problems": [p.model_dump(mode="json") for p in problems[:40]],
        "recommendation": (
            "Run Reorganize Wiki"
            if problems or false_chars
            else "Wiki appears well organized"
        ),
    }


def tool_wiki_context(db: Session, project_id: str, *, domains: list[str] | None = None) -> dict[str, Any]:
    """Approved Wiki context for image/video/script/audio tools — project-scoped."""
    wiki = build_project_wiki(db, project_id)
    sections = wiki.get("sections") or {}
    wanted = set(domains or ["characters", "worldAndSetting", "visualIdentity", "creativeFoundation"])
    context: dict[str, list[str]] = {}
    for key, section in sections.items():
        if key not in wanted and key not in {"characters", "worldAndSetting", "visualIdentity"}:
            continue
        lines = []
        for entry in (section.get("entries") or [])[:12]:
            state = str(entry.get("state") or "")
            if state in {"rejected", "superseded"}:
                continue
            text = str(entry.get("text") or "").strip()
            if not text:
                continue
            et = classify_entity_type(text, hinted_section=key)
            if key == "characters" and is_false_character_name(extract_display_name(text)):
                continue
            lines.append(f"[{et}/{state}] {text[:220]}")
        if lines:
            context[key] = lines
    return {
        "ok": True,
        "projectId": project_id,
        "title": wiki.get("title"),
        "context": context,
        "sourceOfTruth": wiki.get("sourceOfTruth"),
        "professionalToc": wiki.get("professionalToc") or [],
    }


def run_wiki_maintenance(db: Session, project_id: str, *, apply_light_cleanup: bool = False) -> dict[str, Any]:
    """Bounded non-blocking maintenance: health scan + optional light reorganize for aliases."""
    health = wiki_health_report(db, project_id)
    applied = False
    reorg: dict[str, Any] | None = None
    if apply_light_cleanup and (
        health.get("invalidCharacterFragments")
        or health.get("duplicatesOrAliases")
        or (health.get("problems") or [])
    ):
        from .reorganize import start_wiki_reorganization

        reorg = start_wiki_reorganization(
            db,
            project_id,
            domains=["characters", "locations", "world", "canon", "timeline"],
            use_specialists=True,
            preserve_locked_canon=True,
            create_undo_snapshot=True,
        )
        applied = bool(reorg.get("ok"))
        health = wiki_health_report(db, project_id)
    return {
        "ok": True,
        "projectId": project_id,
        "health": health,
        "lightCleanupApplied": applied,
        "reorganization": reorg,
        "lockedCanonPreserved": True,
    }


def compact_tool_wiki_lines(db: Session, project_id: str, *, limit: int = 16) -> list[str]:
    """Flat lines for compilers that cannot consume the full tool-context payload."""
    payload = tool_wiki_context(db, project_id)
    lines: list[str] = []
    for key, bucket in (payload.get("context") or {}).items():
        for item in bucket:
            lines.append(f"{key}: {item}")
            if len(lines) >= limit:
                return lines
    return lines
