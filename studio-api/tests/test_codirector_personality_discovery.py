"""Personality / relationship / intrigue / discovery suite."""

from __future__ import annotations

import json
import re

from app.codirector.conversation.discovery import (
    assess_creative_temperature,
    assess_intrigue,
    extract_documentation,
    score_response_evidence,
)
from app.codirector.conversation.discovery.schemas import CreativeDevelopmentStage, DocumentationReason
from app.codirector.conversation.orchestrate import run_conversation_core_turn
from app.codirector.conversation.relationship import (
    PrimaryRole,
    apply_onboarding_message,
    balanced_defaults,
    load_relationship_profile,
    needs_onboarding,
    skip_onboarding,
)
from app.codirector.conversation.relationship.schemas import CoDirectorRelationshipProfile


class _FakeProject:
    def __init__(self, project_id: str = "proj-a", name: str = "Alpha Saga"):
        self.id = project_id
        self.name = name
        self.primary_project_type = "web_series"
        self.settings_json = "{}"
        self.description = ""


class _FakeDb:
    def __init__(self, project: _FakeProject | None = None):
        self.project = project or _FakeProject()

    def get(self, model, key):  # noqa: ANN001
        name = getattr(model, "__name__", str(model))
        if name == "Project" and key == self.project.id:
            return self.project
        return None

    def add(self, obj):  # noqa: ANN001
        return obj

    def commit(self):
        return None

    def refresh(self, obj):  # noqa: ANN001
        return obj


RICH = (
    "Mira is a cartographer in a salt-marsh city who maps tides that remember people. "
    "When an ancient lantern entity answers her chart marks, the city starts aging backward "
    "for anyone who hears its call. Season one stays intimate and mythic — no cyberpunk polish. "
    "Continuity rule: lantern light must always feel hand-lit and tidal."
)


def _run(msg: str, *, project_id: str = "proj-a", name: str = "Alpha Saga", db: _FakeDb | None = None):
    db = db or _FakeDb(_FakeProject(project_id=project_id, name=name))
    return (
        run_conversation_core_turn(
            db,
            project_id=project_id,
            messages=[{"role": "user", "content": msg}],
            user_message=msg,
        ),
        db,
    )


def test_emergence_temperature_blocks_critique():
    temp = assess_creative_temperature(RICH)
    assert temp.stage == CreativeDevelopmentStage.EMERGENCE
    assert temp.critique_allowed is False
    assert temp.caution_allowed is False


def test_intrigue_has_evidence_spans():
    intrigue = assess_intrigue(RICH)
    assert intrigue.evidence_spans
    assert intrigue.distinctive_elements or intrigue.emotional_hooks


def test_documentation_extracts_candidates_or_reason():
    result = extract_documentation(RICH, project_id="proj-a", source_id="t1")
    assert result.substantive is True
    assert result.candidate_count > 0
    assert result.reason == DocumentationReason.OK


def test_documentation_never_silent_zero_on_substantive():
    result = extract_documentation(
        "I have thoughts but nothing concrete yet about anyone or anywhere specific somehow somehow somehow somehow somehow.",
        project_id="proj-a",
        source_id="t2",
    )
    if result.substantive and result.candidate_count == 0:
        assert result.reason in {
            DocumentationReason.NO_PROJECT_FACTS_FOUND,
            DocumentationReason.AMBIGUOUS_CONTENT,
            DocumentationReason.EXTRACTION_FAILED,
        }


def test_documentation_disabled_reason():
    rel = CoDirectorRelationshipProfile(documentation_mode="MANUAL_ONLY")
    result = extract_documentation(RICH, project_id="proj-a", source_id="t3", relationship=rel)
    assert result.reason == DocumentationReason.DOCUMENTATION_DISABLED
    assert result.candidate_count == 0


def test_response_evidence_requires_two_slots():
    evidence = score_response_evidence(
        "What stands out is the tidal memory maps. That tension gives the story emotional weight. "
        "I’ve begun documenting: 2 character records."
    )
    assert evidence.count >= 2
    assert evidence.ok is True


def test_onboarding_names_and_skip():
    profile = CoDirectorRelationshipProfile()
    assert needs_onboarding(profile) is True
    profile, done = apply_onboarding_message(
        profile, "Call me Sam. I’ll call you Scout. Story partner please."
    )
    assert done is True
    assert profile.user_preferred_name.lower() == "sam"
    assert profile.assistant_preferred_name.lower() == "scout"
    assert profile.primary_role == PrimaryRole.STORY_PARTNER
    skipped = balanced_defaults()
    assert skipped.onboarding_skipped is True


def test_turn_emits_discovery_artifacts_and_evidence():
    result, db = _run(RICH)
    assert result.documentationResult.get("candidate_count", 0) > 0
    assert result.responseEvidence.get("ok") is True
    assert result.responseEvidence.get("count", 0) >= 2
    assert result.creativeTemperature.get("stage") == "EMERGENCE"
    assert result.conversationActions
    assert any(a.get("id") == "continue_explaining" for a in result.conversationActions)
    settings = json.loads(db.project.settings_json)
    assert "discoveryIntelligence" in settings
    assert "relationshipProfile" in settings


def test_inferred_theme_not_confirmed_without_explicit_statement():
    result = extract_documentation(
        "A lonely lighthouse keeper keeps hearing two overlapping versions of the same storm. "
        "It feels like identity and memory are braided together somehow across the coastline.",
        project_id="proj-a",
        source_id="t4",
    )
    themes = [c for c in result.candidates if c.category.value == "THEME"]
    for theme in themes:
        if "inferred" in theme.title.lower() or "emerging" in theme.title.lower():
            assert theme.status in {"INFERRED", "EMERGING"}


def test_project_isolation_discovery_memory():
    _, db_a = _run(RICH, project_id="proj-a", name="Alpha")
    _, db_b = _run("Short hello only.", project_id="proj-b", name="Beta")
    a = json.loads(db_a.project.settings_json)
    b = json.loads(db_b.project.settings_json)
    assert "discoveryIntelligence" in a
    # Beta short message may still create empty-ish bundle; must not contain Alpha lore
    blob_b = json.dumps(b)
    assert "salt-marsh city" not in blob_b
    assert "Mira is a cartographer" not in blob_b


def test_skip_onboarding_persists():
    db = _FakeDb(_FakeProject())
    profile = skip_onboarding(db, "proj-a")
    loaded = load_relationship_profile(db, "proj-a")
    assert profile.onboarding_completed is True
    assert loaded.onboarding_skipped is True


def test_emergence_reply_avoids_generic_praise_and_premature_caution():
    result, _ = _run(RICH)
    assert not re.search(r"you(?:'re| are) a genius|groundbreaking", result.reply, re.I)
    # Soft: unsolicited feasibility caution should stay out of emergence enrichment path
    assert "too ambitious" not in result.reply.lower()
