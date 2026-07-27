"""Project terminology / canon protection."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session

from ...db import Project

TranslationPolicy = Literal[
    "PRESERVE", "TRANSLATE_APPROVED", "TRANSLITERATE", "LOCALIZE", "ASK_USER"
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_settings(project: Project) -> dict[str, Any]:
    try:
        return json.loads(project.settings_json or "{}")
    except Exception:
        return {}


def _save_settings(db: Session, project: Project, settings: dict[str, Any]) -> None:
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()


def list_glossary(db: Session, project_id: str) -> list[dict[str, Any]]:
    project = db.get(Project, project_id)
    if not project:
        return []
    settings = _load_settings(project)
    lang = settings.get("language") or {}
    return list(lang.get("glossary") or [])


def upsert_glossary_term(
    db: Session,
    project_id: str,
    *,
    canonical_term: str,
    source_language: str = "en",
    translations: Optional[dict[str, Optional[str]]] = None,
    translation_policy: TranslationPolicy = "PRESERVE",
    case_sensitive: bool = True,
    notes: str = "",
    term_id: Optional[str] = None,
) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("PROJECT_NOT_FOUND")
    settings = _load_settings(project)
    lang = settings.setdefault("language", {})
    glossary: list[dict[str, Any]] = list(lang.get("glossary") or [])
    tid = term_id or f"term_{uuid.uuid4().hex[:10]}"
    entry = {
        "termId": tid,
        "canonicalTerm": canonical_term,
        "sourceLanguage": source_language,
        "translations": translations or {},
        "translationPolicy": translation_policy,
        "caseSensitive": case_sensitive,
        "notes": notes,
        "updatedAt": _now(),
    }
    replaced = False
    for i, row in enumerate(glossary):
        if row.get("termId") == tid or (
            row.get("canonicalTerm") == canonical_term and row.get("sourceLanguage") == source_language
        ):
            glossary[i] = {**row, **entry, "termId": row.get("termId") or tid}
            entry = glossary[i]
            replaced = True
            break
    if not replaced:
        glossary.append(entry)
    lang["glossary"] = glossary
    settings["language"] = lang
    _save_settings(db, project, settings)
    return entry


def apply_glossary_protection(text: str, glossary: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Mark PRESERVE terms; returns text unchanged and list of protected terms found."""
    protected: list[str] = []
    for row in glossary:
        if row.get("translationPolicy") != "PRESERVE":
            continue
        term = row.get("canonicalTerm") or ""
        if not term:
            continue
        if row.get("caseSensitive", True):
            found = term in text
        else:
            found = term.lower() in text.lower()
        if found:
            protected.append(term)
    return text, protected


# Platform-default protected Adept terms
PLATFORM_PROTECTED_TERMS = [
    "Dreamweaver",
    "Chroma",
    "Life Vital",
    "Starcasters",
    "Handari",
    "Co-Director",
    "Production Bible",
]
