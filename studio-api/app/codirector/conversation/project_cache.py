"""Compact revisioned Project Intelligence Cache — warm on open, section invalidation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

_CACHE_KEY = "projectIntelligenceCache"

CacheSection = Literal[
    "summary",
    "characters",
    "locations",
    "timeline",
    "principles",
    "deliverables",
    "decisions",
    "openQuestions",
    "production",
    "wiki",
]


def _project_settings(project: Any) -> dict[str, Any]:
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


class CompactEntitySummary(BaseModel):
    id: str
    name: str
    kind: str = "entity"
    note: str | None = None


class ProjectIntelligenceCache(BaseModel):
    projectId: str
    cacheVersion: int = 1
    projectSummary: str = ""
    developmentStage: str = "discovery"
    activeGoal: str | None = None
    activeSceneId: str | None = None
    characterIndex: list[CompactEntitySummary] = Field(default_factory=list)
    locationIndex: list[CompactEntitySummary] = Field(default_factory=list)
    timelineIndex: list[CompactEntitySummary] = Field(default_factory=list)
    storyPrinciples: list[CompactEntitySummary] = Field(default_factory=list)
    activeDeliverables: list[CompactEntitySummary] = Field(default_factory=list)
    recentDecisions: list[CompactEntitySummary] = Field(default_factory=list)
    openQuestions: list[CompactEntitySummary] = Field(default_factory=list)
    productionState: str = "idle"
    wikiRevision: int = 0
    bibleRevision: int = 0
    libraryRevision: int = 0
    timelineRevision: int = 0
    staleSections: list[str] = Field(default_factory=list)
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def load_project_cache(db: Session, project_id: str) -> ProjectIntelligenceCache | None:
    from app.db import Project

    project = db.get(Project, project_id)
    if not project:
        return None
    raw = _project_settings(project).get(_CACHE_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return ProjectIntelligenceCache.model_validate(raw)
    except Exception:  # noqa: BLE001
        return None


def save_project_cache(db: Session, cache: ProjectIntelligenceCache) -> None:
    from app.db import Project

    project = db.get(Project, cache.projectId)
    if not project:
        return
    settings = _project_settings(project)
    cache.updatedAt = datetime.now(timezone.utc).isoformat()
    settings[_CACHE_KEY] = cache.model_dump(mode="json")
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()


def invalidate_cache_sections(
    db: Session, project_id: str, sections: list[CacheSection] | list[str]
) -> ProjectIntelligenceCache | None:
    cache = load_project_cache(db, project_id)
    if cache is None:
        return None
    stale = set(cache.staleSections or [])
    for section in sections:
        stale.add(str(section))
    cache.staleSections = sorted(stale)
    cache.cacheVersion = int(cache.cacheVersion or 1) + 1
    save_project_cache(db, cache)
    return cache


def _fill_from_wiki_candidates(cache: ProjectIntelligenceCache, discovery: Any) -> None:
    chars: list[CompactEntitySummary] = []
    locs: list[CompactEntitySummary] = []
    principles: list[CompactEntitySummary] = []
    for c in list(getattr(discovery, "wiki_candidates", None) or [])[:40]:
        title = str(getattr(c, "title", None) or getattr(c, "id", "item"))[:80]
        cat = str(getattr(getattr(c, "category", None), "value", getattr(c, "category", "")) or "")
        note = str(getattr(c, "content", "") or "")[:120]
        entity = CompactEntitySummary(id=str(getattr(c, "id", title)), name=title, note=note or None)
        if cat in {"CHARACTER", "ENTITY"} and "character" in (cat + title).lower() or cat == "CHARACTER":
            chars.append(entity)
        elif cat in {"LOCATION", "WORLD_RULE"}:
            locs.append(entity)
        elif cat in {"THEME", "STORY_PRINCIPLE"}:
            principles.append(entity)
    if chars:
        cache.characterIndex = chars[:12]
    if locs:
        cache.locationIndex = locs[:12]
    if principles:
        cache.storyPrinciples = principles[:8]


def warm_project_cache(
    db: Session, project_id: str, *, force: bool = False, persist: bool = True
) -> ProjectIntelligenceCache:
    """Build or refresh compact cache. Prefer project-open warm; avoid pointless every-turn commits."""
    from .discovery.persistence import load_discovery_bundle
    from .snapshot import load_snapshot

    existing = load_project_cache(db, project_id)
    if existing and not force and not (existing.staleSections or []):
        # Hot path: reuse warm cache without rewrite.
        return existing

    snapshot = load_snapshot(db, project_id)
    discovery = load_discovery_bundle(db, project_id)
    cache = existing or ProjectIntelligenceCache(projectId=project_id)
    if snapshot is not None:
        cache.projectSummary = (
            getattr(snapshot, "summary", None) or getattr(snapshot, "title", None) or ""
        )[:400]
        cache.activeGoal = getattr(snapshot, "activeGoal", None)
        cache.developmentStage = str(getattr(snapshot, "creativeStage", None) or cache.developmentStage)
    cache.openQuestions = [
        CompactEntitySummary(id=q.id, name=q.question[:120], kind="question")
        for q in list(getattr(discovery, "discovery_questions", None) or [])[:8]
    ]
    cache.wikiRevision = len(list(getattr(discovery, "wiki_candidates", None) or []))
    _fill_from_wiki_candidates(cache, discovery)
    cache.staleSections = []
    if existing is None:
        cache.cacheVersion = 1
    else:
        cache.cacheVersion = int(existing.cacheVersion) + 1
    if persist:
        save_project_cache(db, cache)
    return cache


def cache_prompt_block(cache: ProjectIntelligenceCache | None) -> str:
    if cache is None:
        return ""
    lines = [
        "Compact project cache:",
        f"- Summary: {cache.projectSummary or '(none yet)'}",
        f"- Stage: {cache.developmentStage}",
        f"- Active goal: {cache.activeGoal or '(none)'}",
        f"- Wiki revision: {cache.wikiRevision}",
    ]
    if cache.characterIndex:
        lines.append("- Characters: " + ", ".join(c.name for c in cache.characterIndex[:5]))
    if cache.locationIndex:
        lines.append("- Locations: " + ", ".join(c.name for c in cache.locationIndex[:4]))
    if cache.openQuestions:
        lines.append("- Open questions: " + "; ".join(q.name for q in cache.openQuestions[:3]))
    return "\n".join(lines)
