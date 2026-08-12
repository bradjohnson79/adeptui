"""Foundation Phase 4 collaboration helper tests."""

from __future__ import annotations

from app.codirector.foundation.collaboration.modes import infer_mode, normalize_collaboration_mode
from app.codirector.foundation.collaboration.preferences import (
    forget_preference,
    get_preference,
    list_preferences,
    set_preference,
)
from app.codirector.foundation.collaboration.review import (
    build_review_notes,
    list_rejected_alternatives,
    should_suppress_alternative,
)


def test_modes_normalize_and_infer_creator_intent() -> None:
    assert normalize_collaboration_mode("brainstorm") == "explore"
    assert normalize_collaboration_mode("feedback") == "critique"
    assert infer_mode("Compare option A and option B before we decide.") == "compare"
    assert infer_mode("Teach me why this works.") == "teach"


def test_preferences_are_project_scoped_and_forgettable() -> None:
    project_id = "proj-collab-1"
    pref = set_preference(project_id, "tone", "wry", source="explicit")

    assert pref.projectId == project_id
    assert get_preference(project_id, "tone") is not None
    assert [item.key for item in list_preferences(project_id)] == ["tone"]
    assert forget_preference(project_id, "tone") is True
    assert get_preference(project_id, "tone") is None


def test_review_notes_remember_rejected_alternatives() -> None:
    project_id = "proj-collab-2"
    notes = build_review_notes(
        project_id,
        summary="Keep the stronger emotional version.",
        accepted=["Sharper reaction shot"],
        concerns=["Second option feels too generic."],
        rejected_alternatives=["Blue neon alley", "Blue Neon Alley"],
        follow_up=["Offer one warmer alternative."],
    )

    assert notes["rejectedAlternatives"] == ["blue neon alley"]
    assert list_rejected_alternatives(project_id) == ["blue neon alley"]
    assert should_suppress_alternative(project_id, "Blue neon alley") is True
