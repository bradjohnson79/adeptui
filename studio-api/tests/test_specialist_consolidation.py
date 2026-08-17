"""Phase 7 (CDX-086 / CDX-087 / CDX-090) — specialist consolidation tests.

Covers:
- CDX-086: hard max THREE specialists everywhere — foundation routing
  (property over every intent/profile/keyword combination), wiki assignment
  with six domains, conversation bundles.
- CDX-087: single canonical roster — foundation roster entries and
  conversation candidates resolve read-through against the canonical
  intelligence SpecialistRegistry instead of separate id vocabularies.
- CDX-090: foundation findings carry source="heuristic" and the
  limited-analysis assumption so they are never presented as LLM analysis.
"""

from __future__ import annotations

import pytest

from app.codirector.foundation.contracts import SpecialistRequest
from app.codirector.foundation.creative.routing import (
    MAX_SPECIALISTS,
    _INTENT_MAP,
    _KEYWORD_MAP,
    _PROFILE_MAP,
    select_specialists,
)
from app.codirector.foundation.creative.roster import (
    CANONICAL_ALIASES,
    canonical_specialist_id,
    is_known_specialist,
    unresolved_canonical_aliases,
)
from app.codirector.foundation.creative.runners import (
    HeuristicSpecialistResult,
    run_specialist,
)
from app.codirector.foundation.pipeline import (
    FOUNDATION_PROGRESS_LABEL,
    run_foundation_creative_pass,
)
from app.codirector.intelligence.specialist_registry import SpecialistRegistry
from app.codirector.intelligence.specialist_runner import LIMITED_ANALYSIS_ASSUMPTION
from app.codirector.wiki_intelligence.assignment import assign_specialists_for_domains


@pytest.fixture(scope="module")
def registry() -> SpecialistRegistry:
    return SpecialistRegistry()


# ---------------------------------------------------------------------------
# CDX-086 — hard max THREE specialists everywhere
# ---------------------------------------------------------------------------


class TestHardMaxThree:
    """No selection authority may return more than three specialists."""

    def test_foundation_routing_max_three_for_all_intents(self):
        for intents, _ in _INTENT_MAP:
            for intent in intents:
                selected = select_specialists(
                    "staging shot camera lighting mood continuity emotion",
                    intent,
                    ["animation-series"],
                )
                assert len(selected) <= MAX_SPECIALISTS, (intent, selected)

    def test_foundation_routing_max_three_for_all_keyword_groups(self):
        for keywords, _ in _KEYWORD_MAP:
            selected = select_specialists(
                " ".join(keywords),
                "develop_concept",
                ["horror-short"],
            )
            assert len(selected) <= MAX_SPECIALISTS, (keywords, selected)

    def test_foundation_routing_max_three_for_all_profiles(self):
        for profile_keywords, _ in _PROFILE_MAP:
            selected = select_specialists("", "develop_concept", [profile_keywords[0]])
            assert len(selected) <= MAX_SPECIALISTS, (profile_keywords, selected)

    def test_foundation_routing_adversarial_message_still_capped(self):
        # Every signal group fires at once — the bundle must still cap at 3.
        message = (
            "storyboard camera staging light mood edit cut sound music continuity "
            + "character hero world location performance dialogue review risk emotion tone"
        )
        profiles = [keywords[0] for keywords, _ in _PROFILE_MAP]
        for intents, _ in _INTENT_MAP:
            for intent in intents:
                selected = select_specialists(message, intent, profiles)
                assert len(selected) <= MAX_SPECIALISTS, (intent, selected)

    def test_wiki_assignment_six_domains_max_three(self):
        domains = ["characters", "locations", "story", "world", "timeline", "audio"]
        assignment = assign_specialists_for_domains(project_id="p1", domains=domains)
        assert len(assignment.selectedSpecialists) <= 3

    def test_wiki_assignment_explicit_larger_max_is_clamped(self):
        domains = ["characters", "locations", "story", "world", "timeline", "audio"]
        assignment = assign_specialists_for_domains(
            project_id="p1",
            domains=domains,
            max_specialists=8,
        )
        assert len(assignment.selectedSpecialists) <= 3

    def test_conversation_bundles_never_exceed_three(self):
        from app.codirector.conversation.orchestrate import _CONVERSATION_SPECIALIST_CANDIDATES

        assert _CONVERSATION_SPECIALIST_CANDIDATES
        for intent, ids in _CONVERSATION_SPECIALIST_CANDIDATES.items():
            # Conversation bundles are pairs today (<= 2); hard max is 3.
            assert len(ids) <= 3, (intent, ids)


# ---------------------------------------------------------------------------
# CDX-087 — single canonical roster (read-through)
# ---------------------------------------------------------------------------


class TestSingleCanonicalRoster:
    """Foundation and conversation vocabularies resolve through SpecialistRegistry."""

    def test_registry_is_the_single_canonical_source(self, registry):
        assert len(registry.ids()) >= 20

    def test_foundation_aliases_resolve_through_registry(self, registry):
        assert CANONICAL_ALIASES, "expected declared canonical aliases"
        for foundation_id, canonical_id in CANONICAL_ALIASES.items():
            assert is_known_specialist(foundation_id)
            resolved = canonical_specialist_id(foundation_id, registry)
            assert resolved == canonical_id, foundation_id
            assert resolved in registry.ids()

    def test_no_unresolved_canonical_aliases(self):
        assert unresolved_canonical_aliases() == []

    def test_conversation_candidates_resolve_through_registry(self, registry):
        from app.codirector.conversation.orchestrate import conversation_specialist_candidates

        candidates = conversation_specialist_candidates()
        assert candidates, "expected at least one conversation candidate"
        for candidate in candidates:
            assert candidate in registry.ids(), candidate

    def test_conversation_resolver_reads_through_registry(self, registry):
        from app.codirector.conversation.foundation.schemas import IntentType
        from app.codirector.conversation.orchestrate import resolve_conversation_specialist_candidates

        for intent in (IntentType.REQUEST_ACTION, IntentType.REQUEST_PLAN, IntentType.REQUEST_FEEDBACK):
            resolved = resolve_conversation_specialist_candidates(intent)
            assert resolved, intent
            for sid in resolved:
                assert sid in registry.ids(), sid


# ---------------------------------------------------------------------------
# CDX-090 — foundation findings are labeled heuristic
# ---------------------------------------------------------------------------


class TestHeuristicLabeling:
    """Foundation path findings must not masquerade as LLM specialist work."""

    def test_run_specialist_findings_carry_heuristic_source(self):
        result = run_specialist(
            SpecialistRequest(
                specialistId="story_architect",
                projectId="p1",
                userMessage="Give me a clear premise turn.",
                intent="develop_concept",
            )
        )
        assert isinstance(result, HeuristicSpecialistResult)
        assert result.source == "heuristic"
        assert any(
            isinstance(a, str) and a.startswith(LIMITED_ANALYSIS_ASSUMPTION[:24])
            for a in result.assumptions
        )

    def test_foundation_pass_findings_carry_heuristic_source(self):
        findings, review, _refs = run_foundation_creative_pass(
            project_id="p1",
            user_message="Help me develop the premise and lead character for Episode 1.",
            intent_kind="develop_concept",
        )
        assert findings
        assert review is not None
        for finding in findings:
            assert isinstance(finding, HeuristicSpecialistResult)
            assert finding.source == "heuristic", finding.specialistId

    def test_foundation_progress_label_is_heuristic(self):
        assert FOUNDATION_PROGRESS_LABEL == "Heuristic creative review"

    def test_heuristic_findings_cap_synthesis_confidence(self):
        # Reuse the honest-labeling machinery: a heuristic-only finding (no
        # blockers) must cap synthesis confidence instead of reading as
        # validated LLM analysis.
        from app.codirector.intelligence.schemas import IntentClassification
        from app.codirector.intelligence.synthesis import SynthesisEngine

        finding = run_specialist(
            SpecialistRequest(
                specialistId="story_architect",
                projectId="p1",
                userMessage="Give me a clear premise turn.",
                intent="develop_concept",
            )
        )
        intent = IntentClassification(primaryIntent="develop_concept")
        result = SynthesisEngine().synthesize(
            user_message="Give me a clear premise turn",
            intent=intent,
            findings=[finding],
        )
        assert result.confidence <= 0.55
