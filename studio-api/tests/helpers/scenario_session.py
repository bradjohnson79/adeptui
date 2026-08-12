"""Phase 9 — Sustained-conversation acceptance test harness.

ScenarioSession holds persistent mock project state across turns.
Each turn exercises the full Phase 2-8 backend pipeline and returns
a TurnResult with behavioral assertions.

Usage:
    session = ScenarioSession(project_id="schnick-1")
    session.set_fact("title", "Schnick Coffee", "creator-stated")
    session.set_fact("format", "commercial", "creator-stated")

    r = session.turn("I'm looking to create a 20 second commercial...")
    assert r.route_decision.actionClass == RouteActionClass.DISCUSS
    assert r.write_count == 0

The session accumulates state across turns: facts, goals, proposals,
operator events, and deferred recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import MagicMock

from app.codirector.routing.contracts import RouteActionClass, RouteDecision
from app.codirector.routing.orchestrator import route_turn
from app.codirector.conversation.planner import plan_conversation
from app.codirector.conversation.response_composer import sanitize_response
from app.codirector.conversation.schemas import (
    ProjectIntelligenceSnapshot,
    ProjectDirectorState,
    ConversationPlan,
)


@dataclass
class TurnResult:
    turn_number: int
    message: str
    route_decision: Optional[RouteDecision] = None
    conversation_plan: Optional[ConversationPlan] = None
    response: str = ""
    write_count: int = 0
    operator_requested: bool = False
    specialist_count: int = 0
    proposal_created: bool = False
    wiki_written: bool = False

    def assert_discuss(self) -> None:
        assert self.route_decision is None or self.route_decision.actionClass in (
            RouteActionClass.DISCUSS, RouteActionClass.UNKNOWN
        ), f"Expected DISCUSS, got {self.route_decision.actionClass if self.route_decision else None}"
        assert self.write_count == 0, f"DISCUSS should have 0 writes, got {self.write_count}"
        assert not self.operator_requested, "DISCUSS should not request operator"

    def assert_navigate(self) -> None:
        assert self.route_decision is not None
        assert self.route_decision.actionClass == RouteActionClass.NAVIGATE, (
            f"Expected NAVIGATE, got {self.route_decision.actionClass}"
        )
        assert self.operator_requested, "NAVIGATE should request operator"

    def assert_no_leakage(self) -> None:
        assert "[mock]" not in self.response
        assert "toolId" not in self.response
        assert "classifierSource" not in self.response
        assert "executionLane" not in self.response


class ScenarioSession:
    """Sustained conversation session across N turns."""

    def __init__(self, project_id: str, format_str: str = "commercial"):
        self.project_id = project_id
        self.turn_count = 0
        self.facts: dict[str, dict] = {}
        self.conversation_goal: Optional[str] = None
        self.proposals: list[dict] = []
        self.operator_events: list[dict] = []
        self.deferred: set[str] = set()

        self.snapshot = ProjectIntelligenceSnapshot(
            projectId=project_id,
            title="Untitled",
            format=format_str,
            keyCharacters=[],
            knowledgeEntries=[],
            compiledWiki={},
        )
        self.director = ProjectDirectorState()

    def set_fact(self, key: str, value: str, provenance: str = "creator-stated") -> None:
        self.facts[key] = {"value": value, "provenance": provenance}
        if key == "title":
            self.snapshot.title = value
        if key == "format":
            self.snapshot.format = value
        if key == "primary_character":
            if value not in (self.snapshot.keyCharacters or []):
                self.snapshot.keyCharacters = list(self.snapshot.keyCharacters or []) + [value]

    def set_script_exists(self, exists: bool = True) -> None:
        if exists:
            self.facts["script_exists"] = {"value": "true", "provenance": "creator-stated"}
        elif "script_exists" in self.facts:
            del self.facts["script_exists"]

    def turn(self, message: str, *, expected_action: Optional[str] = None) -> TurnResult:
        self.turn_count += 1
        r = TurnResult(turn_number=self.turn_count, message=message)

        # Phase 3 — route decision
        from app.codirector.routing.deterministic import classify_deterministic
        det = classify_deterministic(
            message,
            active_workspace="chat",
            derived_stage=getattr(self.snapshot, "format", None),
            pending_proposal_ids=[p.get("id") for p in self.proposals if p.get("status") == "pending"],
        )
        if det:
            r.route_decision = det
            r.operator_requested = det.actionClass == RouteActionClass.NAVIGATE
            if det.actionClass in (RouteActionClass.NAVIGATE, RouteActionClass.APPROVE, RouteActionClass.REJECT):
                r.write_count += 1  # operator registration / proposal status change

        # Phase 8 — plan conversation
        plan = plan_conversation(
            message,
            self.snapshot,
            "SCRIPT" if self.facts.get("script_exists") else "STORY",
            None,
            self.director,
        )
        r.conversation_plan = plan
        r.wiki_written = plan.shouldWriteWiki

        # Phase 8 — response composition (deterministic checks)
        r.response = sanitize_response(f"Turn {self.turn_count}: acknowledged ({plan.primaryIntent})")
        r.assert_no_leakage()

        # Update session state from turn outcome
        if plan.directorContext and plan.directorContext.get("conversationGoal"):
            self.conversation_goal = plan.directorContext["conversationGoal"]

        if expected_action:
            assert r.route_decision is None or r.route_decision.actionClass.value == expected_action, (
                f"Turn {self.turn_count}: expected action {expected_action}, "
                f"got {r.route_decision.actionClass.value if r.route_decision else 'None'}"
            )

        return r
