"""Deterministic tests for the Production State Projection (Co-Director 2.0 Mission B).

All tests use mocks — no real project, no real DB. Covers:
  - 14-domain composition
  - stage evidence with authoritative wins
  - stage mapping coverage
  - enrich_with_stage populates evidenceTrace
  - invalidation API delegates correctly
  - projection never writes to DB
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.codirector.production_state.contracts import ProductionState, ProjectionDomain, StageEvidence
from app.codirector.production_state.invalidation import invalidate_production_state
from app.codirector.production_state.projection import build_production_state
from app.codirector.production_state.stage_evidence import (
    _map_value,
    _partial_match,
    _SNAPSHOT_CURRENT_STAGE_MAP,
    collect_stage_evidence,
    enrich_with_stage,
)


# ---------------------------------------------------------------------------
# 1. test_projection_domains_present
# ---------------------------------------------------------------------------


def test_projection_domains_present() -> None:
    db = MagicMock(spec=Session)

    fake_project = MagicMock()
    fake_project.name = "Test"
    fake_project.primary_project_type = "NARRATIVE"
    fake_project.fps = 24
    fake_project.width = 1920
    fake_project.height = 1080
    fake_project.resolved_profile_json = {}
    db.get.return_value = fake_project

    # No scenes
    db.query.return_value.filter.return_value.all.return_value = []

    result = build_production_state(db, "proj1")

    assert isinstance(result, ProductionState)
    # ALL 14 ProjectionDomain enum members as keys
    for domain in ProjectionDomain:
        assert domain in result.domains, f"Missing domain: {domain}"

    assert result.domains[ProjectionDomain.PROJECT]["title"].value == "Test"
    assert result.domains[ProjectionDomain.PROJECT]["title"].source == "projects.name"
    assert result.domains[ProjectionDomain.PROJECT]["title"].provenance == "creator-stated"


# ---------------------------------------------------------------------------
# 2. test_stage_evidence_authoritative_wins
# ---------------------------------------------------------------------------


def test_stage_evidence_authoritative_wins() -> None:
    db = MagicMock(spec=Session)

    # Simulate settings_json with conflict:
    #   authoritative: productionLifecycle.currentStage = "SCRIPT"
    #   candidate:     currentStage = "vision" (maps to "STORY" → conflict)
    fake_project = MagicMock()
    fake_project.settings_json = {
        "projectIntelligence": {
            "productionLifecycle": {"currentStage": "SCRIPT"},
            "currentStage": "vision",
        },
    }
    db.get.return_value = fake_project

    evidence = collect_stage_evidence(db, "proj1")

    # Authoritative source (index 0) must have raw_label="SCRIPT"
    assert evidence[0].raw_label == "SCRIPT"
    assert evidence[0].source == "snapshot.productionLifecycle.currentStage"
    assert evidence[0].agreed is True

    # Creative state source (index 2) should be "vision" with mapped_label="STORY"
    creative = [e for e in evidence if e.source == "snapshot.currentStage"]
    assert len(creative) == 1
    assert creative[0].raw_label == "vision"
    assert creative[0].mapped_label == "STORY"
    assert creative[0].agreed is False

    # evidenceTrace lists all 7 sources
    assert len(evidence) == 7


# ---------------------------------------------------------------------------
# 3. test_stage_mapping_coverage
# ---------------------------------------------------------------------------


def test_stage_mapping_coverage() -> None:
    # Test _SNAPSHOT_CURRENT_STAGE_MAP
    assert _map_value("vision", _SNAPSHOT_CURRENT_STAGE_MAP) == "STORY"
    assert _map_value("premise", _SNAPSHOT_CURRENT_STAGE_MAP) == "STORY"
    assert _map_value("production", _SNAPSHOT_CURRENT_STAGE_MAP) == "PRODUCTION"
    assert _map_value("INVALID", _SNAPSHOT_CURRENT_STAGE_MAP) == "unknown"
    assert _map_value(None, _SNAPSHOT_CURRENT_STAGE_MAP) == "unavailable"

    # Test _partial_match — SOUND_STAGE doesn't contain any authoritative stage name
    assert _partial_match("SOUND_STAGE") is None
    assert _partial_match("GARBAGE") is None


# ---------------------------------------------------------------------------
# 4. test_enrich_with_stage
# ---------------------------------------------------------------------------


def test_enrich_with_stage() -> None:
    db = MagicMock(spec=Session)
    fake_project = MagicMock()
    fake_project.settings_json = {
        "projectIntelligence": {
            "productionLifecycle": {"currentStage": "STORY"},
        },
    }
    db.get.return_value = fake_project

    # Build a minimal ProductionState with only PROJECT domain
    domains = {ProjectionDomain.PROJECT: {}}
    state = ProductionState(domains=domains)

    enriched = enrich_with_stage(state, db, "proj1")

    assert isinstance(enriched, ProductionState)
    assert len(enriched.evidenceTrace) > 0
    # evidenceTrace entries are dicts with expected keys
    for entry in enriched.evidenceTrace:
        assert "source" in entry
        assert "raw_label" in entry
        assert "mapped_label" in entry
        assert "agreed" in entry


# ---------------------------------------------------------------------------
# 5. test_invalidation_api
# ---------------------------------------------------------------------------


def test_invalidation_api() -> None:
    db = MagicMock(spec=Session)

    with patch(
        "app.codirector.production_state.invalidation.invalidate_cache_sections"
    ) as mock_invalidate:
        invalidate_production_state(db, "proj1")
        mock_invalidate.assert_called_once_with(db, "proj1", ["production_state"])


# ---------------------------------------------------------------------------
# 6. test_production_state_no_writes
# ---------------------------------------------------------------------------


def test_production_state_no_writes() -> None:
    db = MagicMock(spec=Session)

    fake_project = MagicMock()
    fake_project.name = "Test"
    fake_project.primary_project_type = "NARRATIVE"
    fake_project.fps = 24
    fake_project.width = 1920
    fake_project.height = 1080
    fake_project.resolved_profile_json = {}
    db.get.return_value = fake_project
    db.query.return_value.filter.return_value.all.return_value = []

    result = build_production_state(db, "proj1")

    # build_production_state must never call write methods
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.merge.assert_not_called()
    db.flush.assert_not_called()
