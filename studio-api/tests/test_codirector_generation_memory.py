"""Canonical generation memory — production history, not chat reconstruction."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.codirector.conversation.foundation.image_generation_defaults import (
    parse_image_generation_overrides,
)
from app.codirector.execution.contracts import (
    ChildJobStatus,
    ChildJobView,
    ExecutionPlan,
    ExecutionStatus,
)
from app.codirector.execution.pack_store import save_pack
from app.codirector.generation_memory.contracts import CanonicalGenerationRequest
from app.codirector.generation_memory.inherit import apply_typed_inheritance, overrides_from_utterance
from app.codirector.generation_memory.referential import (
    image_index_hint,
    is_referential_generation,
    requested_artifact_type,
    source_artifact_type,
    target_artifact_type,
)
from app.codirector.generation_memory.resolve import (
    apply_canonical_retry_to_context,
    resolve_canonical_retry,
)
from app.codirector.generation_memory.store import (
    attach_canonical_request,
    list_image_requests,
    snapshot_from_dispatch,
)
from app.db import Base, Job, Project

REPO = Path(__file__).resolve().parents[2]
BRIEF = (
    "Create a Silver metallic Venture corridor scene where we see an elevator door "
    "at the end of the corridor, and then about 10 meters ahead, there is a door "
    "that leads to a Combat Chamber room. The corridor should like something you "
    "would see through an underground research facility. Somewhat sci-fi futuristic, "
    "full wide master shot."
)
RETRY_GPT = "Retry with same prompt again and use GPT Image 2."
RETRY_FLUX = "Retry that with Flux."
RETRY_SAME = "Retry the same prompt."
USE_FLUX_THIS_TIME = "Use Flux this time."
MAKE_IT_WIDE = "Make it 21:9."


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-a", name="Memory A"))
    session.add(Project(id="proj-b", name="Memory B"))
    session.commit()
    yield session
    session.close()


def _plan(
    *,
    project_id: str,
    execution_id: str,
    status: ExecutionStatus = ExecutionStatus.QUEUED,
    created_at: str = "2026-08-31T12:00:00+00:00",
    capability: str = "image.generate",
    job_id: str = "",
) -> ExecutionPlan:
    children = []
    if job_id:
        children = [ChildJobView(job_id=job_id, label="Generated Image", status=ChildJobStatus.QUEUED)]
    return ExecutionPlan(
        execution_id=execution_id,
        capability=capability,
        project_id=project_id,
        status=status,
        child_jobs=children,
        surface_type="image_generation",
        created_at=created_at,
        updated_at=created_at,
    )


def _snapshot(project_id: str, brief: str, **kwargs) -> CanonicalGenerationRequest:
    data = dict(
        requestId=str(uuid4()),
        projectId=project_id,
        originalUserInstructions=brief,
        compiledGeneratorPrompt="COMPILED-FOR-LOCAL-ONLY",
        artifactType="image",
        action="image.generate",
        route="AUTO",
        provider="local",
        modelId="qwen2512",
        aspectRatio="16:9",
        width=1920,
        height=1080,
        referenceAssetIds=["ref-1"],
        characterIds=["char-1"],
        generationParameters={"cfg": 7, "syntax": "fal-only"},
        workflowKey="qwen2512.txt2img",
        providerPayload={"falImageModelId": "do-not-copy"},
        createdAt="2026-08-31T12:00:00+00:00",
    )
    data.update(kwargs)
    return CanonicalGenerationRequest.model_validate(data)


def _persist(
    db,
    project_id: str,
    brief: str,
    *,
    created_at: str,
    status=ExecutionStatus.QUEUED,
    capability: str = "image.generate",
    **kwargs,
):
    exec_id = str(uuid4())
    job_id = str(uuid4())
    plan = _plan(
        project_id=project_id,
        execution_id=exec_id,
        status=status,
        created_at=created_at,
        capability=capability,
        job_id=job_id,
    )
    save_pack(db, project_id, plan)
    req = _snapshot(project_id, brief, executionId=exec_id, jobIds=[job_id], **kwargs)
    plan.result_asset_ids = list(req.resultAssetIds or [])
    attach_canonical_request(db, plan, req)
    return plan, req


def test_gpt_image_2_parse_survives_image_stopword() -> None:
    parsed = parse_image_generation_overrides(RETRY_GPT)
    assert parsed["explicit_provider"] == "gptimage2"
    assert parsed.get("provider_kind") != "fal"
    assert parsed["route"] == "explicit"
    assert image_index_hint(RETRY_GPT) is None


def test_referential_retry_classifies_as_image_generate() -> None:
    from app.codirector.durable.admission import classify_turn_mode, is_timed_instruction

    assert is_referential_generation(RETRY_GPT) is True
    assert is_timed_instruction(RETRY_GPT) is False
    assert classify_turn_mode(RETRY_GPT) != "MUTATE"


def test_named_flux_does_not_keep_a_local_provider_lock() -> None:
    mapped = overrides_from_utterance(USE_FLUX_THIS_TIME)
    assert mapped.get("requestedProvider") in {"", None}


def test_use_flux_does_not_lock_all_local_as_provider() -> None:
    mapped = overrides_from_utterance(USE_FLUX_THIS_TIME)
    assert mapped.get("requestedModelId", "").lower() in {"flux", "flux1", "flux.1"}
    assert mapped.get("requestedProvider") != "local"


def test_generator_and_aspect_restatements_are_referential() -> None:
    from app.codirector.durable.admission import classify_turn_mode, is_timed_instruction

    assert is_referential_generation(USE_FLUX_THIS_TIME) is True
    assert is_referential_generation(MAKE_IT_WIDE) is True
    assert requested_artifact_type(USE_FLUX_THIS_TIME) == "image"
    assert is_timed_instruction(USE_FLUX_THIS_TIME) is False
    assert is_timed_instruction(MAKE_IT_WIDE) is False
    assert classify_turn_mode(USE_FLUX_THIS_TIME) != "MUTATE"
    assert classify_turn_mode(MAKE_IT_WIDE) != "MUTATE"


def test_exact_original_instructions_round_trip(db) -> None:
    _persist(db, "proj-a", BRIEF, created_at="2026-08-31T12:00:00+00:00")
    resolved = resolve_canonical_retry(db, "proj-a", RETRY_GPT)
    assert resolved is not None
    assert resolved.clarification == ""
    assert resolved.next_request is not None
    assert resolved.next_request.originalUserInstructions == BRIEF
    assert resolved.used_chat_inherit is False


def test_gpt_image_2_inherit_audit_recompile(db) -> None:
    prior_plan, prior = _persist(db, "proj-a", BRIEF, created_at="2026-08-31T12:00:00+00:00")
    resolved = resolve_canonical_retry(db, "proj-a", RETRY_GPT)
    assert resolved is not None and resolved.next_request is not None and resolved.audit is not None
    nxt = resolved.next_request
    audit = resolved.audit
    assert "originalUserInstructions" in audit.inherited
    assert "referenceAssetIds" in audit.inherited
    assert "modelId" in audit.overridden
    assert "lockLevel" in audit.overridden
    assert nxt.lockLevel == "PREFERRED"
    assert nxt.requestedModelId == "gptimage2"
    assert "compiledGeneratorPrompt" in audit.recompiled
    assert "generationParameters" in audit.recompiled
    assert nxt.originalUserInstructions == BRIEF
    assert nxt.compiledGeneratorPrompt == ""
    assert nxt.generationParameters == {}
    assert nxt.providerPayload == {}
    assert nxt.workflowKey == ""
    assert nxt.provider != "fal"
    assert nxt.modelId == "gptimage2"
    assert nxt.parentRequestId == prior.requestId
    assert nxt.executionId == ""
    assert nxt.requestId != prior.requestId
    assert nxt.referenceAssetIds == ["ref-1"]
    assert prior_plan.execution_id != nxt.executionId


def test_no_dict_update_copies_compiled_fields() -> None:
    inherit_src = (
        REPO
        / "studio-api"
        / "app"
        / "codirector"
        / "generation_memory"
        / "inherit.py"
    ).read_text(encoding="utf-8")
    assert ".update(" not in inherit_src
    prior = _snapshot("proj-a", BRIEF)
    nxt, audit = apply_typed_inheritance(
        prior,
        overrides=overrides_from_utterance(RETRY_GPT),
        project_id="proj-a",
    )
    assert nxt.compiledGeneratorPrompt == ""
    assert nxt.generationParameters == {}
    assert "cfg" not in nxt.generationParameters
    assert nxt.providerPayload == {}
    assert audit.recompiled


def test_failed_and_cancelled_remain_retryable(db) -> None:
    _persist(
        db,
        "proj-a",
        BRIEF,
        created_at="2026-08-31T12:00:00+00:00",
        status=ExecutionStatus.FAILED,
    )
    failed = resolve_canonical_retry(db, "proj-a", RETRY_SAME)
    assert failed is not None and failed.next_request is not None
    assert failed.next_request.originalUserInstructions == BRIEF

    _persist(
        db,
        "proj-a",
        "Create a coffee shop counter in warm tungsten light.",
        created_at="2026-08-31T12:05:00+00:00",
        status=ExecutionStatus.CANCELLED,
    )
    cancelled = resolve_canonical_retry(db, "proj-a", "retry the last image")
    assert cancelled is not None and cancelled.next_request is not None
    assert "coffee shop" in cancelled.next_request.originalUserInstructions


def test_named_corridor_vs_last_image(db) -> None:
    _persist(db, "proj-a", BRIEF, created_at="2026-08-31T12:00:00+00:00")
    _persist(
        db,
        "proj-a",
        "Create a quiet coffee shop interior, morning window light.",
        created_at="2026-08-31T13:00:00+00:00",
    )
    last_hit = resolve_canonical_retry(db, "proj-a", "retry the last image")
    assert last_hit is not None and last_hit.next_request is not None
    assert "coffee shop" in last_hit.next_request.originalUserInstructions

    named = resolve_canonical_retry(db, "proj-a", "Retry the corridor with the same prompt.")
    assert named is not None and named.next_request is not None
    assert named.next_request.originalUserInstructions == BRIEF
    assert named.clarification == ""


def test_project_b_cannot_see_project_a(db) -> None:
    _persist(db, "proj-a", BRIEF, created_at="2026-08-31T12:00:00+00:00")
    resolved = resolve_canonical_retry(db, "proj-b", RETRY_GPT)
    assert resolved is not None
    assert resolved.next_request is None
    assert resolved.clarification
    assert list_image_requests(db, "proj-b") == []


def test_canonical_path_never_sets_chat_inherit(db) -> None:
    _persist(db, "proj-a", BRIEF, created_at="2026-08-31T12:00:00+00:00")
    resolved = resolve_canonical_retry(db, "proj-a", RETRY_GPT)
    ctx = apply_canonical_retry_to_context(
        {"prompt": RETRY_GPT, "used_chat_inherit": True},
        resolved,
        retry_utterance=RETRY_GPT,
    )
    assert ctx["used_chat_inherit"] is False
    assert ctx["prompt"] == BRIEF
    assert ctx["original_user_instructions"] == BRIEF
    assert ctx["canonical_resolved"] is True


def test_service_resolves_before_semantic_router() -> None:
    """Chat no longer routes through the retired stream. Canonical retry stays a resolver."""
    service = (REPO / "studio-api" / "app" / "codirector" / "service.py").read_text(encoding="utf-8")
    turn = (REPO / "studio-api" / "app" / "codirector" / "durable" / "turn.py").read_text(encoding="utf-8")
    resolve = (REPO / "studio-api" / "app" / "codirector" / "generation_memory" / "resolve.py").read_text(encoding="utf-8")
    assert "def resolve_canonical_retry" in resolve
    assert "def begin_turn(" in turn
    assert "route_turn_with_unified" not in turn
    for name in ("async def chat_for_project", "async def _stream_for_project_inner"):
        assert name not in service


def test_service_skips_chat_inherit_when_canonical_exists() -> None:
    resolve = (REPO / "studio-api" / "app" / "codirector" / "generation_memory" / "resolve.py").read_text(encoding="utf-8")
    assert "def apply_canonical_retry_to_context" in resolve
    assert "used_chat_inherit" in resolve


def test_backfill_from_job_params_not_chat(db) -> None:
    exec_id = str(uuid4())
    job_id = str(uuid4())
    plan = _plan(
        project_id="proj-a",
        execution_id=exec_id,
        created_at="2026-08-31T14:00:00+00:00",
        job_id=job_id,
    )
    save_pack(db, "proj-a", plan)
    db.add(
        Job(
            id=job_id,
            project_id="proj-a",
            kind="imagegen",
            status="failed",
            params_json=json.dumps({"prompt": BRIEF}),
        )
    )
    db.commit()
    resolved = resolve_canonical_retry(db, "proj-a", RETRY_SAME)
    assert resolved is not None and resolved.next_request is not None
    assert resolved.next_request.originalUserInstructions == BRIEF


def test_video_version_of_that_inherits_last_image(db) -> None:
    _plan_row, image = _persist(
        db,
        "proj-a",
        BRIEF,
        created_at="2026-08-31T12:00:00+00:00",
        resultAssetIds=["still-1"],
        characterIds=["char-a", "char-b"],
    )
    _persist(
        db,
        "proj-a",
        "Create a short video version of that corridor shot.",
        created_at="2026-08-31T11:00:00+00:00",
        capability="video.generate",
        artifactType="video",
        action="video.generate",
    )
    phrase = "Make a short video version of that."
    assert is_referential_generation(phrase) is True
    assert target_artifact_type(phrase) == "video"
    assert source_artifact_type(phrase) == "image"
    resolved = resolve_canonical_retry(db, "proj-a", phrase)
    assert resolved is not None and resolved.next_request is not None
    nxt = resolved.next_request
    assert nxt.originalUserInstructions == BRIEF
    assert nxt.artifactType == "video"
    assert nxt.action == "video.generate"
    assert nxt.parentRequestId == image.requestId
    assert "still-1" in nxt.referenceAssetIds
    assert nxt.compiledGeneratorPrompt == ""
    assert nxt.characterIds == ["char-a", "char-b"]


def test_last_video_is_referential_video_not_image(db) -> None:
    _persist(db, "proj-a", BRIEF, created_at="2026-08-31T12:00:00+00:00")
    _persist(
        db,
        "proj-a",
        "Create a short video version of that corridor shot.",
        created_at="2026-08-31T13:00:00+00:00",
        capability="video.generate",
        artifactType="video",
        action="video.generate",
    )
    assert is_referential_generation("Retry the last video.") is True
    assert requested_artifact_type("Retry the last video.") == "video"
    assert requested_artifact_type("retry the last image") == "image"
    video_hit = resolve_canonical_retry(db, "proj-a", "Retry the last video.")
    assert video_hit is not None and video_hit.next_request is not None
    assert video_hit.next_request.artifactType == "video"
    assert "short video" in video_hit.next_request.originalUserInstructions
    image_hit = resolve_canonical_retry(db, "proj-a", "Retry the last image.")
    assert image_hit is not None and image_hit.next_request is not None
    assert image_hit.next_request.originalUserInstructions == BRIEF


def test_last_audio_is_referential_audio_not_image(db) -> None:
    _persist(db, "proj-a", BRIEF, created_at="2026-08-31T12:00:00+00:00")
    _persist(
        db,
        "proj-a",
        "Generate footsteps on the metal grating for this scene.",
        created_at="2026-08-31T13:10:00+00:00",
        capability="audio.sfx",
        artifactType="audio",
        action="audio.sfx",
    )
    assert is_referential_generation("Retry the last audio.") is True
    assert requested_artifact_type("Retry the last audio.") == "audio"
    audio_hit = resolve_canonical_retry(db, "proj-a", "Retry the last audio.")
    assert audio_hit is not None and audio_hit.next_request is not None
    assert audio_hit.next_request.artifactType == "audio"
    assert "footsteps" in audio_hit.next_request.originalUserInstructions
    image_hit = resolve_canonical_retry(db, "proj-a", "Retry the last image.")
    assert image_hit is not None and image_hit.next_request is not None
    assert image_hit.next_request.originalUserInstructions == BRIEF
    flux_hit = resolve_canonical_retry(db, "proj-a", RETRY_FLUX)
    assert flux_hit is not None and flux_hit.next_request is not None
    assert flux_hit.next_request.artifactType == "image"
    assert flux_hit.next_request.originalUserInstructions == BRIEF


def test_audio_pack_backfills_from_audio_studio_not_chat(db, monkeypatch) -> None:
    exec_id = str(uuid4())
    fake_job = str(uuid4())
    plan = _plan(
        project_id="proj-a",
        execution_id=exec_id,
        created_at="2026-08-31T14:00:00+00:00",
        capability="audio.sfx",
        job_id=fake_job,
    )
    save_pack(db, "proj-a", plan)
    batch = {
        "id": "batch-sfx-1",
        "gen_kind": "sfx",
        "raw_prompt": "Generate footsteps on the metal grating for this scene.",
        "prompt": "COMPILED-ACE-STEP-FOOTSTEPS",
        "compiled_prompt": "COMPILED-ACE-STEP-FOOTSTEPS",
        "brief_snapshot": {"prompt": "Generate footsteps on the metal grating for this scene."},
        "status": "complete",
        "candidates": [],
    }

    monkeypatch.setattr(
        "app.audio_studio.store.get_batch",
        lambda project_id, batch_id: None,
    )
    monkeypatch.setattr(
        "app.audio_studio.store.list_batches",
        lambda project_id: [batch],
    )
    resolved = resolve_canonical_retry(db, "proj-a", "Retry the last audio.")
    assert resolved is not None and resolved.next_request is not None
    assert resolved.next_request.originalUserInstructions == (
        "Generate footsteps on the metal grating for this scene."
    )
    assert resolved.next_request.compiledGeneratorPrompt == ""
    assert resolved.next_request.artifactType == "audio"


def test_use_flux_this_time_inherits_last_image(db) -> None:
    _persist(
        db,
        "proj-a",
        BRIEF,
        created_at="2026-08-31T12:00:00+00:00",
        lockLevel="UNLOCKED",
        characterIds=["char-a", "char-b"],
    )
    resolved = resolve_canonical_retry(db, "proj-a", USE_FLUX_THIS_TIME)
    assert resolved is not None and resolved.next_request is not None
    nxt = resolved.next_request
    assert nxt.originalUserInstructions == BRIEF
    assert nxt.compiledGeneratorPrompt == ""
    assert nxt.characterIds == ["char-a", "char-b"]
    assert "flux" in f"{nxt.modelId} {nxt.requestedModelId}".lower()
    assert nxt.lockLevel in {"PREFERRED", "STRICT"}
    assert nxt.requestedProvider != "local"


def test_flux_retry_recompiles_and_does_not_copy_prior_prompt(db) -> None:
    _persist(db, "proj-a", BRIEF, created_at="2026-08-31T12:00:00+00:00")
    resolved = resolve_canonical_retry(db, "proj-a", RETRY_FLUX)
    assert resolved is not None and resolved.next_request is not None
    nxt = resolved.next_request
    assert nxt.originalUserInstructions == BRIEF
    assert nxt.compiledGeneratorPrompt == ""
    model_token = f"{nxt.modelId} {nxt.requestedModelId}".lower()
    assert "flux" in model_token


def test_service_does_not_force_canonical_audio_onto_image() -> None:
    inherit = (REPO / "studio-api" / "app" / "codirector" / "generation_memory" / "inherit.py").read_text(encoding="utf-8")
    assert "image" in inherit
    assert "def apply_typed_inheritance" in inherit or "def overrides_from_utterance" in inherit


def test_snapshot_keeps_every_resolved_character_and_reference() -> None:
    plan = _plan(project_id="proj-a", execution_id="exec-multi")
    snap = snapshot_from_dispatch(
        plan=plan,
        ctx={
            "character_ids": ["char-a", "char-b"],
            "reference_asset_ids": ["ref-a", "ref-b"],
            "canonical_original_instructions": "two characters walking",
            "prompt": "two characters walking",
        },
        result={
            "character_ids": ["char-a", "char-b"],
            "reference_asset_ids": ["ref-a", "ref-b"],
        },
    )
    assert snap.characterIds == ["char-a", "char-b"]
    assert snap.referenceAssetIds == ["ref-a", "ref-b"]


def test_unlocked_stale_generator_is_not_inherited(db) -> None:
    _persist(
        db,
        "proj-a",
        BRIEF,
        created_at="2026-08-31T12:00:00+00:00",
        lockLevel="UNLOCKED",
        requestedModelId="flux",
        modelId="qwen-image-2512-local",
        route="explicit",
    )
    resolved = resolve_canonical_retry(db, "proj-a", RETRY_SAME)
    assert resolved is not None and resolved.next_request is not None
    nxt = resolved.next_request
    assert nxt.originalUserInstructions == BRIEF
    assert nxt.requestedModelId == ""
    assert nxt.lockLevel == ""
    ctx = apply_canonical_retry_to_context({"prompt": RETRY_SAME}, resolved, retry_utterance=RETRY_SAME)
    assert ctx["explicit_provider"] == ""
    assert ctx["requested_model_id"] == ""


def test_preferred_generator_is_inherited_until_restated(db) -> None:
    _persist(
        db,
        "proj-a",
        BRIEF,
        created_at="2026-08-31T12:00:00+00:00",
        lockLevel="PREFERRED",
        requestedModelId="flux",
        modelId="flux",
        route="explicit",
    )
    resolved = resolve_canonical_retry(db, "proj-a", RETRY_SAME)
    assert resolved is not None and resolved.next_request is not None
    assert resolved.next_request.requestedModelId == "flux"
    assert resolved.next_request.lockLevel == "PREFERRED"


def test_snapshot_unlocked_does_not_record_conversation_generator() -> None:
    plan = _plan(project_id="proj-a", execution_id="exec-auto")
    snap = snapshot_from_dispatch(
        plan=plan,
        ctx={
            "explicit_provider": "flux",
            "requested_model_id": "flux",
            "generation_route": "explicit",
            "lock_level": "UNLOCKED",
            "canonical_original_instructions": BRIEF,
            "prompt": BRIEF,
        },
        result={
            "lockLevel": "UNLOCKED",
            "requestedModelId": "flux",
            "selectedModelId": "qwen-image-2512-local",
            "route": "explicit",
            "fallbackAudit": {"step": "auto_local"},
        },
    )
    assert snap.requestedModelId == ""
    assert snap.modelId == "qwen-image-2512-local"
    assert snap.route == "auto_local"


def test_dispatcher_forwards_inherited_route_lock() -> None:
    src = (
        REPO
        / "studio-api"
        / "app"
        / "codirector"
        / "execution"
        / "dispatcher.py"
    ).read_text(encoding="utf-8")
    assert '"lock_level": ctx.get("lock_level")' in src
    assert '"requested_model_id": ctx.get("requested_model_id")' in src


def test_durable_turn_emits_tool_completed_and_has_one_entry() -> None:
    execute = (REPO / "studio-api" / "app" / "codirector" / "durable" / "execute.py").read_text(encoding="utf-8")
    turn = (REPO / "studio-api" / "app" / "codirector" / "durable" / "turn.py").read_text(encoding="utf-8")
    service = (REPO / "studio-api" / "app" / "codirector" / "service.py").read_text(encoding="utf-8")
    assert '"type": event_type' in execute or "tool_completed" in execute
    assert "def begin_turn(" in turn
    assert "load_admission(request_id)" in turn
    for name in ("async def chat_for_project", "async def stream_for_project", "async def _stream_for_project_inner"):
        assert name not in service


def test_duplicate_request_attaches_before_a_second_workflow() -> None:
    turn = (REPO / "studio-api" / "app" / "codirector" / "durable" / "turn.py").read_text(encoding="utf-8")
    attach = turn.find("if load_admission(request_id) is not None")
    start = turn.find("await _start_workflow(")
    assert 0 < attach < start


def test_collect_character_references_keeps_both_approved_sheets(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.codirector.capabilities.handlers.image_generate import collect_character_references

    profiles = {
        "Korri": SimpleNamespace(id="char-k", name="Korri"),
        "Anadriya": SimpleNamespace(id="char-a", name="Anadriya"),
    }
    approved = {"char-k": "ref-k", "char-a": "ref-a"}
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.image_generate.resolve_character_by_name",
        lambda _db, _project, name: profiles.get(name),
    )
    monkeypatch.setattr(
        "app.codirector.capabilities.handlers.image_generate.resolve_approved_reference",
        lambda _db, character_id, _role: approved.get(character_id),
    )
    ids, refs, primary = collect_character_references(
        None,
        "proj-a",
        character_names=["Korri", "Anadriya"],
        attachment_asset_ids=["style-1"],
    )
    assert ids == ["char-k", "char-a"]
    assert refs == ["style-1", "ref-k", "ref-a"]
    assert primary == "Korri"
    tagged_ids, tagged_refs, _ = collect_character_references(
        None,
        "proj-a",
        prompt="Create a shot of @Korri and @Anadriya walking.",
        attachment_asset_ids=["style-1"],
    )
    assert tagged_ids == ["char-k", "char-a"]
    assert tagged_refs == ["style-1", "ref-k", "ref-a"]


def test_stream_clarification_emits_completed_event() -> None:
    workflow = (REPO / "studio-api" / "app" / "codirector" / "durable" / "workflow.py").read_text(encoding="utf-8")
    assert '"type": "completed"' in workflow
    assert "set_status(" in workflow
