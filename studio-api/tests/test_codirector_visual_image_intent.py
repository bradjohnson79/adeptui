"""Co-Director still-image turns must generate, not interview about sound."""

from __future__ import annotations

from app.codirector.conversation.foundation.dialogue_policy import build_dialogue_plan
from app.codirector.conversation.foundation.intent import analyze_intent
from app.codirector.conversation.foundation.speech_act import (
    classify_speech_act,
    resolve_production_action,
)
from app.codirector.conversation.foundation.image_generation_defaults import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    parse_image_generation_overrides,
    resolve_image_generation_profile,
)
from app.codirector.conversation.foundation.visual_generation import (
    generate_means_execute_valid,
    has_usable_visual_brief,
    inherit_visual_prompt_from_history,
    is_executable_image_turn,
    is_generate_now_followup,
    is_non_visual_interrupt_question,
    is_prompt_only_request,
    is_visual_image_request,
    is_visual_inspection_only,
    is_visual_reference_generation,
    visual_only_clarification,
)
from app.codirector.conversation.discovery.temperature import assess_creative_temperature
from app.codirector.creative_operating.minds import extract_open_questions, interpret_user_need
from app.codirector.creative_operating.openings import detect_creative_openings
from app.codirector.routing.unified_intent import DispatchStrategy, UnifiedIntentKind, classify_intent
from app.production_control.image_generator_query import AutoImageSelection, ImageGeneratorCandidate


def _local_candidate(family: str = "zimage", model_id: str = "zimage-local") -> ImageGeneratorCandidate:
    return ImageGeneratorCandidate(
        model_id=model_id,
        family=family,
        locality="local",
        executable=True,
        installed=True,
        runtime_ready=False,
        supports=("text_to_image",),
        supports_reference=False,
        supports_edit=False,
        provider="comfy",
        model_family=family,
        capability_label="Testing",
        default_eligible=False,
        label=family,
    )


def _auto_zimage() -> AutoImageSelection:
    chosen = _local_candidate()
    return AutoImageSelection(
        selected=chosen,
        task="text_to_image",
        why="test",
        local_candidates=[chosen],
    )


def _match_explicit(name: str, **kwargs):
    token = (name or "").lower()
    if "flux" in token:
        return _local_candidate("flux", "flux-local")
    return None


def _list_hosted(task="text_to_image", locality=None, **kwargs):
    if locality == "hosted":
        return [
            ImageGeneratorCandidate(
                model_id="flux-fal",
                family="flux",
                locality="hosted",
                executable=True,
                installed=False,
                runtime_ready=False,
                supports=("text_to_image",),
                supports_reference=False,
                supports_edit=False,
                provider="fal",
                model_family="flux",
                capability_label="Available",
                default_eligible=False,
                label="FLUX (fal.ai)",
            )
        ]
    return []

CORRIDOR = (
    "Create a Silver metallic corridor scene where we see an elevator door at the end "
    "of the corridor, and then about 10 meters ahead, there is a door that leads to a "
    "Combat Chamber room. The corridor should like something you would see through an "
    "underground research facility. Somewhat sci-fi futuristic, full wide master shot."
)

SOUND_QUESTION = "How should this place look and sound on screen?"
CORRIDOR_NOW = CORRIDOR + "\nPlease create this image for me now."
PROMPT_ONLY = "Give me a Flux prompt for the Venture Corridor. Don't generate it."
GENERATE_NOW = "Great. Generate it now."
FLUX_LOCAL = "Generate this with Flux Local."
WORLD_RULE_Q = "What consequence follows when this world rule is broken?"


def test_corridor_master_shot_is_executable_image() -> None:
    assert is_visual_image_request(CORRIDOR) is True
    assert has_usable_visual_brief(CORRIDOR) is True
    assert is_executable_image_turn(CORRIDOR) is True
    assert classify_speech_act(CORRIDOR) == "COMMAND"
    assert resolve_production_action(CORRIDOR) == "image.generate"


def test_corridor_routes_to_image_generate_deterministic() -> None:
    unified = classify_intent(CORRIDOR, {})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "image.generate"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC


def test_corridor_does_not_ask_sound_or_budget_a_question() -> None:
    intent = analyze_intent(CORRIDOR)
    plan = build_dialogue_plan(intent)
    assert intent.should_ask_question is False
    assert intent.should_use_tools is True
    assert plan.question_budget == 0
    assert interpret_user_need(CORRIDOR) == "EXECUTION"
    assert SOUND_QUESTION not in extract_open_questions(CORRIDOR)
    openings = detect_creative_openings(user_message=CORRIDOR)
    blob = " ".join(
        f"{o.suggestedQuestion or ''} {o.missingDimension} {o.whyItMatters}" for o in openings
    ).lower()
    assert "sound" not in blob
    temp = assess_creative_temperature(CORRIDOR)
    assert temp.question_budget == 0
    assert is_non_visual_interrupt_question(SOUND_QUESTION) is True


def test_plain_create_image_without_brief_is_request_not_sound_interview() -> None:
    text = "Create an image."
    assert is_visual_image_request(text) is True
    assert is_executable_image_turn(text) is False
    assert extract_open_questions(text) == []


def test_use_flux_local_aspect_is_image_generate_not_timeline() -> None:
    from app.codirector.routing.unified_intent import _resolve_capability

    text = "Use Flux local. 16:9"
    cap, _ = _resolve_capability(text)
    assert cap == "image.generate"
    unified = classify_intent(text, {})
    assert unified.capability != "timeline.add_asset"
    timeline_cap, _ = _resolve_capability("Put this 16:9 frame on the timeline.")
    assert timeline_cap == "timeline.add_asset"


def test_atlas_and_counted_scene_shots_are_not_still_image() -> None:
    from app.codirector.routing.unified_intent import _resolve_capability

    assert is_visual_image_request("Create an atlas shot of the lab.") is False
    assert is_visual_image_request("Generate four scene shots.") is False
    cap, _ = _resolve_capability("Create a multi-view image of Korri.")
    assert cap == "image.generate"


def test_corridor_now_is_act_not_prompt_draft() -> None:
    from app.codirector.conversation.next_steps import should_offer_options

    assert is_prompt_only_request(CORRIDOR_NOW) is False
    assert is_executable_image_turn(CORRIDOR_NOW) is True
    unified = classify_intent(CORRIDOR_NOW, {})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "image.generate"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    assert interpret_user_need(CORRIDOR_NOW) == "EXECUTION"
    assert extract_open_questions(CORRIDOR_NOW) == []
    assert WORLD_RULE_Q not in extract_open_questions(CORRIDOR_NOW + " This world has a rule.")
    intent = analyze_intent(CORRIDOR_NOW)
    plan = build_dialogue_plan(intent)
    assert intent.should_ask_question is False
    assert plan.question_budget == 0
    assert any("prompt to paste" in item.lower() or "run themselves" in item.lower() for item in plan.prohibited_elements)
    assert should_offer_options(
        user_message=CORRIDOR_NOW,
        primary_intent=intent.primary_intent.value,
        workflow_hold=False,
        listen_only=False,
    ) is False


def test_prompt_only_does_not_generate() -> None:
    assert is_prompt_only_request(PROMPT_ONLY) is True
    assert is_executable_image_turn(PROMPT_ONLY) is False
    unified = classify_intent(PROMPT_ONLY, {})
    assert unified.intent == UnifiedIntentKind.CONVERSATION
    assert unified.capability == ""
    assert unified.dispatch == DispatchStrategy.LLM_ONLY
    assert generate_means_execute_valid(
        capability=unified.capability,
        dispatch=unified.dispatch.value,
        intent=unified.intent.value,
        conversational_only=True,
    )


def test_generate_it_now_after_drafted_prompt_is_act() -> None:
    recent = [
        {"role": "user", "content": CORRIDOR},
        {
            "role": "assistant",
            "content": "When you run this locally, use this Flux prompt: silver metallic corridor, 16:9, steps=20.",
        },
    ]
    assert is_generate_now_followup(GENERATE_NOW, recent) is True
    assert inherit_visual_prompt_from_history(recent)
    unified = classify_intent(GENERATE_NOW, {"recent_messages": recent})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "image.generate"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    assert is_generate_now_followup(GENERATE_NOW, []) is False


def test_generate_means_execute_invariant() -> None:
    unified = classify_intent(CORRIDOR_NOW, {})
    assert generate_means_execute_valid(
        capability=unified.capability,
        dispatch=unified.dispatch.value,
        intent=unified.intent.value,
        job_id="",
        execution_id="",
        conversational_only=True,
    ) is False
    assert generate_means_execute_valid(
        capability=unified.capability,
        dispatch=unified.dispatch.value,
        intent=unified.intent.value,
        job_id="job-1",
        conversational_only=False,
    ) is True


def test_create_this_image_resolves_capability() -> None:
    from app.codirector.routing.unified_intent import _resolve_capability

    cap, _ = _resolve_capability("Please create this image for me now.")
    assert cap == "image.generate"


def test_corridor_now_handle_enqueues_job(monkeypatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.codirector.capabilities.handlers import image_generate as handler
    from app.codirector.preferences.resolver import PreferenceResolution

    captured: list[dict] = []

    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(
            provider="zimage",
            source="default",
            modality="image",
        ),
    )
    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: True)
    monkeypatch.setattr(handler, "select_auto_image_generator", lambda *args, **kwargs: _auto_zimage())
    monkeypatch.setattr(handler, "match_explicit_image_generator", _match_explicit)
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda db, project_id, body=None, **kwargs: captured.append(dict(body or {}))
        or SimpleNamespace(id="job-corridor-1"),
    )
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-corridor",
        prompt=CORRIDOR_NOW,
        user_instructions=CORRIDOR_NOW,
    )
    assert captured
    assert result["child_jobs"]
    assert result["child_jobs"][0]["job_id"] == "job-corridor-1"
    assert generate_means_execute_valid(
        capability="image.generate",
        dispatch="deterministic",
        intent="EXECUTION",
        job_id=result["child_jobs"][0]["job_id"],
        execution_id="exec-corridor",
    )


def test_flux_unavailable_fails_forward_not_tutorial(monkeypatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.codirector.capabilities.handlers import image_generate as handler
    from app.codirector.image_route.contracts import ProviderAvailability
    from app.codirector.preferences.resolver import PreferenceResolution

    captured: list[dict] = []
    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(
            provider="flux",
            source="explicit",
            modality="image",
            explicit=True,
            configured=False,
        ),
    )
    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: True)
    monkeypatch.setattr(handler, "match_explicit_image_generator", lambda *args, **kwargs: None)
    monkeypatch.setattr(handler, "select_auto_image_generator", lambda *args, **kwargs: _auto_zimage())
    monkeypatch.setattr(handler, "list_compatible_image_generators", _list_hosted)
    monkeypatch.setattr(
        handler,
        "observe_hosted_provider_state",
        lambda pid: ProviderAvailability(
            provider_id=pid,
            provider_configured=True,
            provider_reachable=True,
            provider_funded=True,
            funding_state="unknown",
        ),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda db, project_id, body=None, **kwargs: captured.append(dict(body or {}))
        or SimpleNamespace(id="job-flux-fallback"),
    )
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-1",
        prompt=FLUX_LOCAL,
        user_instructions=FLUX_LOCAL,
    )
    assert captured
    assert captured[0].get("source") == "fal"
    ack = (result.get("creatorAck") or result.get("error") or "").lower()
    assert "when you run" not in ack
    assert "paste" not in ack
    assert result["child_jobs"]


def test_corridor_now_dispatch_submits_job(monkeypatch) -> None:
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from uuid import uuid4

    from app.codirector.execution.dispatcher import dispatch
    from app.codirector.preferences.resolver import PreferenceResolution
    from app.codirector.routing.unified_intent import UnifiedIntent

    captured: list[dict] = []

    def fake_enqueue(db, project_id, body=None, **kwargs):
        captured.append(dict(body or {}))
        return SimpleNamespace(id=f"job-{len(captured)}")

    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: True)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.image_generate.select_auto_image_generator",
        lambda *args, **kwargs: _auto_zimage(),
    )
    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", fake_enqueue)
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.image_generate.resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(
            provider="zimage",
            source="default",
            modality="image",
        ),
    )
    monkeypatch.setattr(
        "app.codirector.execution.dispatcher.save_pack",
        lambda db, project_id, pack: pack,
    )

    unified = classify_intent(CORRIDOR_NOW, {})
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    db = MagicMock()
    plan = asyncio.run(
        dispatch(
            db,
            str(uuid4()),
            UnifiedIntent(
                intent=unified.intent,
                capability=unified.capability,
                confidence=unified.confidence,
                dispatch=unified.dispatch,
            ),
            context={"prompt": CORRIDOR_NOW, "user_instructions": CORRIDOR_NOW},
        )
    )
    assert plan.capability == "image.generate"
    assert captured, "expected a real image job enqueue"
    assert "Silver metallic corridor" in (captured[0].get("prompt") or "")
    assert plan.child_jobs, "GENERATE+READY must produce a job"
    assert plan.child_jobs[0].job_id
    assert generate_means_execute_valid(
        capability=plan.capability,
        dispatch=unified.dispatch.value,
        intent=unified.intent.value,
        job_id=plan.child_jobs[0].job_id,
        execution_id=plan.execution_id,
        conversational_only=False,
    )


VENTURE_IMAGE = "Create an image of the Venture corridor."
VENTURE_21_9 = "Create the Venture corridor at 21:9."
VENTURE_RES = "Create an image of the Venture corridor. Generate this at 2560×1440."
VENTURE_FAL = "Create an image of the Venture corridor. Generate this with fal.ai."
VENTURE_FLUX = "Create an image of the Venture corridor. Use Flux Local."


def _handle_captured(monkeypatch, prompt: str, *, comfy_ok: bool = True):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.codirector.capabilities.handlers import image_generate as handler
    from app.codirector.preferences.resolver import PreferenceResolution

    captured: list[dict] = []
    profile = resolve_image_generation_profile(prompt)
    monkeypatch.setattr("runtime_supervisor.health.comfy_healthy", lambda: comfy_ok)
    monkeypatch.setattr(
        handler,
        "resolve_generator_preference",
        lambda *args, **kwargs: PreferenceResolution(
            provider="flux" if "flux" in prompt.lower() else "zimage",
            source="explicit" if "flux" in prompt.lower() else "default",
            modality="image",
            explicit="flux" in prompt.lower(),
            configured=True,
        ),
    )
    monkeypatch.setattr(handler, "select_auto_image_generator", lambda *args, **kwargs: _auto_zimage())
    monkeypatch.setattr(handler, "match_explicit_image_generator", _match_explicit)
    monkeypatch.setattr(handler, "list_compatible_image_generators", _list_hosted)
    monkeypatch.setattr(
        handler,
        "observe_hosted_provider_state",
        lambda pid: __import__(
            "app.codirector.image_route.contracts",
            fromlist=["ProviderAvailability"],
        ).ProviderAvailability(
            provider_id=pid,
            provider_configured=True,
            provider_reachable=True,
            provider_funded=True,
            funding_state="unknown",
        ),
    )
    monkeypatch.setattr(
        "app.storyboard_jobs.enqueue_imagegen_job",
        lambda db, project_id, body=None, **kwargs: captured.append(dict(body or {}))
        or SimpleNamespace(id=f"job-{len(captured) + 1}"),
    )
    result = handler.handle(
        db=MagicMock(),
        project_id="proj",
        execution_id="exec-defaults",
        prompt=prompt,
        user_instructions=prompt,
        aspect_ratio=profile.aspect_ratio,
        width=profile.width,
        height=profile.height,
        provider_kind=profile.provider_kind,
        generation_route=profile.route,
    )
    return result, captured


def test_default_venture_image_is_auto_local_16x9_1080() -> None:
    assert is_executable_image_turn(VENTURE_IMAGE) is True
    unified = classify_intent(VENTURE_IMAGE, {})
    assert unified.capability == "image.generate"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC
    assert extract_open_questions(VENTURE_IMAGE) == []
    profile = resolve_image_generation_profile(VENTURE_IMAGE)
    assert profile.route == "AUTO"
    assert profile.provider_kind == "local"
    assert profile.local_first is True
    assert profile.aspect_ratio == "16:9"
    assert (profile.width, profile.height) == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    assert profile.clarification_count == 0
    assert profile.acknowledgement() == "Got it — generating that locally at 16:9 now."
    assert "1920" not in profile.acknowledgement()
    assert "steps" not in profile.acknowledgement().lower()


def test_default_venture_image_submits_local_job(monkeypatch) -> None:
    result, captured = _handle_captured(monkeypatch, VENTURE_IMAGE)
    assert captured
    body = captured[0]
    assert body["aspectRatio"] == "16:9"
    assert body["width"] == 1920
    assert body["height"] == 1080
    assert body.get("source") == "local"
    assert body.get("providerKind") == "local"
    assert "fal" not in str(body.get("hostedModelId") or "").lower()
    assert result["child_jobs"]
    assert result["route"] == "AUTO"
    assert result["providerKind"] == "local"
    assert generate_means_execute_valid(
        capability="image.generate",
        dispatch="deterministic",
        intent="EXECUTION",
        job_id=result["child_jobs"][0]["job_id"],
        execution_id="exec-defaults",
    )


def test_explicit_aspect_21_9_does_not_leak_16x9(monkeypatch) -> None:
    profile = resolve_image_generation_profile(VENTURE_21_9)
    assert profile.route == "AUTO"
    assert profile.provider_kind == "local"
    assert profile.aspect_ratio == "21:9"
    assert (profile.width, profile.height) != (1920, 1080)
    result, captured = _handle_captured(monkeypatch, VENTURE_21_9)
    assert captured[0]["aspectRatio"] == "21:9"
    assert captured[0]["width"] != 1920 or captured[0]["height"] != 1080
    assert result["aspectRatio"] == "21:9"


def test_explicit_resolution_2560x1440_does_not_leak_1080(monkeypatch) -> None:
    profile = resolve_image_generation_profile(VENTURE_RES)
    assert (profile.width, profile.height) == (2560, 1440)
    result, captured = _handle_captured(monkeypatch, VENTURE_RES)
    assert captured[0]["width"] == 2560
    assert captured[0]["height"] == 1440
    assert captured[0]["width"] != 1920
    assert captured[0]["height"] != 1080
    assert result["width"] == 2560


def test_explicit_fal_does_not_execute_local(monkeypatch) -> None:
    profile = resolve_image_generation_profile(VENTURE_FAL)
    assert profile.provider_kind == "fal"
    assert profile.local_first is False
    result, captured = _handle_captured(monkeypatch, VENTURE_FAL)
    body = captured[0]
    assert body.get("providerKind") == "fal"
    assert body.get("source") == "fal"
    assert body.get("hostedModelId") == "flux-fal"
    assert result["providerKind"] == "fal"
    assert "locally" not in (result.get("creatorAck") or "").lower()


def test_explicit_flux_local_keeps_default_frame(monkeypatch) -> None:
    profile = resolve_image_generation_profile(VENTURE_FLUX)
    assert profile.explicit_provider == "flux"
    assert profile.provider_kind == "local"
    assert profile.aspect_ratio == "16:9"
    assert (profile.width, profile.height) == (1920, 1080)
    result, captured = _handle_captured(monkeypatch, VENTURE_FLUX)
    assert captured[0]["modelFamilyPreference"] == "flux"
    assert captured[0]["aspectRatio"] == "16:9"
    assert captured[0]["width"] == 1920
    assert captured[0]["height"] == 1080
    assert captured[0].get("source") == "local"
    assert result["providerKind"] == "local"


def test_local_unavailable_fails_forward_to_hosted(monkeypatch) -> None:
    result, captured = _handle_captured(monkeypatch, VENTURE_IMAGE, comfy_ok=False)
    assert captured
    assert captured[0].get("source") == "fal"
    assert captured[0].get("hostedModelId") == "flux-fal"
    assert result["child_jobs"]
    assert "hosted image API" in (result.get("creatorAck") or "")
    assert result.get("error") in {None, ""}


def test_conversation_remembers_fal_and_21_9() -> None:
    recent = [{"role": "user", "content": "For these shots, use fal.ai at 21:9."}]
    profile = resolve_image_generation_profile(VENTURE_IMAGE, recent)
    assert profile.provider_kind == "fal"
    assert profile.aspect_ratio == "21:9"
    assert (profile.width, profile.height) != (1920, 1080)
    current = resolve_image_generation_profile("Make it 4:3.", recent)
    assert current.aspect_ratio == "4:3"
    assert current.provider_kind == "fal"


def test_gpt_image_2_named_in_retry_utterance() -> None:
    parsed = parse_image_generation_overrides(
        "Retry with same prompt again and use GPT Image 2."
    )
    assert parsed["explicit_provider"] == "gptimage2"
    assert parsed.get("provider_kind") != "fal"
    unified = classify_intent("Retry with same prompt again and use GPT Image 2.", {})
    assert unified.capability == "image.generate"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC


LIVE_ATTACHED = (
    "I would like to see the created image more like what you see attached through GPT Image 2."
)
REFERENCE_CORRIDOR = (
    "Create another corridor that matches the lighting, industrial density, "
    "materials and visual style of this reference."
)


def test_attached_reference_is_executable_without_interview() -> None:
    assert is_visual_reference_generation(LIVE_ATTACHED) is True
    assert is_visual_inspection_only(LIVE_ATTACHED) is False
    assert is_executable_image_turn(LIVE_ATTACHED, has_visual_reference=True) is True
    assert visual_only_clarification(LIVE_ATTACHED, has_visual_reference=True) is None


def test_what_do_you_see_is_inspection_not_generation() -> None:
    text = "What do you see in this image?"
    assert is_visual_inspection_only(text) is True
    assert is_executable_image_turn(text, has_visual_reference=True) is False


def test_match_reference_corridor_is_executable() -> None:
    assert is_visual_reference_generation(REFERENCE_CORRIDOR) is True
    assert is_executable_image_turn(REFERENCE_CORRIDOR, has_visual_reference=True) is True
    assert visual_only_clarification(REFERENCE_CORRIDOR, has_visual_reference=True) is None
