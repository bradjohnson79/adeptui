"""Stage evidence collector for the Production State Projection.

Law 4: read-only. Reads all 7 audited stage sources, maps candidate labels to
the authoritative STORY -> COMPLETE vocabulary, returns evidence trace.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ...db import Project
from ..m214.store import M214Store
from .contracts import ProductionState, StageEvidence

# ---------------------------------------------------------------------------
# Mapping tables — all keys .casefold() for case-insensitive lookup
# ---------------------------------------------------------------------------

_SNAPSHOT_CURRENT_STAGE_MAP: dict[str, str] = {
    "vision": "STORY",
    "premise": "STORY",
    "discovery": "STORY",
    "treatment": "SCRIPT",
    "screenplay": "SCRIPT",
    "pitch": "SCRIPT",
    "pre_production": "PRODUCTION_PLANNING",
    "production": "PRODUCTION",
    "post": "POST_PRODUCTION",
}

_DIRECTOR_CREATIVE_STAGE_MAP: dict[str, str] = {
    "vision": "STORY",
    "premise": "STORY",
    "discovery": "STORY",
    "treatment": "SCRIPT",
    "screenplay": "SCRIPT",
    "pitch": "SCRIPT",
    "pre_production": "PRODUCTION_PLANNING",
    "production": "PRODUCTION",
    "post": "POST_PRODUCTION",
}

_DEVELOPMENT_STAGE_MAP: dict[str, str] = {
    "story": "STORY",
    "script": "SCRIPT",
    "preproduction": "PRODUCTION_PLANNING",
    "pre_production": "PRODUCTION_PLANNING",
    "casting": "CASTING",
    "production": "PRODUCTION",
    "post": "POST_PRODUCTION",
    "post_production": "POST_PRODUCTION",
    "final_qc": "FINAL_QC",
    "complete": "COMPLETE",
    "timeline_assembly": "TIMELINE_ASSEMBLY",
    "discovery": "STORY",
}

_DISCOVERY_TEMPERATURE_MAP: dict[str, str] = {
    "emergence": "STORY",
    "exploration": "STORY",
    "formation": "SCRIPT",
    "evaluation": "SCRIPT",
    "production": "PRODUCTION",
}

_PARTNERSHIP_JOURNEY_MAP: dict[str, str] = {
    "initial_idea": "STORY",
    "discovery": "STORY",
    "treatment": "SCRIPT",
    "screenplay": "SCRIPT",
    "pitch_package": "SCRIPT",
    "pre_production": "PRODUCTION_PLANNING",
    "production": "PRODUCTION",
    "post_production": "POST_PRODUCTION",
}

AUTHORITATIVE_STAGES: frozenset[str] = frozenset({
    "STORY", "SCRIPT", "CASTING", "PRODUCTION_PLANNING", "PRODUCTION",
    "TIMELINE_ASSEMBLY", "POST_PRODUCTION", "FINAL_QC", "COMPLETE",
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_settings(db: Session, project_id: str) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if not project:
        return {}
    raw = getattr(project, "settings_json", None)
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _try_path(settings: dict[str, Any], *keys: str) -> Any:
    current: Any = settings
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _map_value(label: str | None, mapping: dict[str, str]) -> str:
    if label is None:
        return "unavailable"
    mapped = mapping.get(label.casefold())
    return mapped if mapped is not None else "unknown"


def _make_evidence(
    source: str,
    raw_label: str | None,
    mapped_label: str,
    authoritative_stage: str,
) -> StageEvidence:
    raw = raw_label if raw_label is not None else "unavailable"
    mapped = mapped_label if raw_label is not None else "unavailable"
    agreed = mapped == authoritative_stage
    return StageEvidence(
        source=source,
        raw_label=raw,
        mapped_label=mapped,
        agreed=agreed,
        stale=False,
    )


def _partial_match(label: str) -> str | None:
    lower = label.casefold()
    for stage in AUTHORITATIVE_STAGES:
        if lower in stage.casefold() or stage.casefold() in lower:
            return stage
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_stage_evidence(db: Session, project_id: str) -> list[StageEvidence]:
    """Read all 7 audited stage sources and return an evidence trace.

    Source order (frozen per §2.3 Derived stage):
      1. snapshot.productionLifecycle.currentStage — AUTHORITATIVE
      2. snapshot.currentStage                         — candidate
      3. snapshot.director.creativeStage                — candidate
      4. ProjectIntelligenceCache.developmentStage      — candidate
      5. m214_project_stages.stage                      — candidate
      6. discovery temperature.stage                    — heuristic
      7. partnership journey.current_stage              — heuristic
    """
    settings = _project_settings(db, project_id)

    # --- Resolve authoritative stage (source 1) ---
    raw_lifecycle = _try_path(settings, "projectIntelligence", "productionLifecycle", "currentStage")
    if isinstance(raw_lifecycle, str) and raw_lifecycle.upper() in AUTHORITATIVE_STAGES:
        authoritative_stage = raw_lifecycle.upper()
    else:
        authoritative_stage = "unknown"

    evidence: list[StageEvidence] = []

    # ------------------------------------------------------------------
    # Source 1 — authoritative lifecycle
    # ------------------------------------------------------------------
    raw_lc_label = raw_lifecycle if isinstance(raw_lifecycle, str) else None
    if raw_lc_label and raw_lc_label.upper() in AUTHORITATIVE_STAGES:
        mapped_lc = raw_lc_label.upper()
    else:
        mapped_lc = "unknown"
    evidence.append(_make_evidence(
        "snapshot.productionLifecycle.currentStage",
        raw_lc_label,
        mapped_lc,
        authoritative_stage,
    ))

    # ------------------------------------------------------------------
    # Source 2 — snapshot.currentStage
    # ------------------------------------------------------------------
    raw_current = _try_path(settings, "projectIntelligence", "currentStage")
    raw_current_label = raw_current if isinstance(raw_current, str) else None
    mapped_current = _map_value(raw_current_label, _SNAPSHOT_CURRENT_STAGE_MAP)
    evidence.append(_make_evidence(
        "snapshot.currentStage",
        raw_current_label,
        mapped_current,
        authoritative_stage,
    ))

    # ------------------------------------------------------------------
    # Source 3 — snapshot.director.creativeStage
    # ------------------------------------------------------------------
    raw_creative = _try_path(settings, "projectIntelligence", "director", "creativeStage")
    raw_creative_label = raw_creative if isinstance(raw_creative, str) else None
    mapped_creative = _map_value(raw_creative_label, _DIRECTOR_CREATIVE_STAGE_MAP)
    evidence.append(_make_evidence(
        "snapshot.director.creativeStage",
        raw_creative_label,
        mapped_creative,
        authoritative_stage,
    ))

    # ------------------------------------------------------------------
    # Source 4 — ProjectIntelligenceCache.developmentStage
    # ------------------------------------------------------------------
    try:
        raw_dev = _try_path(settings, "projectIntelligenceCache", "developmentStage")
    except Exception:
        raw_dev = None
    raw_dev_label = raw_dev if isinstance(raw_dev, str) else None
    mapped_dev = _map_value(raw_dev_label, _DEVELOPMENT_STAGE_MAP)
    evidence.append(_make_evidence(
        "ProjectIntelligenceCache.developmentStage",
        raw_dev_label,
        mapped_dev,
        authoritative_stage,
    ))

    # ------------------------------------------------------------------
    # Source 5 — m214_project_stages.stage
    # ------------------------------------------------------------------
    try:
        m214_result = M214Store.get_stage(db, project_id)
        m214_stage = m214_result.get("stage") if isinstance(m214_result, dict) else None
    except Exception:
        m214_stage = None
    raw_m214_label = m214_stage if isinstance(m214_stage, str) else None
    if raw_m214_label is not None:
        upper = raw_m214_label.upper()
        if upper in AUTHORITATIVE_STAGES:
            mapped_m214 = upper
        else:
            match = _partial_match(raw_m214_label)
            mapped_m214 = match if match is not None else "unknown"
    else:
        mapped_m214 = "unavailable"
    evidence.append(_make_evidence(
        "m214_project_stages.stage",
        raw_m214_label,
        mapped_m214,
        authoritative_stage,
    ))

    # ------------------------------------------------------------------
    # Source 6 — discovery temperature.stage
    # ------------------------------------------------------------------
    try:
        discovery_bundle = settings.get("discoveryIntelligence")
        if isinstance(discovery_bundle, dict):
            raw_temp = discovery_bundle.get("creative_stage")
            if raw_temp is None:
                ct = discovery_bundle.get("creativeTemperature")
                if isinstance(ct, dict):
                    raw_temp = ct.get("stage")
        else:
            raw_temp = None
    except Exception:
        raw_temp = None
    raw_temp_label = raw_temp if isinstance(raw_temp, str) else None
    mapped_temp = _map_value(raw_temp_label, _DISCOVERY_TEMPERATURE_MAP)
    evidence.append(_make_evidence(
        "discovery.temperature.stage",
        raw_temp_label,
        mapped_temp,
        authoritative_stage,
    ))

    # ------------------------------------------------------------------
    # Source 7 — partnership journey.current_stage
    # ------------------------------------------------------------------
    try:
        companion = settings.get("companionIntelligence")
        journey_state: dict[str, Any] | None = None
        if isinstance(companion, dict):
            journey_state = companion.get("partnershipJourneyState") or companion.get("journey")
        if not journey_state:
            partnership = settings.get("partnershipIntelligence")
            if isinstance(partnership, dict):
                journey_state = partnership.get("journey")
        raw_journey = None
        if isinstance(journey_state, dict):
            raw_journey = journey_state.get("currentStage") or journey_state.get("current_stage")
    except Exception:
        raw_journey = None
    raw_journey_label = raw_journey if isinstance(raw_journey, str) else None
    mapped_journey = _map_value(raw_journey_label, _PARTNERSHIP_JOURNEY_MAP)
    evidence.append(_make_evidence(
        "partnership.journey.current_stage",
        raw_journey_label,
        mapped_journey,
        authoritative_stage,
    ))

    return evidence


def enrich_with_stage(state: ProductionState, db: Session, project_id: str) -> ProductionState:
    """Return a copy of *state* with ``evidenceTrace`` populated from live stage sources."""
    evidence = collect_stage_evidence(db, project_id)
    return state.model_copy(update={
        "evidenceTrace": [e.model_dump() for e in evidence],
    })


def get_authoritative_stage(db: Session, project_id: str) -> str:
    """Return the authoritative ``currentStage`` for the project, or ``"unknown"``."""
    settings = _project_settings(db, project_id)
    raw = _try_path(settings, "projectIntelligence", "productionLifecycle", "currentStage")
    if isinstance(raw, str) and raw.upper() in AUTHORITATIVE_STAGES:
        return raw.upper()
    return "unknown"
