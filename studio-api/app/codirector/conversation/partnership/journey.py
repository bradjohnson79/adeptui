"""Production journey awareness — lifecycle stage tracking."""

from __future__ import annotations

from .schemas import (
    CreativeDeliverableStatus,
    PartnershipProjectBundle,
    ProductionJourneyStage,
    ProductionJourneyState,
    ProjectDestination,
)


def update_journey(
    bundle: PartnershipProjectBundle,
    *,
    creative_stage: str,
    substantive: bool,
    user_message: str,
) -> ProductionJourneyState:
    journey = bundle.journey
    msg = (user_message or "").lower()
    stage = journey.current_stage

    if creative_stage == "EMERGENCE" and substantive:
        stage = ProductionJourneyStage.INITIAL_IDEA.value
    if creative_stage in {"EXPLORATION", "FORMATION"}:
        stage = ProductionJourneyStage.DISCOVERY.value
    if any(k in msg for k in ("treatment", "outline", "beat sheet")):
        stage = ProductionJourneyStage.TREATMENT.value
    if any(k in msg for k in ("screenplay", "script", "scene")):
        stage = ProductionJourneyStage.SCREENPLAY.value
    if any(k in msg for k in ("pitch", "logline", "one-sheet")):
        stage = ProductionJourneyStage.PITCH_PACKAGE.value
    if any(k in msg for k in ("youtube", "festival", "marketing", "launch", "release")):
        stage = ProductionJourneyStage.MARKETING_PREP.value
    if any(k in msg for k in ("production plan", "shot list", "pre-production")):
        stage = ProductionJourneyStage.PRE_PRODUCTION.value

    if journey.current_stage != stage and journey.current_stage not in journey.completed_stages:
        journey.completed_stages.append(journey.current_stage)
    journey.current_stage = stage

    approved = [d for d in bundle.deliverables if d.status in {CreativeDeliverableStatus.APPROVED, CreativeDeliverableStatus.LOCKED}]
    journey.active_deliverables = [d.id for d in bundle.deliverables if d.status.value in {"PREVIEW", "DRAFT", "IN_REVIEW"}]
    journey.upcoming_decisions = []
    if bundle.vision.primary_destination == ProjectDestination.UNDECIDED and substantive:
        journey.upcoming_decisions.append("project_destination")
    if any(d.status == CreativeDeliverableStatus.IN_REVIEW for d in bundle.deliverables):
        journey.upcoming_decisions.append("deliverable_approval")

    locked = [d for d in bundle.deliverables if d.status == CreativeDeliverableStatus.LOCKED]
    journey.blocked_by = []
    # Screenplay lock blocks rewrite, not progress
    if locked:
        journey.blocked_by.append("locked_deliverables_require_unlock_for_rewrite")

    journey.next_useful_artifact = None
    if stage in {ProductionJourneyStage.INITIAL_IDEA.value, ProductionJourneyStage.DISCOVERY.value}:
        journey.next_useful_artifact = "story_template"
        journey.next_recommended_stage = ProductionJourneyStage.LIVING_BRIEF.value
    elif stage == ProductionJourneyStage.TREATMENT.value:
        journey.next_useful_artifact = "treatment"
        journey.next_recommended_stage = ProductionJourneyStage.OUTLINE.value
    elif stage == ProductionJourneyStage.PITCH_PACKAGE.value:
        journey.next_useful_artifact = "pitch_summary"
    elif approved and stage == ProductionJourneyStage.SCREENPLAY.value:
        journey.next_recommended_stage = ProductionJourneyStage.PRE_PRODUCTION.value

    journey.ownership_resolved_for_current_stage = bool(bundle.collaboration.default_ownership)
    return journey
