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
from app.codirector.durable.wording import project_creator_reply

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


def test_backstory_request_is_not_a_voice_command():
    text = "Give me a concise backstory for this character."
    allowed = {
        "character_creator.generate_voice_candidates",
        "character_creator.create_from_brief",
    }
    assert _operation_tool(text, allowed) == ""
    decision = resolve_admitted_tool(
        text,
        {
            "mode": "MUTATE",
            "confidence": "high",
            "tool_id": "character_creator.generate_voice_candidates",
            "reply": "He grew up cataloging wrecks for a civilian salvage guild.",
        },
        allowed=allowed,
        fallback="character_creator.generate_voice_candidates",
    )
    assert decision.tool_id is None
    assert "salvage guild" in decision.reply


def test_broken_reply_envelope_stays_a_sentence():
    broken = """{
  "mode": "CONVERSATION",
  "confidence": "high",
  "reply": "He keeps a "closed" silhouette and a short coat."
}"""
    spoken = project_creator_reply(broken)
    assert "short coat" in spoken
    assert '"mode"' not in spoken
    assert not spoken.lstrip().startswith("{")


def test_portrait_still_pixels_match_three_by_four():
    from app.image_product.compile import _size

    width, height = _size("3:4", "1080p")
    assert width % 8 == 0 and height % 8 == 0
    assert abs((width / height) - 0.75) < 0.02


def test_any_named_ratio_gets_matching_pixels():
    from app.image_product.compile import _size, resolve_image_canvas

    samples = (("5:4", 1.25), ("4:5", 0.8), ("7:5", 1.4), ("3:4", 0.75), ("16:9", 16 / 9), ("9:16", 9 / 16))
    for aspect, want in samples:
        width, height = _size(aspect, "1080p")
        assert width % 8 == 0 and height % 8 == 0
        assert abs((width / height) - want) <= 0.08 * want, aspect
    forced_w, forced_h = resolve_image_canvas("3:4", "1080p", 1024, 1024, named_aspect=True)
    assert abs((forced_w / forced_h) - 0.75) < 0.02
    kept_w, kept_h = resolve_image_canvas("1:1", "1080p", 1280, 720, named_aspect=False)
    assert (kept_w, kept_h) == (1280, 720)

    from app.imagegen_workflows import build_txt2img_workflow
    from app.workflows.flux_image import build_flux_txt2img_workflow
    from app.workflows.image_tools import build_zimage_txt2img_workflow
    from app.workflows.krea2_image import build_krea2_turbo_txt2img_workflow
    from app.workflows.qwen_image_2512 import build_qwen_2512_txt2img_workflow

    def latent(graph: dict) -> tuple[int, int]:
        for node in graph.values():
            if isinstance(node, dict) and node.get("class_type") in {"EmptyLatentImage", "EmptySD3LatentImage"}:
                inputs = node["inputs"]
                return int(inputs["width"]), int(inputs["height"])
        raise AssertionError("latent canvas missing")

    canvas = (768, 1024)
    graphs = [
        build_qwen_2512_txt2img_workflow(
            unet_name="u", clip_name="c", vae_name="v", positive="still", width=768, height=1024
        ),
        build_zimage_txt2img_workflow(
            unet_name="u", clip_name="c", vae_name="v", positive="still", width=768, height=1024
        ),
        build_flux_txt2img_workflow(
            positive="still",
            negative="",
            width=768,
            height=1024,
            seed=1,
            unet_name="u",
            clip_l_name="c",
            t5_name="t",
            vae_name="v",
        ),
        build_krea2_turbo_txt2img_workflow(
            unet_name="u", clip_name="c", vae_name="v", positive="still", width=768, height=1024
        ),
        build_txt2img_workflow(
            checkpoint="illustrious.safetensors",
            positive="still",
            negative="",
            width=768,
            height=1024,
            seed=1,
        ),
    ]
    for graph in graphs:
        assert latent(graph) == canvas


def test_simple_still_does_not_require_a_saved_reference():
    from app.codirector.durable.approval import _image_contract_matches, _verified_wording

    raw = {"ok": True, "toolResult": {"ok": True, "jobId": "job-1", "operation": "image.generate"}}
    arguments = {"prompt": "amber eyes, short coat", "aspectRatio": "3:4"}
    assert _image_contract_matches(raw, arguments)
    spoken = _verified_wording("propose_image_generate", arguments)
    assert spoken == ""
    assert not _image_contract_matches(raw, {"prompt": "", "aspectRatio": "3:4"})


def test_classic_anime_still_uses_the_anime_family():
    from unittest.mock import MagicMock

    from app.codirector.durable.bind import bind_request_arguments

    text = (
        "Use Image Generator with Qwen for a still image, 3:4. "
        "Classic anime. A civilian crisis analyst in a short coat."
    )
    args, refusal = bind_request_arguments(
        MagicMock(),
        tool_id="propose_image_generate",
        arguments={},
        user_text=text,
        project_id="project",
    )
    assert refusal is None
    assert args["modelFamilyPreference"] == "qwen2512"
    assert args["lockModelFamily"] is True
    assert "not live action" in str(args["prompt"]).lower()
    assert "cel shading" in str(args["prompt"]).lower()


def test_image_surface_alone_does_not_choose_a_still():
    assert _operation_tool("Use Image Generator.", {"propose_image_generate"}) == ""
    still = "Use Image Generator to create a still."
    assert classify_turn_mode(still) == "MUTATE"
    assert _operation_tool(still, {"propose_image_generate"}) == "propose_image_generate"
