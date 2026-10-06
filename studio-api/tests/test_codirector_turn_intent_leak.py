"""Context leak + turn-intent: internal knowledge must not become the answer."""

from __future__ import annotations

from app.codirector.creator_response_gate import (
    find_internal_product_leak,
    strip_internal_product_leak,
)
from app.codirector.knowledgebase.platform_replies import knowledge_reply
from app.codirector.knowledgebase.retrieve import render_knowledge_context_block, retrieve_knowledge
from app.codirector.routing.turn_intent import classify_turn_intent, is_production_turn, strip_quoted_dialogue

LEAK_PHRASES = (
    "Spatial Map",
    "PoseCraft",
    "Standalone",
    "Image Runtime",
    "Local Video Runtime",
    "Adept is the filmmaking app",
)

SCENE_REVISION = (
    'Change the scene so Cade walks through the corridor and says "Where is the Adept?"'
)
RETRY = "Retry"
PREPARE = (
    "Build a Timeline scene. Cade punches the door. 30 seconds, 2 batches, MiniMax H3."
)


def test_quoted_adept_dialogue_is_not_a_platform_question() -> None:
    residual = strip_quoted_dialogue(SCENE_REVISION)
    assert "Where is the Adept?" not in residual
    kind = classify_turn_intent(SCENE_REVISION, workspace="timeline")
    assert kind == "scene_revision"
    assert is_production_turn(kind)


def test_retry_with_active_production_is_production_retry() -> None:
    kind = classify_turn_intent(RETRY, has_active_production=True)
    assert kind == "production_retry"
    assert is_production_turn(kind)


def test_knowledge_reply_does_not_swallow_scene_revision() -> None:
    from app.codirector.routing.generation_authority import classify_generation_authority
    from app.codirector.routing.unified_intent import classify_intent
    from app.codirector.service import _maybe_platform_knowledge_reply

    assert knowledge_reply(SCENE_REVISION, workspace="timeline") is None
    assert knowledge_reply(PREPARE, workspace="timeline") is None
    assert knowledge_reply(RETRY, workspace="timeline") is None
    assert _maybe_platform_knowledge_reply(SCENE_REVISION, "timeline") is None
    assert _maybe_platform_knowledge_reply(RETRY, "timeline") is None
    assert classify_intent(PREPARE, {}).capability == "timeline.prepare_scene"
    authority = classify_generation_authority(PREPARE)
    assert authority is not None and authority.capability == "timeline.prepare_scene"


def test_retrieve_excludes_stale_platform_packets() -> None:
    retrieval = retrieve_knowledge(
        "Adept is the filmmaking app. Spatial Map PoseCraft Image Runtime",
        workspace="timeline",
    )
    assert "adept-platform" not in retrieval.doc_ids
    assert "adept-system-map" not in retrieval.doc_ids
    assert "spatial-map" not in retrieval.doc_ids
    assert "posecraft" not in retrieval.doc_ids
    block = render_knowledge_context_block(SCENE_REVISION, workspace="timeline")
    for phrase in LEAK_PHRASES:
        assert phrase not in (block or "")


def test_internal_leak_gate_strips_stale_guidance() -> None:
    dirty = (
        "Adept is the filmmaking app. Image Runtime and Local Video Runtime work underneath. "
        "Spatial Map is shelved. PoseCraft is Standalone. Cade walks the corridor."
    )
    cleaned = strip_internal_product_leak(dirty, user_message=SCENE_REVISION)
    for phrase in LEAK_PHRASES:
        assert phrase not in cleaned
    assert "Cade walks the corridor" in cleaned
    assert find_internal_product_leak(dirty, user_message=SCENE_REVISION)


def test_explicit_platform_question_still_redirects_shelf() -> None:
    reply = knowledge_reply("What does Spatial Map do?")
    assert reply
    low = reply.lower()
    assert "environment creator" in low
    assert "spatial map" not in low
    assert "posecraft" not in low
