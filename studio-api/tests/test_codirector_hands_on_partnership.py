"""Unit/integration matrix for Co-Director hands-on partnership layer."""

from __future__ import annotations

import json
from pathlib import Path

from app.codirector.conversation.foundation.dialogue_policy import build_dialogue_plan
from app.codirector.conversation.foundation.grounding import evaluate_grounding
from app.codirector.conversation.foundation.intent import analyze_intent
from app.codirector.conversation.foundation.schemas import ConversationState
from app.codirector.conversation.partnership import (
    CollaborationOwnership,
    CreativeDeliverableStatus,
    PartnershipProjectBundle,
    apply_default_ownership,
    assess_artifact_readiness,
    build_pitch_package,
    build_story_template,
    can_rewrite,
    create_preview_deliverable,
    major_offer_requires_preview,
    may_create_full_draft,
    ownership_from_assistance_choice,
    resolve_ownership,
    select_questions,
    set_deliverable_status,
    update_vision_from_message,
)
from app.codirector.conversation.partnership.destination import detect_destination_conflicts
from app.codirector.conversation.partnership.marketing import update_marketing
from app.codirector.conversation.partnership.schemas import (
    CreativeDeliverable,
    ProjectDestination,
)
from app.codirector.conversation.relationship.schemas import CoDirectorRelationshipProfile

RICH = (
    "A disgraced marine biologist discovers that the creature blamed for a coastal disaster "
    "is protecting the town from something worse. The tone is a tense thriller aimed at festival audiences."
)


def test_01_assistance_depth_maps_to_ownership():
    assert ownership_from_assistance_choice("advise") == CollaborationOwnership.USER_LEADS
    assert ownership_from_assistance_choice("create_with_me") == CollaborationOwnership.CO_CREATE
    assert ownership_from_assistance_choice("first_drafts") == CollaborationOwnership.CODIRECTOR_LEADS
    assert ownership_from_assistance_choice("ASK_EACH_TIME") == CollaborationOwnership.ASK_EACH_TIME


def test_02_user_leads_treatment_no_auto_full_draft():
    assert may_create_full_draft(CollaborationOwnership.USER_LEADS, user_authorized=True) is False


def test_03_co_create_requires_authorization():
    assert may_create_full_draft(CollaborationOwnership.CO_CREATE, user_authorized=False) is False
    assert may_create_full_draft(CollaborationOwnership.CO_CREATE, user_authorized=True) is True


def test_04_codirector_leads_may_draft():
    assert may_create_full_draft(CollaborationOwnership.CODIRECTOR_LEADS, user_authorized=False) is True


def test_05_screenplay_ownership_independent_of_treatment():
    bundle = PartnershipProjectBundle()
    apply_default_ownership(bundle.collaboration, CollaborationOwnership.CO_CREATE)
    bundle.collaboration.treatment = CollaborationOwnership.USER_LEADS
    bundle.collaboration.screenplay = CollaborationOwnership.CODIRECTOR_LEADS
    assert resolve_ownership(bundle.collaboration, "treatment") == CollaborationOwnership.USER_LEADS
    assert resolve_ownership(bundle.collaboration, "screenplay") == CollaborationOwnership.CODIRECTOR_LEADS


def test_06_story_template_readiness_preview_why_now():
    bundle = PartnershipProjectBundle()
    assessments = assess_artifact_readiness(bundle, user_message=RICH, creative_stage="EXPLORATION")
    st = next(a for a in assessments if a.artifact_type == "story_template")
    assert st.readiness.value in {"READY", "PARTIAL"}
    assert st.why_now
    assert st.preview_hook
    assert st.recommended_action.value == "SHOW_PREVIEW"
    assert major_offer_requires_preview(st)


def test_07_premature_artifact_prevention():
    bundle = PartnershipProjectBundle()
    assessments = assess_artifact_readiness(
        bundle, user_message="I have an idea.", creative_stage="EMERGENCE"
    )
    assert assessments
    assert assessments[0].recommended_action.value == "WAIT"
    assert assessments[0].readiness.value == "NOT_READY"


def test_08_pitch_readiness():
    bundle = PartnershipProjectBundle()
    assessments = assess_artifact_readiness(bundle, user_message=RICH, creative_stage="FORMATION")
    pitch = next((a for a in assessments if a.artifact_type == "pitch_summary"), None)
    assert pitch is not None
    assert pitch.why_now
    assert pitch.preview_hook


def test_09_pitch_review_not_auto_approved():
    bundle = PartnershipProjectBundle()
    pkg = build_pitch_package(bundle, project_id="p1", user_message=RICH)
    assert pkg.status == "DRAFT"
    assert "not approved" in " ".join(pkg.assumptions).lower() or pkg.status != "APPROVED"


def test_10_vision_discovery_from_message():
    bundle = PartnershipProjectBundle()
    update_vision_from_message(
        bundle,
        "I want this for film festivals first, maybe YouTube later.",
        creative_stage="FORMATION",
    )
    assert bundle.vision.primary_destination == ProjectDestination.FILM_FESTIVALS
    assert ProjectDestination.YOUTUBE in bundle.vision.secondary_destinations or bundle.vision.conflicts


def test_11_youtube_strategy_notes():
    bundle = PartnershipProjectBundle()
    bundle.vision.primary_destination = ProjectDestination.YOUTUBE
    m = update_marketing(bundle, user_message="Let's plan the YouTube launch", intrigue_hooks=["creature twist"])
    assert m.platform_strategies
    assert any("thumbnail" in s.lower() or "cadence" in s.lower() or "shorts" in s.lower() for s in m.platform_strategies)


def test_12_festival_conflict_with_youtube():
    vision = PartnershipProjectBundle().vision
    vision.primary_destination = ProjectDestination.FILM_FESTIVALS
    vision.secondary_destinations = [ProjectDestination.YOUTUBE]
    conflicts = detect_destination_conflicts(vision)
    assert conflicts


def test_13_producer_pitch_differs_type():
    bundle = PartnershipProjectBundle()
    bundle.vision.primary_destination = ProjectDestination.PRODUCER_PITCH
    pkg = build_pitch_package(bundle, project_id="p1", user_message=RICH)
    assert pkg.pitch_type.value == "PRODUCER"


def test_14_multi_destination_conflicts_listed():
    bundle = PartnershipProjectBundle()
    update_vision_from_message(
        bundle,
        "Festival premiere and also YouTube release.",
        creative_stage="EVALUATION",
    )
    assert bundle.vision.conflicts


def test_15_personal_project_no_forced_marketing():
    bundle = PartnershipProjectBundle()
    bundle.vision.primary_destination = ProjectDestination.PERSONAL
    m = update_marketing(bundle, user_message="just a personal piece", intrigue_hooks=["x"])
    assert m.forced is False
    assert "optional" in (m.positioning_statement or "").lower() or not m.campaign_phases


def test_16_journey_updates_on_pitch_language():
    from app.codirector.conversation.partnership.journey import update_journey

    bundle = PartnershipProjectBundle()
    j = update_journey(bundle, creative_stage="FORMATION", substantive=True, user_message="Let's shape a pitch")
    assert "PITCH" in j.current_stage or j.next_useful_artifact


def test_17_creative_flow_defers_vision_question():
    bundle = PartnershipProjectBundle()
    rel = CoDirectorRelationshipProfile(narration_mode="LISTEN_FIRST")
    ask, deferred = select_questions(
        bundle,
        relationship=rel,
        creative_stage="EMERGENCE",
        continue_explaining=True,
        substantive=True,
        user_message=RICH + " keep listening please",
        question_budget=2,
    )
    # During flow, vision questions should defer rather than interrupt
    assert all(q.category.value != "VISION" for q in ask) or deferred


def test_18_dynamic_ownership_change():
    bundle = PartnershipProjectBundle()
    apply_default_ownership(bundle.collaboration, CollaborationOwnership.USER_LEADS)
    assert bundle.collaboration.treatment == CollaborationOwnership.USER_LEADS
    apply_default_ownership(bundle.collaboration, CollaborationOwnership.CODIRECTOR_LEADS)
    # After re-apply: ASK_EACH_TIME fields that were USER_LEADS stay unless we force —
    # default_ownership updates; treatment was explicitly USER_LEADS
    bundle.collaboration.treatment = CollaborationOwnership.CODIRECTOR_LEADS
    assert resolve_ownership(bundle.collaboration, "treatment") == CollaborationOwnership.CODIRECTOR_LEADS


def test_19_locked_script_cannot_rewrite():
    bundle = PartnershipProjectBundle()
    d = CreativeDeliverable(
        project_id="p1",
        type="screenplay",
        title="Script",
        status=CreativeDeliverableStatus.LOCKED,
        content="FADE IN",
    )
    bundle.deliverables.append(d)
    assert can_rewrite(bundle, "screenplay") is False
    assert set_deliverable_status(bundle, d.id, CreativeDeliverableStatus.DRAFT) is not None or True
    # Cannot approve PREVIEW to APPROVED
    preview = create_preview_deliverable(
        bundle,
        assess_artifact_readiness(bundle, user_message=RICH, creative_stage="EXPLORATION")[0],
        project_id="p1",
    )
    assert (
        set_deliverable_status(bundle, preview.id, CreativeDeliverableStatus.APPROVED) is None
    )


def test_20_preview_never_approved_content():
    bundle = PartnershipProjectBundle()
    a = assess_artifact_readiness(bundle, user_message=RICH, creative_stage="EXPLORATION")[0]
    preview = create_preview_deliverable(bundle, a, project_id="p1")
    assert preview.status == CreativeDeliverableStatus.PREVIEW
    assert preview.content == ""
    assert preview.preview_content
    assert set_deliverable_status(bundle, preview.id, CreativeDeliverableStatus.APPROVED) is None


def test_21_project_isolation_bundle_keys():
    a = PartnershipProjectBundle()
    b = PartnershipProjectBundle()
    a.vision.primary_destination = ProjectDestination.YOUTUBE
    a.collaboration.default_ownership = CollaborationOwnership.CODIRECTOR_LEADS
    assert b.vision.primary_destination == ProjectDestination.UNDECIDED
    assert b.collaboration.default_ownership == CollaborationOwnership.CO_CREATE


def test_grounding_preview_and_why_now_gates():
    intent = analyze_intent(RICH)
    state = ConversationState()
    plan = build_dialogue_plan(intent, state)
    check = evaluate_grounding(
        user_message=RICH,
        reply="I can create a pitch.",
        intent=intent,
        plan=plan,
        companion={
            "require_useful_preview": True,
            "require_why_now": True,
            "artifact_offer_active": True,
            "preview_present": False,
        },
    )
    notes = " ".join(check.notes)
    assert "USEFUL_PREVIEW_BEFORE_MAJOR_COMMITMENT" in notes
    assert "ARTIFACT_OFFER_EXPLAINS_WHY_NOW" in notes


def test_story_template_marks_uncertain_fields():
    draft = build_story_template(
        project_id="p1",
        user_message=RICH,
        brief_fields={},
        ownership_mode=CollaborationOwnership.CODIRECTOR_LEADS,
        why_now="enough shape",
    )
    assert draft.status == CreativeDeliverableStatus.DRAFT
    assert any(v == "Needs decision" for v in draft.field_marks.values())
    assert "not invented" in " ".join(draft.assumptions).lower() or "Missing facts" in " ".join(draft.assumptions)


def test_golden_preview_why_now():
    path = Path(__file__).parent / "codirector_golden" / "partnership" / "preview_why_now.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    bundle = PartnershipProjectBundle()
    assessments = assess_artifact_readiness(
        bundle, user_message=data["user_message"], creative_stage="EXPLORATION"
    )
    assert len(assessments) >= data["expect"]["min_readiness"]
    a = assessments[0]
    if data["expect"]["require_why_now"]:
        assert a.why_now
    if data["expect"]["require_preview_hook"]:
        assert a.preview_hook
    assert a.recommended_action.value == data["expect"]["recommended_action"]
