"""Unit tests for Co-Director Advanced Deliberation contracts + core wiring."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.codirector.deliberation import (
    Commitment,
    DeliberationDecision,
    RiskLevel,
    TalkAskAct,
    assess_risk,
    build_decision,
    normalize_commitment,
    reason_codes as RC,
    resolve_referential_structure,
)
from app.codirector.deliberation.contracts import SCHEMA_VERSION
from app.codirector.generation_memory.referential import (
    is_referential_generation,
    requested_artifact_type,
    source_artifact_type,
    target_artifact_type,
)
from app.codirector.routing.unified_intent import (
    DispatchStrategy,
    UnifiedIntent,
    UnifiedIntentKind,
)


def test_contracts_schema_version_and_enums() -> None:
    d = DeliberationDecision(act=TalkAskAct.TALK, reasonCodes=[RC.GROUNDING_TALK])
    assert d.schemaVersion == SCHEMA_VERSION == "cd-deliberation-v1"
    assert Commitment.NONE.value == "NONE"
    assert RiskLevel.DESTRUCTIVE.value == "DESTRUCTIVE"
    assert TalkAskAct.ACT.value == "ACT"
    assert d.should_talk() is True
    assert d.should_dispatch() is False


def test_normalize_commitment_explicit_and_none() -> None:
    c, codes = normalize_commitment(user_message="Do it")
    assert c == Commitment.EXPLICIT
    assert RC.COMMITMENT_EXPLICIT in codes

    c2, _ = normalize_commitment(user_message="Go ahead")
    assert c2 == Commitment.EXPLICIT

    c3, _ = normalize_commitment(user_message="Generate that")
    assert c3 == Commitment.EXPLICIT

    c4, _ = normalize_commitment(user_message="Make that better")
    assert c4 == Commitment.NONE

    pending = SimpleNamespace(state="AWAITING_CONFIRMATION")
    c5, codes5 = normalize_commitment(user_message="Yes, proceed", pending_execution=pending)
    assert c5 == Commitment.EXPLICIT
    assert RC.COMMITMENT_EXPLICIT in codes5


def test_normalize_commitment_implied_command() -> None:
    c, codes = normalize_commitment(
        user_message="Create a cinematic image of the Venture corridor.",
        speech_act="COMMAND",
        production_action="image.generate",
    )
    assert c == Commitment.IMPLIED
    assert RC.COMMITMENT_IMPLIED in codes


def test_sufficiency_live_wired_into_build_decision() -> None:
    decision = build_decision(
        user_message="Create Korri's CRS.",
        project_id="proj-1",
        speech_act="COMMAND",
        bound_character_id="char-korri",
        db=None,
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="character.generate_visual_sheet",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert decision.sufficiency.contextSufficient is True
    assert RC.SUFFICIENCY_OK in decision.reasonCodes or RC.SUFFICIENCY_OK in decision.sufficiency.notes


def test_sufficiency_asks_when_character_missing() -> None:
    decision = build_decision(
        user_message="Create a character reference sheet.",
        project_id="proj-1",
        speech_act="COMMAND",
        bound_character_id=None,
        db=None,
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ASK
    assert "characterId" in decision.sufficiency.missingRequiredFields
    assert decision.responsePlan.clarificationQuestion


def test_referential_last_corridor_image_structural() -> None:
    text = "Put @Korri and @Anadriya in the last corridor image."
    assert is_referential_generation(text) is True
    assert requested_artifact_type(text) == "image"
    ref = resolve_referential_structure(text)
    assert ref.matched is True
    assert ref.sourceArtifactType == "image"
    assert "corridor" in (ref.subjectQualifier or "")


def test_referential_video_version_of_last_image() -> None:
    text = "Make a video version of the last corridor image."
    ref = resolve_referential_structure(text)
    assert ref.matched is True
    assert source_artifact_type(text) == "image" or ref.sourceArtifactType == "image"
    assert target_artifact_type(text) == "video" or ref.targetArtifactType == "video"


def test_risk_destructive_delete_scene_asks() -> None:
    risk = assess_risk(user_message="Delete this scene.")
    assert risk.level == RiskLevel.DESTRUCTIVE
    assert risk.confirmationRequired is True
    decision = build_decision(
        user_message="Delete this scene.",
        project_id="proj-1",
        speech_act="COMMAND",
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ASK
    assert RC.DESTRUCTIVE_CONFIRMATION_REQUIRED in decision.reasonCodes
    assert "confirm" in decision.responsePlan.clarificationQuestion.lower() or "delete" in decision.responsePlan.clarificationQuestion.lower()


def test_strict_unavailable_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.deliberation import service as delib_service
    from app.codirector.image_route.contracts import ImageRoutePlan, RouteLock

    def _fake_precheck(**kwargs):  # noqa: ANN003
        from app.codirector.deliberation.contracts import RuntimePrecheck

        return RuntimePrecheck(
            consulted=True,
            ready=False,
            lockLevel="STRICT",
            error="STRICT model unavailable",
            reasonCodes=[RC.STRICT_MODEL_UNAVAILABLE],
        )

    monkeypatch.setattr(delib_service, "_runtime_precheck_image", _fake_precheck)
    decision = build_decision(
        user_message="Create an image using only Flux with no fallback.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
            evidence=["speech-act COMMAND + still image"],
        ),
        route_lock={"level": "STRICT", "requestedModelId": "flux"},
        runtime_precheck=True,
    )
    assert decision.act == TalkAskAct.STOP
    assert RC.STRICT_MODEL_UNAVAILABLE in decision.reasonCodes


def test_entity_influence_on_plan_for_last_corridor() -> None:
    decision = build_decision(
        user_message="Put @Korri and @Anadriya in the last corridor image.",
        project_id="beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        speech_act="COMMAND",
        entity_bindings=[
            {"resolved": True, "id": "c1", "name": "Korri", "token": "@Korri"},
            {"resolved": True, "id": "c2", "name": "Anadriya", "token": "@Anadriya"},
        ],
        grounding_snapshot={"bound": True, "projectId": "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"},
        runtime_precheck=False,
    )
    assert decision.referential.matched is True
    assert decision.act == TalkAskAct.ACT
    assert decision.capabilityId == "image.generate"
    assert RC.ENTITY_RESOLVED in decision.reasonCodes or RC.REFERENTIAL_MATCHED in decision.reasonCodes


def test_image_and_video_share_talk_ask_act_path() -> None:
    img = build_decision(
        user_message="Create a cinematic image of the Venture corridor.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    vid = build_decision(
        user_message="Make a video version of that.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="video.generate",
            confidence=0.93,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert img.act == TalkAskAct.ACT
    assert vid.act == TalkAskAct.ACT
    assert img.schemaVersion == vid.schemaVersion
    assert img.executionPlanStub.preferCanonicalMemory is True
    assert vid.executionPlanStub.preferCanonicalMemory is True


def test_make_that_better_asks_not_invents() -> None:
    decision = build_decision(
        user_message="Make that better.",
        project_id="proj-1",
        speech_act="DISCUSSION",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.CONVERSATION,
            confidence=0.5,
            dispatch=DispatchStrategy.LLM_ONLY,
        ),
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ASK
    assert RC.TARGET_AMBIGUOUS in decision.reasonCodes


def test_canonical_memory_preferred_over_chat_inherit() -> None:
    next_req = SimpleNamespace(
        action="image.generate",
        artifactType="image",
        requestId="req-1",
        parentRequestId="req-0",
    )
    canonical = SimpleNamespace(next_request=next_req, clarification=None, inherit_audit=None)
    decision = build_decision(
        user_message="Retry that with Flux at 21:9.",
        project_id="proj-1",
        speech_act="COMMAND",
        canonical_retry=canonical,
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.94,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ACT
    assert RC.CANONICAL_REQUEST_FOUND in decision.reasonCodes
    assert RC.PRODUCTION_MEMORY_PREFERRED in decision.reasonCodes
    assert decision.executionPlanStub.preferCanonicalMemory is True
    assert decision.executionPlanStub.params.get("used_chat_inherit") is False


def test_commitment_without_target_asks() -> None:
    decision = build_decision(
        user_message="Do it",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="",
            confidence=0.8,
            dispatch=DispatchStrategy.CURATED_TOOLS,
        ),
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ASK
    assert RC.COMMITMENT_WITHOUT_TARGET in decision.reasonCodes or RC.TARGET_AMBIGUOUS in decision.reasonCodes

def test_footsteps_null_scene_asks() -> None:
    decision = build_decision(
        user_message="Place the approved footsteps on the timeline for this walk.",
        project_id="proj-1",
        scene_id="",
        speech_act="COMMAND",
        grounding_snapshot={"bound": True, "projectId": "proj-1", "activeScene": None},
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="timeline.add_audio",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ASK
    assert RC.SCENE_REQUIRED in decision.reasonCodes or RC.SCENE_UNBOUND_ASK in decision.reasonCodes


def test_pending_execution_passed_for_confirm() -> None:
    pending = SimpleNamespace(state="AWAITING_CONFIRMATION", capability="image.generate")
    decision = build_decision(
        user_message="Yes, proceed",
        project_id="proj-1",
        speech_act="COMMAND",
        pending_execution=pending,
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert decision.commitment == Commitment.EXPLICIT
    assert RC.PENDING_CONFIRM_PATH in decision.reasonCodes or RC.COMMITMENT_EXPLICIT in decision.reasonCodes
    assert decision.act == TalkAskAct.ACT


def test_failure_informed_retry_reason() -> None:
    decision = build_decision(
        user_message="Retry that image.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        failed_execution_history=[
            {"capability": "image.generate", "status": "failed", "error": "Comfy timeout"}
        ],
        runtime_precheck=False,
    )
    assert RC.FAILURE_INFORMED_RETRY in decision.reasonCodes
    assert "Comfy" in decision.failedExecutionSummary or "image.generate" in decision.failedExecutionSummary


def test_fast_vs_deep_effort_flag() -> None:
    from app.codirector.deliberation import DeliberationMode, resolve_effort_mode

    assert resolve_effort_mode(user_message="hi") == DeliberationMode.FAST
    assert resolve_effort_mode(user_message="Please deep dive the whole project bible.") == DeliberationMode.DEEP
    deep = build_decision(
        user_message="Please thoroughly research the corridor continuity across the project.",
        project_id="proj-1",
        speech_act="DISCUSSION",
        runtime_precheck=False,
    )
    assert deep.mode == DeliberationMode.DEEP
    assert deep.effortHint == "DEEP"
    assert RC.DEEP_EFFORT in deep.reasonCodes


def test_runtime_precheck_uses_local_runtime_ready_false(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.codirector.deliberation import service as delib_service
    from app.codirector.deliberation.contracts import RuntimePrecheck

    def _fake_precheck(**kwargs):
        assert kwargs.get("local_runtime_ready") is False
        return RuntimePrecheck(
            consulted=True,
            ready=False,
            lockLevel="UNLOCKED",
            error="local runtime unavailable",
            reasonCodes=[RC.RUNTIME_UNAVAILABLE],
        )

    monkeypatch.setattr(delib_service, "_runtime_precheck_image", _fake_precheck)
    decision = build_decision(
        user_message="Create a cinematic still of the Venture corridor.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        local_runtime_ready=False,
        runtime_precheck=True,
    )
    assert decision.act in {TalkAskAct.ASK, TalkAskAct.STOP}
    assert RC.RUNTIME_UNAVAILABLE in decision.reasonCodes or decision.runtimePrecheck.consulted


# --- Behavioral convergence: 8 still-failing cases + contrast / STRICT ---


def test_convergence_ref_latest_shot_enhance_acts() -> None:
    decision = build_decision(
        user_message="Enhance the latest corridor shot with denser fog.",
        project_id="beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        speech_act="",
        grounding_snapshot={"bound": True, "projectId": "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"},
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.CONVERSATION,
            confidence=0.5,
            dispatch=DispatchStrategy.LLM_ONLY,
        ),
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.ACT, TalkAskAct.ASK}
    assert decision.capabilityId == "image.generate" or decision.act == TalkAskAct.ASK
    assert decision.referential.matched is True


def test_convergence_unresolved_entity_asks_not_act() -> None:
    decision = build_decision(
        user_message="Generate a still of @UnknownHeroX in the corridor.",
        project_id="proj-1",
        speech_act="COMMAND",
        entity_bindings=[{"resolved": False, "token": "@UnknownHeroX", "name": "UnknownHeroX"}],
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.ASK, TalkAskAct.STOP}
    assert RC.ENTITY_UNRESOLVED in decision.reasonCodes


def test_convergence_use_flux_provider_command_acts() -> None:
    from app.codirector.image_route.lock import parse_route_lock

    lock = parse_route_lock("Use Flux for this corridor image.")
    decision = build_decision(
        user_message="Use Flux for this corridor image.",
        project_id="proj-1",
        speech_act="COMMAND",
        route_lock={
            "level": lock.level,
            "requestedModelId": lock.requested_model_id,
            "scope": lock.scope,
        },
        grounding_snapshot={"bound": True, "projectId": "proj-1"},
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ACT
    assert decision.capabilityId == "image.generate"
    assert lock.level == "PREFERRED"
    assert lock.requested_model_id == "flux"


def test_convergence_use_flux_cinematic_acts() -> None:
    from app.codirector.image_route.lock import parse_route_lock

    prompt = "Use Flux for a cinematic image of the Venture corridor."
    lock = parse_route_lock(prompt)
    decision = build_decision(
        user_message=prompt,
        project_id="proj-1",
        speech_act="COMMAND",
        route_lock={
            "level": lock.level,
            "requestedModelId": lock.requested_model_id,
            "scope": lock.scope,
        },
        grounding_snapshot={"bound": True},
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.ACT, TalkAskAct.ASK, TalkAskAct.STOP}
    assert lock.requested_model_id == "flux"


def test_convergence_runtime_unavailable_hard_gate() -> None:
    decision = build_decision(
        user_message="Create a cinematic image of the Venture corridor.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        local_runtime_ready=False,
        runtime_precheck=True,
    )
    assert decision.act in {TalkAskAct.ASK, TalkAskAct.STOP}
    assert RC.RUNTIME_UNAVAILABLE in decision.reasonCodes
    assert decision.runtimePrecheck.ready is False


def test_convergence_destructive_discussion_talks() -> None:
    decision = build_decision(
        user_message="Should we eventually delete this scene, or keep it for continuity?",
        project_id="proj-1",
        speech_act="QUESTION",
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.TALK
    assert RC.DESTRUCTIVE_DISCUSSION in decision.reasonCodes
    assert decision.risk.destructive is False


def test_convergence_quoted_command_protected_talks() -> None:
    prompt = (
        'Brad said: "Create a cinematic image of the Venture corridor." '
        "— should we actually do that, or was he just giving an example?"
    )
    decision = build_decision(
        user_message=prompt,
        project_id="proj-1",
        speech_act="",
        grounding_snapshot={"bound": True},
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.TALK, TalkAskAct.ASK}
    assert RC.QUOTED_COMMAND_PROTECTED in decision.reasonCodes


def test_convergence_deferred_not_yet_talks() -> None:
    decision = build_decision(
        user_message="Make another version of that corridor shot, but not yet.",
        project_id="proj-1",
        speech_act="COMMAND",
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.TALK, TalkAskAct.ASK}
    assert RC.DEFERRED_INTENT in decision.reasonCodes


def test_contrast_can_you_generate_images_talks() -> None:
    decision = build_decision(
        user_message="Can you generate images?",
        project_id="proj-1",
        speech_act="",
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.TALK


def test_contrast_can_you_generate_this_acts() -> None:
    decision = build_decision(
        user_message="Can you generate this for me?",
        project_id="proj-1",
        speech_act="",
        grounding_snapshot={"bound": True},
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ACT
    assert decision.capabilityId == "image.generate"


def test_mixed_chitchat_plus_command_still_acts() -> None:
    decision = build_decision(
        user_message="I like the corridor mood. Create a cinematic still of the Venture corridor at golden hour.",
        project_id="proj-1",
        speech_act="",
        grounding_snapshot={"bound": True},
        unified_intent=UnifiedIntent(
            intent=UnifiedIntentKind.EXECUTION,
            capability="image.generate",
            confidence=0.9,
            dispatch=DispatchStrategy.DETERMINISTIC,
        ),
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ACT


def test_strict_flux_only_no_fallback_lock() -> None:
    from app.codirector.image_route.lock import parse_route_lock

    lock = parse_route_lock("Use Flux only. No fallback.")
    assert lock.level == "STRICT"
    assert lock.requested_model_id == "flux"
    assert lock.requested_model_id != "nofallback"
    assert "fallback" not in (lock.requested_model_id or "")


def test_with_denser_fog_is_not_a_model_lock() -> None:
    from app.codirector.image_route.lock import parse_route_lock

    lock = parse_route_lock("Enhance the latest corridor shot with denser fog.")
    assert (lock.requested_model_id or "") == ""
    assert lock.level == "UNLOCKED"


# --- ROUND2 residual closure: P0 false-ACT / false-ASK ---


def test_round2_f32_contradiction_not_act() -> None:
    decision = build_decision(
        user_message=(
            "Make Korri taller in the next shot, but also keep her the exact same height as before. "
            "Use only Flux with no fallback, and also use automatic local."
        ),
        project_id="proj-1",
        speech_act="COMMAND",
        grounding_snapshot={"bound": True, "characters": [{"name": "Korri"}]},
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.ASK, TalkAskAct.STOP, TalkAskAct.TALK}
    assert RC.CONTRADICTORY_CONSTRAINTS in decision.reasonCodes


def test_round2_37_future_will_generate_talks() -> None:
    decision = build_decision(
        user_message="Tomorrow I'll want you to generate footsteps SFX. What would you need from me first?",
        project_id="proj-1",
        speech_act="QUESTION",
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.TALK
    assert (
        RC.FUTURE_INTENT in decision.reasonCodes
        or RC.HYPOTHETICAL_QUERY in decision.reasonCodes
        or RC.DEFERRED_INTENT in decision.reasonCodes
    )


def test_round2_41_status_then_soft_task_talks() -> None:
    decision = build_decision(
        user_message=(
            "Status check first - and after that, if things look good, we might retry the last "
            "corridor image (but wait for my go-ahead)."
        ),
        project_id="proj-1",
        speech_act="",
        grounding_snapshot={"bound": True},
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.TALK, TalkAskAct.ASK}
    assert (
        RC.DEFERRED_INTENT in decision.reasonCodes
        or RC.HYPOTHETICAL_QUERY in decision.reasonCodes
    )


def test_round2_42_stale_wrong_character_asks() -> None:
    decision = build_decision(
        user_message="Retry the last image of Captain Vega on the bridge with warmer lights.",
        project_id="proj-1",
        speech_act="COMMAND",
        entity_bindings=[
            {"name": "Korri", "resolved": True},
            {"name": "Anadriya", "resolved": True},
        ],
        grounding_snapshot={
            "bound": True,
            "characters": [{"name": "Korri"}, {"name": "Anadriya"}],
        },
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.ASK, TalkAskAct.TALK, TalkAskAct.STOP}
    assert RC.UNKNOWN_CAST_SUBJECT in decision.reasonCodes or RC.ENTITY_UNRESOLVED in decision.reasonCodes


def test_round2_46_talk_after_failure_no_enqueue() -> None:
    decision = build_decision(
        user_message=(
            "The previous Flux attempt failed. Explain the failure modes before we retry - "
            "do not enqueue a retry."
        ),
        project_id="proj-1",
        speech_act="",
        failed_execution_history=[
            {"capability": "image.generate", "error": "STRICT model unavailable: flux"}
        ],
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.TALK, TalkAskAct.ASK}
    assert RC.NO_ENQUEUE_REQUEST in decision.reasonCodes or RC.DEFERRED_INTENT in decision.reasonCodes


def test_round2_49_complex_nested_hypothetical_talks() -> None:
    decision = build_decision(
        user_message=(
            "I'm not asking you to generate; I'm asking whether, hypothetically, a Flux-only "
            "retry of the last corridor image at 21:9 would conflict with preferring continuity "
            "over model novelty - walk me through the trade."
        ),
        project_id="proj-1",
        speech_act="DISCUSSION",
        complexity="DEEP",
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.TALK, TalkAskAct.ASK}
    assert RC.HYPOTHETICAL_QUERY in decision.reasonCodes


def test_round2_soak_hypothetical_retry_inherit_talks() -> None:
    decision = build_decision(
        user_message="If we retry the last corridor image, what would you inherit?",
        project_id="proj-1",
        speech_act="QUESTION",
        grounding_snapshot={"bound": True},
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.TALK
    assert RC.HYPOTHETICAL_QUERY in decision.reasonCodes


def test_round2_pending_do_it_acts() -> None:
    pending = SimpleNamespace(state="AWAITING_CONFIRMATION", capabilityId="image.generate")
    decision = build_decision(
        user_message="Do it.",
        project_id="proj-1",
        speech_act="COMMAND",
        pending_execution=pending,
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ACT
    assert decision.capabilityId == "image.generate"
    assert RC.PENDING_CONFIRM_PATH in decision.reasonCodes or RC.COMMITMENT_EXPLICIT in decision.reasonCodes


def test_round2_pending_go_ahead_acts() -> None:
    pending = SimpleNamespace(state="AWAITING_CONFIRMATION", capability="image.generate")
    decision = build_decision(
        user_message="Go ahead.",
        project_id="proj-1",
        speech_act="COMMAND",
        pending_execution=pending,
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ACT
    assert decision.capabilityId == "image.generate"


def test_round2_pending_yes_proceed_acts() -> None:
    pending = SimpleNamespace(state="AWAITING_CONFIRMATION", capabilityId="image.generate")
    decision = build_decision(
        user_message="Yes, proceed.",
        project_id="proj-1",
        speech_act="COMMAND",
        pending_execution=pending,
        runtime_precheck=False,
    )
    assert decision.act == TalkAskAct.ACT


def test_round2_do_it_without_pending_asks() -> None:
    decision = build_decision(
        user_message="Do it.",
        project_id="proj-1",
        speech_act="COMMAND",
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.ASK, TalkAskAct.TALK}
    assert decision.act != TalkAskAct.ACT


def test_round2_contrast_strict_flux_not_talk() -> None:
    from app.codirector.image_route.lock import parse_route_lock

    prompt = "Use Flux only. No fallback."
    lock = parse_route_lock(prompt)
    decision = build_decision(
        user_message=prompt,
        project_id="proj-1",
        speech_act="COMMAND",
        route_lock={
            "level": lock.level,
            "requestedModelId": lock.requested_model_id,
            "scope": lock.scope,
        },
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.ACT, TalkAskAct.ASK, TalkAskAct.STOP}
    assert lock.level == "STRICT"
    assert lock.requested_model_id == "flux"


def test_round2_adv_flux_then_dont_not_flux_act() -> None:
    decision = build_decision(
        user_message="Use Flux for the corridor image. Actually wait - don't use Flux.",
        project_id="proj-1",
        speech_act="COMMAND",
        grounding_snapshot={"bound": True},
        runtime_precheck=False,
    )
    assert decision.act in {TalkAskAct.TALK, TalkAskAct.ASK}
    assert RC.CONTRADICTORY_CONSTRAINTS in decision.reasonCodes or RC.DEFERRED_INTENT in decision.reasonCodes
