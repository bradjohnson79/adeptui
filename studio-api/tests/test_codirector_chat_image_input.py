"""Compact Co-Director image-input / vision context tests. Do not edit certified probes."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.codirector.context_enrichment import attachment_context_block
from app.codirector.vision.turn import ChatVisionTurn
from app.db import Asset, Base, Project
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_attachment_context_includes_vision_facts_not_denial():
    db = _db()
    pid = "p-vision"
    db.add(Project(id=pid, name="Vision", description=""))
    db.add(
        Asset(
            id="a1",
            project_id=pid,
            kind="image",
            tag="Cafe lighting.jpg",
            filename="Cafe lighting.jpg",
            path="cafe-lighting.jpg",
        )
    )
    db.commit()
    block = attachment_context_block(
        db,
        project_id=pid,
        attachment_ids=["a1"],
        vision_block="=== VISION FACTS (pixels were read by Adept vision) ===\nWarm practicals.",
    )
    assert "VISION FACTS" in block
    assert "Warm practicals" in block
    assert "not automatically run" not in block.lower()
    assert "was not performed" not in block.lower()
    assert "I cannot access" not in block.lower()


def test_prepare_chat_request_includes_vision_facts(monkeypatch):
    from app.codirector.service import _prepare_chat_request

    db = _db()
    pid = "p-prep"
    db.add(Project(id=pid, name="Prep", description=""))
    db.add(
        Asset(
            id="img1",
            project_id=pid,
            kind="image",
            tag="cafe.jpg",
            filename="cafe.jpg",
            path="cafe.jpg",
        )
    )
    db.commit()

    async def _fake_vision(*_args, **_kwargs):
        return ChatVisionTurn(
            ok=True,
            facts="Warm practicals on wood.",
            context_block="=== VISION FACTS (pixels were read by Adept vision) ===\nWarm practicals on wood.",
            vision_trace={"hasImages": True, "assetIds": ["img1"]},
        )

    monkeypatch.setattr("app.codirector.vision.turn.run_chat_vision_turn", _fake_vision)
    monkeypatch.setattr(
        "app.codirector.service.get_provider",
        lambda _id=None: SimpleNamespace(id="ollama", display_name="Ollama"),
    )

    async def _run():
        return await _prepare_chat_request(
            db,
            messages=[{"role": "user", "content": "What do you think of this image?"}],
            project_id=pid,
            scene_id=None,
            mode="chat",
            model="mock",
            provider_id="mock",
            request_id="vision-compact",
            attachment_ids=["img1"],
        )

    _provider, chat_request, _manifest = asyncio.run(_run())
    assert "VISION FACTS" in (chat_request.project_context or "")
    system = next(m for m in chat_request.messages if m.get("role") == "system")
    assert "VISION FACTS" in system["content"]
    assert "not automatically run" not in system["content"].lower()
    assert "was not performed" not in system["content"].lower()
    assert chat_request.vision_turn is not None
    assert chat_request.vision_turn.ok is True
