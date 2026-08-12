"""Read-through production state projection. Builds a ProductionState DTO from authoritative stores
for all 14 domains. Law 4: composes, never persists.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ...db import Project, Scene
from ..conversation.snapshot import load_snapshot
from .contracts import (
    ALLOWED_PROVENANCE,
    ProductionState,
    ProjectionDomain,
    ProvenanceField,
    ProvenanceTaxonomy,
)


def _now() -> datetime:
    return datetime.utcnow()


def _pf(
    value: Any,
    source: str,
    provenance: ProvenanceTaxonomy = "system-derived",
) -> ProvenanceField:
    return ProvenanceField(value=value, source=source, provenance=provenance, updated_at=_now())


def _build_project_domain(db: Session, project_id: str) -> dict[str, ProvenanceField] | None:
    project = db.get(Project, project_id)
    if not project:
        return None

    scenes = db.query(Scene).filter(Scene.project_id == project_id).all()
    runtime = sum(getattr(s, "duration_sec", 0) or 0 for s in scenes)

    # Phase CK — read project-level preferences from settings_json
    ss, vg = None, None
    try:
        raw = getattr(project, "settings_json", None)
        if isinstance(raw, str) and raw.strip():
            parsed = json.loads(raw)
            ss = parsed.get("storyboardStyle")
            vg = parsed.get("preferredVideoGenerator")
        elif isinstance(raw, dict):
            ss = raw.get("storyboardStyle")
            vg = raw.get("preferredVideoGenerator")
    except Exception:
        pass

    fields = {
        "title": _pf(project.name, "projects.name", "creator-stated"),
        "format": _pf(project.primary_project_type, "projects.primary_project_type", "creator-stated"),
        "fps": _pf(project.fps, "projects.fps", "creator-stated"),
        "runtime": _pf(runtime, "scenes.duration_sec (sum)", "system-derived"),
    }
    if ss:
        fields["storyboardStyle"] = _pf(ss, "settings_json.storyboardStyle", "creator-stated")
    if vg:
        fields["preferredVideoGenerator"] = _pf(vg, "settings_json.preferredVideoGenerator", "creator-stated")
    return fields


def _build_lifecycle_domain(db: Session, project_id: str) -> dict[str, ProvenanceField]:
    try:
        snapshot = load_snapshot(db, project_id)
        lifecycle = getattr(snapshot, "productionLifecycle", None) or {}
        current_stage = lifecycle.get("currentStage", "STORY") if isinstance(lifecycle, dict) else "STORY"
    except Exception:
        current_stage = "STORY"

    return {
        "currentStage": _pf(current_stage, "snapshot.productionLifecycle.currentStage", "system-derived"),
    }


def _placeholder_domain(domain: ProjectionDomain, primary_key: str, note: str) -> dict[str, ProvenanceField]:
    return {
        primary_key: _pf(
            value=None,
            source=note,
            provenance="system-derived",
        ),
    }


def build_production_state(db: Session, project_id: str) -> ProductionState:
    """Compose a ProductionState projection from authoritative stores.

    Reads the 14 domains defined in §2.1. PROJECT and PRODUCTION_LIFECYCLE are
    populated from their authoritative sources; the remaining 12 domains receive
    placeholder entries indicating the store they will read from in later phases.
    """
    try:
        project_fields = _build_project_domain(db, project_id)
        if project_fields is None:
            return ProductionState(generated_at=_now())

        domains: dict[ProjectionDomain, dict[str, ProvenanceField]] = {
            ProjectionDomain.PROJECT: project_fields,
            ProjectionDomain.PRODUCTION_LIFECYCLE: _build_lifecycle_domain(db, project_id),
            ProjectionDomain.CHARACTERS: _placeholder_domain(
                ProjectionDomain.CHARACTERS,
                "characters",
                "character_profiles + character_versions (not yet composed)",
            ),
            ProjectionDomain.LOCATIONS: _placeholder_domain(
                ProjectionDomain.LOCATIONS,
                "locations",
                "production_bible_entities entity_type=location (not yet composed)",
            ),
            ProjectionDomain.SCRIPT: _placeholder_domain(
                ProjectionDomain.SCRIPT,
                "script",
                "script_documents_v2 + draft_status (not yet composed)",
            ),
            ProjectionDomain.SCENES: _placeholder_domain(
                ProjectionDomain.SCENES,
                "scenes",
                "scenes table (not yet composed)",
            ),
            ProjectionDomain.PRODUCTION_BIBLE: _placeholder_domain(
                ProjectionDomain.PRODUCTION_BIBLE,
                "productionBible",
                "production_bible_versions + entities + facts (not yet composed)",
            ),
            ProjectionDomain.WIKI: _placeholder_domain(
                ProjectionDomain.WIKI,
                "wiki",
                "knowledgeEntries in settings_json projectIntelligence (not yet composed)",
            ),
            ProjectionDomain.DECISIONS: _placeholder_domain(
                ProjectionDomain.DECISIONS,
                "decisions",
                "m211_decision_records + codirector_approvals (not yet composed)",
            ),
            ProjectionDomain.TIMELINE: _placeholder_domain(
                ProjectionDomain.TIMELINE,
                "timeline",
                "scenes.director_json.timelineMaster + MAGI sequence (not yet composed)",
            ),
            ProjectionDomain.IMAGE_PLANNING: _placeholder_domain(
                ProjectionDomain.IMAGE_PLANNING,
                "imagePlans",
                "data/image_pipeline/{project}/plans/*.json (not yet composed)",
            ),
            ProjectionDomain.MULTI_SHOT: _placeholder_domain(
                ProjectionDomain.MULTI_SHOT,
                "multiShot",
                "multi_shot_plans + multi_shots + candidates (not yet composed)",
            ),
            ProjectionDomain.MAGI_READINESS: _placeholder_domain(
                ProjectionDomain.MAGI_READINESS,
                "magiReadiness",
                "magi/readiness.py readiness payload + gates (not yet composed)",
            ),
            ProjectionDomain.SESSION_CONTEXT: _placeholder_domain(
                ProjectionDomain.SESSION_CONTEXT,
                "sessionContext",
                "session_context: ephemeral, never persisted (not yet composed)",
            ),
        }

        return ProductionState(
            domains=domains,
            evidenceTrace=[],
            generated_at=_now(),
        )

    except Exception:
        return ProductionState(generated_at=_now())
