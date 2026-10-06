"""The model reads the turn. The server only admits an explicit command or a validated decision."""

from pathlib import Path

from app.codirector.durable.admission import (
    classify_turn_mode,
    named_surface,
    resolve_admitted_tool,
    validate_semantic_decision,
)
from app.codirector.durable.agent import _operation_tool
from app.codirector.durable.authority import mode_allows_tool

_CREATE = {"create_scene", "character_creator.create_from_brief", "timeline.propose_add_prompt_segment"}


def _resolved(text: str, raw: dict | None = None, allowed: set[str] | None = None):
    choices = allowed or _CREATE
    return resolve_admitted_tool(
        text,
        raw,
        allowed=choices,
        fallback=_operation_tool(text, choices),
    )


def test_prompt_lets_read_and_navigate_call_tools():
    source = Path("app/codirector/durable/agent.py").read_text(encoding="utf-8")
    assert "READ, or NAVIGATE, tool_id must be null" not in source
    assert "You may call one admitted read-only tool" in source
    assert "You may call one admitted navigation tool" in source
    assert "tool_id must be null" in source


def test_pure_discussion_does_not_select_a_production_tool():
    text = "How would you make Cade seem more suspicious without changing the scene?"
    decision = _resolved(text)
    assert classify_turn_mode(text) == "CONVERSATION"
    assert decision.mode == "CONVERSATION"
    assert decision.tool_id is None


def test_contextual_correction_stays_a_conversation():
    first = "I think Cade should seem protective."
    second = "Actually, change one thing — make it ambiguous."
    assert classify_turn_mode(first) == "CONVERSATION"
    assert classify_turn_mode(second) == "CONVERSATION"
    decision = _resolved(
        second,
        {"mode": "CONVERSATION", "confidence": "high", "tool_id": "create_scene", "reply": "Keep it ambiguous."},
    )
    assert decision.mode == "CONVERSATION"
    assert decision.tool_id is None


def test_read_allows_a_read_tool_and_refuses_a_mutation():
    text = "What characters are in this project?"
    assert classify_turn_mode(text) == "READ"
    decision = validate_semantic_decision(
        text,
        {
            "mode": "READ",
            "confidence": "high",
            "tool_id": "list_character_profiles",
            "reply": "I'll look up the characters.",
        },
    )
    assert decision.mode == "READ"
    assert decision.tool_id == "list_character_profiles"
    assert mode_allows_tool("READ", kind="read", tool_id="list_character_profiles")
    assert not mode_allows_tool("READ", kind="mutating", tool_id="create_scene")
    assert not mode_allows_tool("CONVERSATION", kind="read", tool_id="list_character_profiles")


def test_navigate_allows_navigation_and_refuses_a_mutation():
    text = "Open Character Creator."
    assert classify_turn_mode(text) == "NAVIGATE"
    assert mode_allows_tool("NAVIGATE", kind="read", tool_id="workspace.open_image_generator")
    assert not mode_allows_tool("NAVIGATE", kind="mutating", tool_id="character_creator.create_from_brief")
    decision = validate_semantic_decision(
        text,
        {"mode": "NAVIGATE", "confidence": "high", "tool_id": "workspace.open_image_generator", "reply": "Opening it."},
    )
    assert decision.mode == "NAVIGATE"
    assert decision.tool_id == "workspace.open_image_generator"


def test_explicit_proposal_is_not_a_mutation():
    text = "Prepare a 10-second Timeline prompt, but don't place it yet."
    assert classify_turn_mode(text) == "PROPOSE"
    decision = validate_semantic_decision(
        text,
        {"mode": "MUTATE", "confidence": "high", "tool_id": "timeline.propose_add_prompt_segment"},
    )
    assert decision.mode == "PROPOSE"
    assert decision.constraints.no_execute is True


def test_explicit_character_create_admits_the_create_tool():
    text = "Create a new character named Lar in Character Creator."
    assert classify_turn_mode(text) == "MUTATE"
    assert named_surface(text) == "character"
    decision = _resolved(text)
    assert decision.mode == "MUTATE"
    assert decision.tool_id == "character_creator.create_from_brief"
    assert mode_allows_tool("MUTATE", kind="mutating", tool_id="character_creator.create_from_brief")


def test_ambiguous_words_do_not_mutate_without_a_confident_reading():
    phrases = (
        "change one thing",
        "use Cade",
        "add more tension",
        "move this later",
        "show me the scene",
    )
    for phrase in phrases:
        decision = _resolved(phrase, {"mode": "MUTATE", "confidence": "low", "tool_id": "create_scene"})
        assert decision.mode == "CONVERSATION", phrase
        assert decision.tool_id is None, phrase
        assert classify_turn_mode(phrase) != "MUTATE"


def test_same_words_follow_the_model_when_the_reading_is_confident():
    discussion = _resolved(
        "Maybe Cade should sit nearer the window.",
        {"mode": "CONVERSATION", "confidence": "high", "reply": "That would soften the shot."},
    )
    command = _resolved(
        "Move Cade nearer the window in Timeline.",
        {
            "mode": "MUTATE",
            "confidence": "high",
            "surface": "TIMELINE",
            "tool_id": "timeline.propose_add_prompt_segment",
            "entities": {"characters": ["Cade"]},
        },
    )
    assert discussion.mode == "CONVERSATION"
    assert discussion.tool_id is None
    assert command.mode == "MUTATE"
    assert command.tool_id == "timeline.propose_add_prompt_segment"
    assert command.entities.characters == ["Cade"]
    assert classify_turn_mode("Move Cade nearer the window in Timeline.") != "MUTATE"


def test_explicit_scene_command_falls_back_when_the_model_selects_nothing():
    text = "Create a new scene in Timeline."
    assert _operation_tool(text, {"create_scene"}) == "create_scene"
    decision = _resolved(text, None, {"create_scene"})
    assert decision.mode == "MUTATE"
    assert decision.tool_id == "create_scene"


def test_discussion_does_not_invent_a_mutation_when_the_model_selects_nothing():
    text = "I think this scene should feel different."
    assert _operation_tool(text, {"create_scene", "set_scene_prompt"}) == ""
    decision = _resolved(text, None, {"create_scene", "set_scene_prompt"})
    assert decision.mode == "CONVERSATION"
    assert decision.tool_id is None


def test_named_surface_alone_does_not_choose_a_tool():
    text = "Use Character Creator."
    assert named_surface(text) == "character"
    assert classify_turn_mode(text) != "MUTATE"
    assert _operation_tool(text, {"character_creator.create_from_brief", "character_creator.propose_visual_sheet"}) == ""


def test_image_surface_alone_does_not_choose_a_still():
    assert _operation_tool("Use Image Generator.", {"propose_image_generate"}) == ""
    still = "Use Image Generator to create a still."
    assert classify_turn_mode(still) == "MUTATE"
    assert _operation_tool(still, {"propose_image_generate"}) == "propose_image_generate"
