"""Knowledge Card — creator-controlled conversation-to-project bridge.

Generic conversation must NOT create canonical project records.
Knowledge Cards are proposals. Add makes the information project truth.
Only then do Wiki/Production State projections reflect it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy.orm import Session


class CardType(str, Enum):
    STORY = "STORY"
    CHARACTER = "CHARACTER"
    VISION = "VISION"
    PROJECT_STYLE = "PROJECT_STYLE"


class CardStatus(str, Enum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    EDITING = "EDITING"
    APPROVED_FOR_ADD = "APPROVED_FOR_ADD"
    ADDED = "ADDED"
    DISMISSED = "DISMISSED"
    FAILED = "FAILED"


@dataclass
class KnowledgeCard:
    card_id: str = field(default_factory=lambda: f"kc_{uuid.uuid4().hex[:12]}")
    project_id: str = ""
    card_type: CardType = CardType.STORY
    title: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    summary: Optional[str] = None
    source_refs: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    provenance: str = "creator-stated"  # Phase 2 provenance taxonomy
    confidence: float = 1.0
    target_system: Optional[str] = None  # e.g. "character_identity", "story_intelligence", "project_vision"
    status: CardStatus = CardStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None


# Session-scoped card store (NOT persisted to project database — ephemeral)
_cards: dict[str, KnowledgeCard] = {}


def create_card(
    project_id: str,
    card_type: CardType,
    title: str,
    fields: dict[str, Any],
    *,
    summary: Optional[str] = None,
    source_refs: Optional[list[str]] = None,
    attachments: Optional[list[dict[str, Any]]] = None,
) -> KnowledgeCard:
    """Create a Knowledge Card candidate. Card is DRAFT until creator reviews."""
    card = KnowledgeCard(
        project_id=project_id,
        card_type=card_type,
        title=title,
        fields=fields,
        summary=summary or "",
        source_refs=source_refs or [],
        attachments=attachments or [],
        status=CardStatus.DRAFT,
    )
    _cards[card.card_id] = card
    return card


def get_card(card_id: str) -> Optional[KnowledgeCard]:
    return _cards.get(card_id)


def get_project_cards(project_id: str) -> list[KnowledgeCard]:
    return [c for c in _cards.values() if c.project_id == project_id and c.status not in (CardStatus.DISMISSED, CardStatus.ADDED, CardStatus.FAILED)]


def update_card(card_id: str, *, title: Optional[str] = None, fields: Optional[dict[str, Any]] = None, summary: Optional[str] = None, attachments: Optional[list[dict]] = None) -> Optional[KnowledgeCard]:
    """Edit card fields before Add. Does NOT change card_id or type."""
    card = _cards.get(card_id)
    if not card or card.status in (CardStatus.ADDED, CardStatus.DISMISSED):
        return None
    if title is not None:
        card.title = title
    if fields is not None:
        card.fields = dict(fields)
    if summary is not None:
        card.summary = summary
    if attachments is not None:
        card.attachments = list(attachments)
    card.status = CardStatus.EDITING
    card.updated_at = datetime.utcnow().isoformat()
    return card


def dismiss_card(card_id: str) -> bool:
    """Dismiss removes candidate. Zero authoritative mutation."""
    card = _cards.get(card_id)
    if not card:
        return False
    card.status = CardStatus.DISMISSED
    card.updated_at = datetime.utcnow().isoformat()
    return True


def add_card_to_project(
    db: Session,
    project_id: str,
    card_id: str,
) -> Optional[KnowledgeCard]:
    """Add approved card payload to authoritative project system.

    Card payload is pinned at creation — no hidden recomputation at Add time.
    Routes to the appropriate authoritative system based on card type.
    """
    card = _cards.get(card_id)
    if not card or card.status in (CardStatus.ADDED, CardStatus.DISMISSED):
        return None

    payload = dict(card.fields)
    try:
        if card.card_type == CardType.CHARACTER:
            _add_character(db, project_id, card)
        elif card.card_type == CardType.STORY:
            _add_story(db, project_id, card)
        elif card.card_type == CardType.VISION:
            _add_vision(db, project_id, card)
        elif card.card_type == CardType.PROJECT_STYLE:
            _add_style(db, project_id, card)
        card.status = CardStatus.ADDED
        card.updated_at = datetime.utcnow().isoformat()
        _invalidate_after_add(db, project_id, card.card_type)
        return card
    except Exception as exc:
        card.status = CardStatus.FAILED
        card.error = str(exc)
        card.updated_at = datetime.utcnow().isoformat()
        return card


def _add_character(db: Session, project_id: str, card: KnowledgeCard) -> None:
    """Route Character Card to Character Identity."""
    fields = card.fields
    try:
        from app.character_identity.schemas import CharacterProfileCreate, CharacterProfileUpdate
        from app.character_identity.service import create_profile, list_profiles, update_profile

        profiles = list_profiles(db, project_id)
        existing = [p for p in profiles if p.name.lower() == card.title.lower()] if profiles else []
        if existing:
            update_profile(
                db,
                project_id,
                existing[0].id,
                CharacterProfileUpdate(personality_traits=fields.get("personality", [])),
            )
        else:
            create_profile(
                db,
                project_id,
                CharacterProfileCreate(
                    name=card.title,
                    role=fields.get("role", "character"),
                    species_or_type=fields.get("species", ""),
                    description=fields.get("description", ""),
                ),
            )
    except ImportError:
        _add_to_snapshot_field(db, project_id, "keyCharacters", card.title)


def _add_story(db: Session, project_id: str, card: KnowledgeCard) -> None:
    """Route Story Card to compiledWiki/storySummary."""
    from app.codirector.conversation.snapshot import load_snapshot, save_snapshot

    snapshot = load_snapshot(db, project_id)
    compiled = getattr(snapshot, "compiledWiki", None) or {}
    if isinstance(compiled, dict):
        if "storySummary" not in compiled:
            compiled["storySummary"] = {}
        for key, value in card.fields.items():
            if value:
                compiled["storySummary"][key] = str(value)
        snapshot.compiledWiki = compiled
        save_snapshot(db, snapshot)


def _add_vision(db: Session, project_id: str, card: KnowledgeCard) -> None:
    """Route Vision Card to project state."""
    _add_to_snapshot_field(db, project_id, "vision", card.fields)


def _add_style(db: Session, project_id: str, card: KnowledgeCard) -> None:
    """Route Style Card to project state."""
    _add_to_snapshot_field(db, project_id, "style", card.fields)


def _add_to_snapshot_field(db: Session, project_id: str, field: str, value: Any) -> None:
    from app.codirector.conversation.snapshot import load_snapshot, save_snapshot

    snapshot = load_snapshot(db, project_id)
    setattr(snapshot, field, value)
    save_snapshot(db, snapshot)


def _list_profiles(db: Session, project_id: str) -> list[Any]:
    try:
        from app.character_identity.service import list_profiles

        return list_profiles(db, project_id)
    except ImportError:
        return []


def _invalidate_after_add(db: Session, project_id: str, card_type: CardType) -> None:
    """Invalidate Production State domains after successful Add."""
    try:
        from app.codirector.production_state.invalidation import invalidate_production_state

        domain_map = {
            CardType.CHARACTER: {"CHARACTERS"},
            CardType.STORY: {"SCRIPT", "WIKI"},
            CardType.VISION: {"PROJECT"},
            CardType.PROJECT_STYLE: {"PROJECT"},
        }
        domains = domain_map.get(card_type, set())
        if domains:
            invalidate_production_state(db, project_id, affected_domains=domains)
    except Exception:
        pass


def generate_card_from_conversation(
    card_type: CardType,
    title: str,
    conversation_context: dict[str, Any],
) -> KnowledgeCard:
    """Generate a Knowledge Card candidate from structured conversation context.

    The card payload is pinned at generation time. Add commits the exact same payload.
    No hidden recomputation.
    """
    fields: dict[str, Any] = {}
    source_refs: list[str] = conversation_context.get("sourceRefs", [])
    attachments: list[dict] = conversation_context.get("attachments", [])

    if card_type == CardType.CHARACTER:
        fields = {
            "role": conversation_context.get("role", "character"),
            "species": conversation_context.get("species", ""),
            "description": conversation_context.get("description", ""),
            "personality": conversation_context.get("personality", []),
        }
    elif card_type == CardType.STORY:
        fields = {
            "premise": conversation_context.get("premise", ""),
            "protagonist": conversation_context.get("protagonist", ""),
            "conflict": conversation_context.get("conflict", ""),
            "tone": conversation_context.get("tone", ""),
            "format": conversation_context.get("format", ""),
        }
    elif card_type == CardType.VISION:
        fields = {
            "audience_feeling": conversation_context.get("audience_feeling", ""),
            "creative_objective": conversation_context.get("creative_objective", ""),
            "thematic_intent": conversation_context.get("thematic_intent", ""),
        }
    elif card_type == CardType.PROJECT_STYLE:
        fields = {
            "visual_style": conversation_context.get("visual_style", ""),
            "genre": conversation_context.get("genre", ""),
            "tone": conversation_context.get("tone", ""),
            "lighting": conversation_context.get("lighting", ""),
            "color_palette": conversation_context.get("color_palette", ""),
        }

    return create_card(
        project_id=conversation_context.get("project_id", ""),
        card_type=card_type,
        title=title,
        fields={k: v for k, v in fields.items() if v},
        summary=conversation_context.get("summary"),
        source_refs=source_refs,
        attachments=attachments,
    )
