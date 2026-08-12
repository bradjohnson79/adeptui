"""Undo a creator correction by restoring its pre-correction snapshot.

Reuses the same snapshot/restore mechanism as `undo_wiki_reorganization`.
Also deactivates the learned correction so the mistake can be re-learned later
if the creator re-applies it.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ....db import Project
from ...conversation.project_cache import invalidate_cache_sections, warm_project_cache
from ...wiki import build_project_wiki
from . import memory
from .apply import _KEY_REVISIONS, _save_settings, _settings


def undo_correction(db: Session, project_id: str, correction_id: str) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "project_not_found"}
    settings = _settings(project)
    revisions = settings.get(_KEY_REVISIONS) or []
    match = None
    for rev in reversed(revisions if isinstance(revisions, list) else []):
        if isinstance(rev, dict) and rev.get("correctionId") == correction_id:
            match = rev
            break
    if not match or not match.get("reversible"):
        return {"ok": False, "error": "revision_not_reversible"}
    snapshot = match.get("snapshot") or {}
    intel = snapshot.get("projectIntelligence")
    if not isinstance(intel, dict):
        return {"ok": False, "error": "snapshot_missing"}

    settings["projectIntelligence"] = intel
    settings["wikiRevision"] = int(match.get("previousWikiRevision") or 0)
    _save_settings(db, project, settings)

    # Deactivate the learned correction so it no longer influences extraction.
    learned_id = match.get("learnedCorrectionId")
    if learned_id:
        for c in memory.load_corrections(db, project_id):
            if c.id == learned_id:
                c.active = False
                memory.save_correction(db, c)
                break

    try:
        invalidate_cache_sections(db, project_id, sections=["wiki", "knowledge"])
        warm_project_cache(db, project_id)
    except Exception:  # noqa: BLE001
        pass

    wiki: dict[str, Any] = {}
    try:
        wiki = build_project_wiki(db, project_id)
    except Exception:  # noqa: BLE001
        # A full wiki rebuild is best-effort here; the snapshot restore above is
        # the authoritative undo. Never let a rebuild failure block the restore.
        wiki = {}

    return {
        "ok": True,
        "projectId": project_id,
        "correctionId": correction_id,
        "restoredRevision": match.get("previousWikiRevision"),
        "wiki": wiki,
    }


__all__ = ["undo_correction"]
