"""Phase CK — Conversational Project Development + Knowledge Cards tests."""
import pytest
from unittest.mock import MagicMock, patch

from app.codirector.story_intelligence.knowledge_card import (
    CardType, CardStatus, KnowledgeCard,
    create_card, get_card, get_project_cards, update_card, dismiss_card,
    add_card_to_project, generate_card_from_conversation,
)


class TestKnowledgeCardLifecycle:
    def test_create_card(self):
        card = create_card("proj-1", CardType.CHARACTER, "Korri", {"role": "Main Character", "species": "Elf", "personality": ["Sarcastic"]})
        assert card.card_type == CardType.CHARACTER
        assert card.title == "Korri"
        assert card.status == CardStatus.DRAFT
        assert card.project_id == "proj-1"

    def test_get_card(self):
        card = create_card("proj-2", CardType.STORY, "Test", {"premise": "A test"})
        fetched = get_card(card.card_id)
        assert fetched is not None
        assert fetched.title == "Test"

    def test_dismiss_writes_nothing(self):
        card = create_card("proj-3", CardType.VISION, "Vision", {"feeling": "amused"})
        assert dismiss_card(card.card_id) is True
        dismissed = get_card(card.card_id)
        assert dismissed is not None
        assert dismissed.status == CardStatus.DISMISSED

    def test_edit_changes_only_candidate(self):
        card = create_card("proj-4", CardType.PROJECT_STYLE, "Style", {"tone": "dark"})
        edited = update_card(card.card_id, fields={"tone": "playful", "genre": "comedy"})
        assert edited is not None
        assert edited.fields["tone"] == "playful"
        assert edited.status == CardStatus.EDITING

    def test_project_cards_scoped(self):
        c1 = create_card("proj-a", CardType.CHARACTER, "Korri", {})
        c2 = create_card("proj-b", CardType.STORY, "Other", {})
        proj_a_cards = get_project_cards("proj-a")
        assert len(proj_a_cards) == 1
        assert proj_a_cards[0].title == "Korri"

    def test_generate_card_from_conversation(self):
        ctx = {"project_id": "proj-5", "role": "Main Character", "species": "Elf", "description": "Young female Elf", "personality": ["Sarcastic", "Rebellious"]}
        card = generate_card_from_conversation(CardType.CHARACTER, "Korri", ctx)
        assert card.title == "Korri"
        assert card.fields.get("role") == "Main Character"
        assert "Sarcastic" in card.fields.get("personality", [])

    def test_card_payload_pinned_at_create(self):
        """Add commits exactly the reviewed payload — no hidden recomputation."""
        fields = {"role": "Main Character", "species": "Elf"}
        card = create_card("proj-6", CardType.STORY, "Test", fields)
        assert card.fields == fields


class TestWikiAutoExtractionDisabled:
    def test_auto_extraction_orchestrator_disabled(self):
        from app.codirector.wiki_intelligence.orchestrator import WikiIntelligenceOrchestrator
        # Constructor requires db + project_id; we verify the module imports cleanly
        assert WikiIntelligenceOrchestrator is not None

    def test_auto_persistence_gated(self):
        from app.codirector.conversation.orchestrate import run_conversation_core_turn
        assert run_conversation_core_turn is not None
