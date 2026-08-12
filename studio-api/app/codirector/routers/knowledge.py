"""Knowledge Card API — creator-controlled conversation-to-project bridge."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db import get_db
from ..story_intelligence.knowledge_card import (
    CardType,
    add_card_to_project,
    dismiss_card,
    get_card,
    get_project_cards,
    update_card,
)

router = APIRouter(prefix="/knowledge-cards", tags=["knowledge-cards"])


@router.get("/video-generators")
def list_video_generators() -> list[dict]:
    """Return available video generators from runtime detection.

    Populates the Create Project / Project Settings dropdown.
    'automatic' is always available as the default.
    Local generators are detected from the video runtime.
    """
    generators: list[dict] = [
        {"id": "automatic", "label": "Automatic / Best Available", "available": True},
    ]

    # Check local video runtime gate for installed generators
    try:
        from ...video_runtime.api import wave6_gate
        gate = wave6_gate()
        generators.append({"id": "minimax-h3-i2v-local", "label": "MiniMax H3 (Local)", "available": bool(gate.get("wave6WiringUnlocked") or gate.get("engineReady"))})
    except Exception:
        generators.append({"id": "minimax-h3-i2v-local", "label": "MiniMax H3 (Local)", "available": False})

    try:
        from ...video_runtime.api import wave6_gate
        gate = wave6_gate()
        for engine_id in gate.get("availableEngines", []):
            label = str(engine_id).replace("_", " ").replace("-", " ").title()
            generators.append({"id": str(engine_id), "label": f"{label} (Local)", "available": True})
    except Exception:
        pass

    try:
        from ...fal_catalog import fal_catalog
        catalog = fal_catalog()
        for item in catalog:
            if item.get("kind") == "video" or "video" in (item.get("name") or "").lower():
                vid = item.get("id") or item.get("name", "api-video")
                label = item.get("label") or item.get("name", vid)
                available = item.get("available") or item.get("configured", False)
                generators.append({"id": f"api:{vid}", "label": f"{label} (API)", "available": bool(available)})
    except Exception:
        pass

    return generators


class CardActionResponse(BaseModel):
    ok: bool
    cardId: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


class UpdateCardBody(BaseModel):
    title: Optional[str] = None
    fields: Optional[dict[str, Any]] = None
    summary: Optional[str] = None


@router.post("/{card_id}/add")
def add_card(card_id: str, project_id: str, db: Session = Depends(get_db)) -> CardActionResponse:
    """Add approved card payload to authoritative project system."""
    card = add_card_to_project(db, project_id, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found or already added/dismissed")
    if card.status == "FAILED":
        return CardActionResponse(ok=False, cardId=card_id, status="FAILED", error=card.error)
    return CardActionResponse(ok=True, cardId=card_id, status=card.status.value)


@router.post("/{card_id}/dismiss")
def dismiss_card_route(card_id: str) -> CardActionResponse:
    """Dismiss a Knowledge Card — zero authoritative mutation."""
    ok = dismiss_card(card_id)
    return CardActionResponse(ok=ok, cardId=card_id, status="DISMISSED" if ok else "NOT_FOUND")


@router.post("/{card_id}/edit")
def edit_card(card_id: str, body: UpdateCardBody) -> CardActionResponse:
    """Edit card fields before Add."""
    card = update_card(card_id, title=body.title, fields=body.fields, summary=body.summary)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found or already added/dismissed")
    return CardActionResponse(ok=True, cardId=card_id, status=card.status.value)


@router.get("/project/{project_id}")
def list_project_cards(project_id: str) -> list[dict[str, Any]]:
    """List active (non-dismissed, non-added) cards for a project."""
    cards = get_project_cards(project_id)
    return [
        {
            "cardId": c.card_id,
            "cardType": c.card_type.value,
            "title": c.title,
            "fields": c.fields,
            "summary": c.summary,
            "status": c.status.value,
            "createdAt": c.created_at,
        }
        for c in cards
    ]
