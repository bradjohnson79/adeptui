"""Unit tests for Smart Production Gates and Timeline Context Package."""

from __future__ import annotations

from app.codirector.timeline_context.contracts import (
    SCENE_LIFECYCLE_STATUSES,
    TimelineContextPackage,
    TimelineGateLevel,
)
from app.codirector.timeline_context.smart_gates import evaluate_smart_gate


def test_scene_lifecycle_statuses_present():
    assert "Draft" in SCENE_LIFECYCLE_STATUSES
    assert "Ready" in SCENE_LIFECYCLE_STATUSES
    assert "Approved" in SCENE_LIFECYCLE_STATUSES
    assert "Locked" in SCENE_LIFECYCLE_STATUSES
    assert len(SCENE_LIFECYCLE_STATUSES) == 7


def test_gate_level_literal_values():
    levels = {"EXPLORATION", "PRODUCTION_WARNING", "PRODUCTION_LOCK"}
    assert set(TimelineGateLevel.__args__) == levels  # type: ignore[attr-defined]


def test_context_package_defaults():
    pkg = TimelineContextPackage(projectId="p1", sceneId="s1")
    assert pkg.gateLevel == "EXPLORATION"
    assert pkg.sceneStatus == "Draft"
    assert pkg.characters == []
    assert pkg.references == []
    assert pkg.readiness.status == "BLOCKED"
    assert pkg.generationConstraints.engine == "auto"


def test_evaluate_smart_gate_missing_project_does_not_crash(tmp_path):
    """Gate evaluation must degrade gracefully when project/scene missing."""
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        result = evaluate_smart_gate(db, "nonexistent-project", "nonexistent-scene", action_scope="exploration")
        assert result["ok"] is True
        assert result["decision"] == "ALLOW"
        assert result["level"] == "EXPLORATION"
    finally:
        db.close()
