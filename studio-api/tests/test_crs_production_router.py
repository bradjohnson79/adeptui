"""Narrow CRS production-router tests. No live generate. No :8758 bounce."""

from __future__ import annotations

from inspect import signature

from app.character_identity.visual_sheet import start_visual_sheet_generation, _coerce_single_crs_sources
from app.codirector.capabilities.registry import get_capability
from app.codirector.conversation.foundation.intent import analyze_intent
from app.codirector.conversation.foundation.schemas import IntentType
from app.codirector.conversation.foundation.speech_act import (
    CRS_CAPABILITY_ID,
    CRS_CREATE_TOOL,
    is_crs_create_action,
    resolve_production_action,
)
from app.codirector.routing.deterministic import classify_deterministic
from app.codirector.routing.contracts import RouteActionClass
from app.codirector.routing.unified_intent import (
    DispatchStrategy,
    UnifiedIntentKind,
    _resolve_capability,
    classify_intent,
)
from app.codirector.tools.handlers.character_creator import _crs_generator_sources


def test_create_korris_crs_is_not_unknown() -> None:
    intent = analyze_intent("Create Korri's CRS")
    assert intent.primary_intent == IntentType.REQUEST_ACTION
    assert intent.primary_intent != IntentType.UNKNOWN
    assert intent.should_use_tools is True


def test_create_korris_crs_is_visual_sheet_not_scene_or_ers() -> None:
    utterance = "Create Korri's CRS"
    action = resolve_production_action(utterance)
    assert is_crs_create_action(action)
    cap, tools = _resolve_capability(utterance)
    assert cap == "character.generate_visual_sheet"
    assert cap not in {"ers.generate", "scene.generate", "image.generate"}
    decision = classify_deterministic(utterance)
    assert decision.actionClass == RouteActionClass.EXECUTE_PRODUCTION
    assert decision.target == "character.generate_visual_sheet"
    unified = classify_intent(utterance, route_decision=decision, foundation_intent=analyze_intent(utterance))
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "character.generate_visual_sheet"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC


def test_character_generate_visual_sheet_is_registered() -> None:
    cap = get_capability("character.generate_visual_sheet")
    assert cap is not None
    assert "character_creator.propose_visual_sheet" in cap.tool_ids
    assert CRS_CAPABILITY_ID == "character.generate_visual_sheet"
    assert CRS_CREATE_TOOL == "character_creator.propose_visual_sheet"


def test_propose_extras_default_off() -> None:
    sig = signature(start_visual_sheet_generation)
    assert sig.parameters["include_details"].default is False
    assert sig.parameters["include_performance"].default is False
    sources = _crs_generator_sources({})
    assert sources["local"][0]["family"] == "auto"
    assert sources["local"][0]["family"] != "qwen2512"


def test_auto_is_not_hardcoded_qwen_type() -> None:
    omitted = _coerce_single_crs_sources(None)
    auto = _coerce_single_crs_sources({"local": [{"family": "auto", "enabled": True, "batchCount": 1}]})
    assert omitted["local"][0]["family"] == "auto"
    assert auto["local"][0]["family"] == "auto"
    assert omitted["local"][0]["family"] != "qwen2512"
    explicit = _coerce_single_crs_sources({"local": [{"family": "qwen2512", "enabled": True, "batchCount": 1}]})
    assert explicit["local"][0]["family"] == "qwen2512"
