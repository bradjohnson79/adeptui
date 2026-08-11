"""Foundation status computation across the four project pillars.

Each pillar query is wrapped defensively so that a missing table, missing
module, or partial install never crashes the API. A pillar that cannot be
inspected is reported as ``not_started`` with ``exists=False``.

Pillar detection rules
----------------------
- Story: ``story_documents`` row for the project. Complete when word_count > 0.
- Script: ``script_documents_v2`` rows for the project. Complete when any
  document has at least one element.
- Storyboard: ``storyboard_studio`` documents on disk OR legacy
  ``storyboard_panels`` rows. Complete when at least one panel exists.
- Characters: ``character_profiles`` rows for the project. Complete when at
  least one profile exists.

``ready_for_timeline`` is True when either Story or Script is complete — the
timeline can operate with an incomplete foundation.

Note: Storyboard is still computed by ``_storyboard_pillar`` and surfaced on the
response as informational metadata (consumed by Co-Director generation), but it
is no longer treated as a creator-facing foundation pillar: it is excluded from
``missing_pillars`` and the user-facing foundation status bar. The standalone
StoryboardStudio workspace remains accessible via its deep-link.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .schemas import FoundationStatus, PillarInfo, PillarStatus

logger = logging.getLogger(__name__)


def _empty() -> PillarInfo:
    return PillarInfo(status="not_started", exists=False, last_updated=None, item_count=0)


def _info(status: PillarStatus, *, exists: bool, last_updated: str | None, item_count: int) -> PillarInfo:
    return PillarInfo(
        status=status,
        exists=exists,
        last_updated=last_updated,
        item_count=item_count,
    )


def _story_pillar(db: Session, project_id: str) -> PillarInfo:
    try:
        from ..story_entries.store import list_entries, migrate_from_legacy

        migrate_from_legacy(db, project_id)
        rows = list_entries(db, project_id)
        if not rows:
            return _empty()
        exists = True
        item_count = len(rows)
        has_content = any(
            bool(getattr(r, "title", "") or "")
            or bool(getattr(r, "logline", "") or "")
            or bool(getattr(r, "short_summary", "") or "")
            or bool(getattr(r, "long_summary", "") or "")
            for r in rows
        )
        status: PillarStatus = "complete" if has_content else "in_progress"
        last_updated = None
        for r in rows:
            updated = getattr(r, "updated_at", None)
            if updated is not None and hasattr(updated, "isoformat"):
                updated_str = updated.isoformat()
            elif updated:
                updated_str = str(updated)
            else:
                continue
            if last_updated is None or updated_str > last_updated:
                last_updated = updated_str
        return _info(status, exists=exists, last_updated=last_updated, item_count=item_count)
    except Exception:
        logger.exception("Foundation: story pillar inspection failed")
        return _empty()


def _script_pillar(db: Session, project_id: str) -> PillarInfo:
    try:
        from ..scriptwriter.store import list_documents

        docs = list_documents(db, project_id)
        if not docs:
            return _empty()
        element_count = 0
        last_updated: str | None = None
        for doc in docs:
            elements = getattr(doc, "elements", None) or []
            element_count += len(elements)
            updated = getattr(doc, "updatedAt", "") or ""
            if updated and (last_updated is None or updated > last_updated):
                last_updated = updated or None
        status: PillarStatus = "complete" if element_count > 0 else "in_progress"
        return _info(status, exists=True, last_updated=last_updated, item_count=element_count)
    except Exception:
        logger.exception("Foundation: script pillar inspection failed")
        return _empty()


def _storyboard_pillar(db: Session, project_id: str) -> PillarInfo:
    panel_count = 0
    last_updated: str | None = None
    found = False

    try:
        from ..storyboard_studio.documents import list_documents

        docs = list_documents(project_id)
        for doc in docs:
            found = True
            order = getattr(doc, "panelOrder", None) or []
            pages = getattr(doc, "pages", None) or []
            page_panel_ids = sum(len(getattr(p, "panelIds", None) or []) for p in pages)
            panel_count += max(len(order), page_panel_ids)
            updated = getattr(doc, "updatedAt", "") or ""
            if updated and (last_updated is None or updated > last_updated):
                last_updated = updated or None
    except Exception:
        logger.exception("Foundation: storyboard_studio documents inspection failed")

    if panel_count == 0:
        try:
            from ..script_storyboard import StoryboardPanelRow, ensure_script_tables

            ensure_script_tables()
            rows = (
                db.query(StoryboardPanelRow)
                .filter(StoryboardPanelRow.project_id == project_id)
                .all()
            )
            panel_count = len(rows)
            if rows:
                found = True
                updated_values: list[Any] = [
                    getattr(r, "updated_at", None) for r in rows if getattr(r, "updated_at", None)
                ]
                updated = max(updated_values) if updated_values else None
                if updated is not None and hasattr(updated, "isoformat"):
                    last_updated = updated.isoformat()
                elif updated:
                    last_updated = str(updated)
        except Exception:
            logger.exception("Foundation: legacy storyboard_panels inspection failed")

    if not found and panel_count == 0:
        return _empty()
    status: PillarStatus = "complete" if panel_count > 0 else "in_progress"
    return _info(status, exists=True, last_updated=last_updated, item_count=panel_count)


def _characters_pillar(db: Session, project_id: str) -> PillarInfo:
    try:
        from ..character_identity.service import list_profiles

        profiles = list_profiles(db, project_id)
        if not profiles:
            return _empty()
        count = len(profiles)
        last_updated: str | None = None
        for profile in profiles:
            updated = getattr(profile, "updated_at", "") or ""
            if updated and (last_updated is None or updated > last_updated):
                last_updated = updated or None
        status: PillarStatus = "complete" if count >= 1 else "in_progress"
        return _info(status, exists=True, last_updated=last_updated, item_count=count)
    except Exception:
        logger.exception("Foundation: characters pillar inspection failed")
        return _empty()


def get_foundation_status(db: Session, project_id: str) -> FoundationStatus:
    """Compute the current Foundation Status for ``project_id``.

    Every pillar is inspected independently and defensively. A failure in one
    pillar does not affect the others.
    """
    story = _story_pillar(db, project_id)
    script = _script_pillar(db, project_id)
    storyboard = _storyboard_pillar(db, project_id)
    characters = _characters_pillar(db, project_id)

    pillars: dict[str, PillarInfo] = {
        "story": story,
        "script": script,
        "storyboard": storyboard,
        "characters": characters,
    }
    # Storyboard remains available as informational metadata (used by
    # Co-Director generation), but is no longer a creator-facing foundation
    # pillar. `missing_pillars` only tracks the user-facing pillars:
    # story, script, characters.
    missing_pillars = [
        name
        for name, info in pillars.items()
        if name != "storyboard" and info.status == "not_started"
    ]
    ready_for_timeline = story.status == "complete" or script.status == "complete"

    return FoundationStatus(
        story=story,
        script=script,
        storyboard=storyboard,
        characters=characters,
        ready_for_timeline=ready_for_timeline,
        missing_pillars=missing_pillars,
    )


__all__ = ["get_foundation_status", "FoundationStatus", "PillarInfo"]
