"""Co-Director intelligence remediation — speech-act, sufficiency, CRS, NBA, vision flags."""

from __future__ import annotations

import json
from pathlib import Path

from app.codirector.capabilities.registry import get_capability
from app.codirector.conversation.foundation.asset_authority import classify_asset_rank
from app.codirector.conversation.foundation.dialogue_policy import build_dialogue_plan
from app.codirector.conversation.foundation.intent import analyze_intent
from app.codirector.conversation.foundation.runtime_capabilities import build_runtime_capabilities
from app.codirector.conversation.foundation.speech_act import classify_speech_act, resolve_production_action
from app.codirector.conversation.foundation.sufficiency import evaluate_sufficiency
from app.codirector.routing.unified_intent import DispatchStrategy, UnifiedIntentKind, classify_intent

CORPUS = Path(__file__).parent / "fixtures" / "codirector_reasoning_corpus.json"


def _corpus() -> list[dict]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]


def test_corpus_speech_acts() -> None:
    for case in _corpus():
        act = classify_speech_act(case["text"])
        assert act == case["speech_act"], f"{case['id']}: {act} != {case['speech_act']}"
        intent = analyze_intent(case["text"])
        assert intent.speech_act == case["speech_act"], case["id"]
        if case["execute"]:
            assert intent.should_use_tools is True
            assert intent.should_ask_question is False
            assert intent.primary_intent.value in {"REQUEST_ACTION", "REQUEST_GENERATION"}
            assert intent.suppress_next_best_action is True
        else:
            assert intent.should_use_tools is False
            assert "EXECUTE" not in {p.value for p in intent.required_postures}


def test_command_vs_question_crs() -> None:
    command = analyze_intent("Create Korri's CRS.")
    question = analyze_intent("Should we create Korri's CRS?")
    assert command.speech_act == "COMMAND"
    assert question.speech_act == "QUESTION"
    assert command.should_ask_question is False
    assert question.should_use_tools is False


def test_command_sufficient_acts_crs_capability() -> None:
    text = "Create Korri's CRS."
    intent = analyze_intent(text)
    sufficiency = evaluate_sufficiency(
        user_message=text,
        speech_act="COMMAND",
        project_id="proj-1",
        bound_character_id="char-korri",
        db=None,
    )
    assert sufficiency.context_sufficient is True
    assert sufficiency.clarification_required is False
    unified = classify_intent(text, {}, foundation_intent=intent)
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "character.generate_visual_sheet"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    cap = get_capability("create_character_reference_sheet")
    assert cap is not None
    assert "character_creator.propose_visual_sheet" in cap.tool_ids


def test_command_required_missing_asks_only_that_field() -> None:
    text = "Create a character reference sheet."
    sufficiency = evaluate_sufficiency(
        user_message=text,
        speech_act="COMMAND",
        project_id="proj-1",
        bound_character_id=None,
        db=None,
    )
    assert sufficiency.context_sufficient is False
    assert sufficiency.missing_required_fields == ["characterId"]
    assert "which character" in sufficiency.clarification_question.lower()
    intent = analyze_intent(text)
    intent.clarification_required = True
    intent.missing_required_fields = ["characterId"]
    plan = build_dialogue_plan(intent)
    assert plan.question_budget == 1
    assert plan.tool_policy == "NONE"
    assert "characterId" in " ".join(plan.required_elements)


def test_optional_ambiguity_does_not_block() -> None:
    sufficiency = evaluate_sufficiency(
        user_message="Create Korri's CRS in a slightly cooler palette.",
        speech_act="COMMAND",
        project_id="proj-1",
        bound_character_id="char-korri",
        aesthetic_conflict=True,
        db=None,
    )
    assert sufficiency.context_sufficient is True
    assert sufficiency.clarification_required is False
    assert "optional_aesthetic_conflict_ignored" in sufficiency.notes


def test_historical_candidate_does_not_outrank_current() -> None:
    attached = classify_asset_rank(attached_this_turn=True, attachment_asset_id="att-1")
    historical = classify_asset_rank(candidate_or_historical=True)
    assert attached.rank == "ATTACHED_THIS_TURN"
    assert attached.outranks_historical
    assert historical.rank == "CANDIDATE_HISTORICAL_ARCHIVED"
    assert not historical.outranks_historical


def test_nba_suppressed_on_command() -> None:
    intent = analyze_intent("Create Korri's CRS.")
    plan = build_dialogue_plan(intent)
    assert intent.suppress_next_best_action is True
    assert plan.question_budget == 0
    assert "Would you like" in plan.prohibited_elements
    assert "next-best-action" in " ".join(plan.prohibited_elements).lower() or any(
        "questionnaire" in item.lower() for item in plan.prohibited_elements
    )


def test_vision_supported_vs_active_and_degraded() -> None:
    supported = build_runtime_capabilities(
        provider="ollama",
        model="qwen3.6:35b-a3b",
        vision_supported=True,
        vision_trace={"hasImages": False},
        attachment_ids=[],
    )
    assert supported.vision_supported is True
    assert supported.vision_active is False
    assert supported.vision_state == "SUPPORTED"
    answer = supported.answer_capability_question()
    assert "supports vision" in answer.lower()
    assert "korri" not in answer.lower()
    assert "schnick" not in answer.lower()

    active = build_runtime_capabilities(
        provider="ollama",
        model="qwen3.6:35b-a3b",
        vision_supported=True,
        vision_trace={"hasImages": True, "encodedCount": 1},
        attachment_ids=["a1"],
    )
    assert active.vision_active is True
    assert active.vision_state == "ACTIVE"
    assert "active" in active.answer_capability_question().lower()

    degraded = build_runtime_capabilities(
        provider="ollama",
        model="qwen3.6:35b-a3b",
        vision_supported=True,
        vision_trace={"hasImages": False},
        degraded=True,
        degraded_reason="Ollama Unavailable",
    )
    assert degraded.degraded is True
    assert "Ollama Unavailable" in degraded.answer_capability_question()
    assert "korri" not in degraded.answer_capability_question().lower()

    unavailable = build_runtime_capabilities(
        provider="ollama",
        model="llama3",
        vision_supported=False,
        vision_trace={"hasImages": True, "encodedCount": 1},
    )
    assert unavailable.vision_state == "UNAVAILABLE"
    assert "unavailable" in unavailable.answer_capability_question().lower()
    assert "text-only" not in unavailable.answer_capability_question().lower()


def test_retry_uses_user_text_not_assistant_assumption() -> None:
    rejected = "I can start with Cyber-Grunge or a cleaner direction — which would you like?"
    user = "Create Korri's CRS."
    combined = f"{rejected}\n{user}"
    # Retry must reclassify the user command, not the rejected assistant fork.
    assert classify_speech_act(user) == "COMMAND"
    assert classify_speech_act(rejected) != "COMMAND"
    assert classify_speech_act(combined.splitlines()[-1]) == "COMMAND"


def test_tool_case_aliases() -> None:
    assert resolve_production_action("Create Korri's CRS.") == "create_character_reference_sheet"
    assert resolve_production_action("Regenerate Korri's visual sheet.") == "character_creator.advance_visual_sheet"
    assert resolve_production_action("Approve this CRS as the hero.") == "character.assign_reference"
    assert resolve_production_action("Use this as Character Identity.") == "character.assign_reference"
    assert resolve_production_action("Create a multi-view image of Korri.") == "image.generate"


def test_crs_vs_multiview_routing() -> None:
    crs = classify_intent("Create Korri's CRS.", {})
    assert crs.capability == "character.generate_visual_sheet"
    multi = classify_intent("Create a multi-view image of Korri.", {})
    assert multi.capability == "image.generate"
    assert multi.capability != "character.generate_visual_sheet"


def test_negatives_command_does_not_ask_optional() -> None:
    intent = analyze_intent("Create Korri's character reference sheet.")
    plan = build_dialogue_plan(intent)
    assert plan.question_budget == 0
    blob = " ".join(plan.prohibited_elements).lower()
    assert "questionnaire" in blob
    assert "would you like" in blob


def test_negatives_capability_does_not_give_project_advice() -> None:
    intent = analyze_intent("Do you have vision?")
    plan = build_dialogue_plan(intent)
    assert plan.tool_policy == "NONE"
    assert any("runtime" in item.lower() or "vision" in item.lower() for item in plan.required_elements)
    assert any("branding" in item.lower() or "costume" in item.lower() for item in plan.prohibited_elements)


def test_question_does_not_become_execution() -> None:
    intent = analyze_intent("Should we create Korri's CRS?")
    unified = classify_intent("Should we create Korri's CRS?", {}, foundation_intent=intent)
    assert unified.intent != UnifiedIntentKind.EXECUTION
    assert unified.dispatch == DispatchStrategy.LLM_ONLY
