"""Approved project voices bind as H3 ref_audios â€” never invented; not exact-script TTS."""

from __future__ import annotations

import inspect
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from app.director_timeline_w46.contracts import BatchBlock, DurationState, TimelinePromptSegment
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.direct_reference import DirectReferenceItem, DirectReferencePayload
from app.director_timeline_w46.generation.registry import get_registry
from app.director_timeline_w46.generation.voice_bind import (
    apply_approved_voices,
    resolve_approved_voice_audio,
)


def _request(**kwargs) -> TimelineGenerationRequest:
    body = {
        "projectId": "proj",
        "sceneId": "scene",
        "batchBlockId": "bb",
        "executionSnapshotId": "snap",
        "generatorId": "minimax-h3-t2v-local",
        "generationMode": "reference",
        "prompt": "Korri says hello to Anadriya.",
        "providerOptions": {
            "originalGeneratorId": "minimax-h3",
            "authoredPrompt": "Korri says hello to Anadriya.",
            "r2v": {
                "mechanism": "h3_ref2va",
                "slots": [
                    {"role": "character", "assetId": "hero-k", "label": "Korri", "pictureIndex": 1},
                ],
            },
        },
    }
    body.update(kwargs)
    return TimelineGenerationRequest(**body)


def _batch() -> BatchBlock:
    return BatchBlock(
        sceneId="scene",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=8.0),
        promptSegments=[TimelinePromptSegment(text="Korri says hello", start=0, length=8)],
        references=[
            {
                "kind": "characterIdentity",
                "identityIds": ["char-k"],
                "identityNames": ["Korri"],
                "identityAssetIds": ["hero-k"],
                "consumed": True,
            }
        ],
    )


def _db(*, approval="approved", project_id="proj", asset_project="proj", voice_id="voice-k", is_global=False):
    profile = MagicMock()
    profile.project_id = project_id
    profile.active_voice_profile_id = voice_id
    profile.name = "Korri"
    profile.is_global = is_global
    voice = MagicMock()
    voice.id = voice_id
    voice.project_id = project_id
    voice.character_profile_id = "char-k"
    voice.approval_status = approval
    voice.approved_preview_asset_id = "audio-k"
    voice.reference_asset_id = None
    asset = MagicMock()
    asset.project_id = asset_project
    asset.path = r"C:\tmp\audio-k.wav"
    asset.kind = "audio"

    def _get(model, key):
        if key == "char-k":
            return profile
        if key == voice_id:
            return voice
        if key == "audio-k":
            return asset
        return None

    db = MagicMock()
    db.get.side_effect = _get
    return db


def _dr_request() -> TimelineGenerationRequest:
    payload = DirectReferencePayload(
        projectId="proj",
        sceneId="scene",
        batchId="bb",
        generatorId="minimax-h3-t2v-local",
        characters=[
            DirectReferenceItem(
                kind="character",
                canonicalTag="@Korri",
                bindingId="bind-k",
                assetId="hero-k",
                assetType="image",
                approved=True,
                identityId="char-k",
                ordinal=1,
            )
        ],
        sockets=[],
    )
    return _request(
        providerOptions={
            "originalGeneratorId": "minimax-h3",
            "authoredPrompt": "Korri says hello to Anadriya.",
            "directReferences": payload.model_dump(),
            "r2v": {
                "mechanism": "h3_ref2va",
                "slots": [
                    {"role": "character", "assetId": "hero-k", "label": "@Korri", "pictureIndex": 1},
                ],
            },
        }
    )


def test_resolve_requires_approved_same_project_asset():
    assert resolve_approved_voice_audio(_db(), "proj", "char-k")["assetId"] == "audio-k"
    assert resolve_approved_voice_audio(_db(approval="draft"), "proj", "char-k") is None
    assert resolve_approved_voice_audio(_db(project_id="other"), "proj", "char-k") is None
    assert resolve_approved_voice_audio(_db(asset_project="other"), "proj", "char-k") is None


def test_resolve_global_character_current_voice_from_other_project():
    home = _db(project_id="home-a", asset_project="home-a", is_global=True)
    assert resolve_approved_voice_audio(home, "proj-b", "char-k")["assetId"] == "audio-k"
    local = _db(project_id="home-a", asset_project="home-a", is_global=False)
    assert resolve_approved_voice_audio(local, "proj-b", "char-k") is None


def test_apply_binds_h3_audio_slot_without_rewriting_timed_prompt():
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    request = _request()
    authored = request.prompt
    result = apply_approved_voices(_db(), request, _batch(), caps=caps)
    assert result["applied"] is True
    assert result["voices"][0]["assetId"] == "audio-k"
    assert result["exactScriptDialogue"] is False
    assert result["control"] == "voice_timbre_ref_only"
    slots = ((request.providerOptions or {}).get("r2v") or {}).get("slots") or []
    audio = next(slot for slot in slots if slot.get("role") == "audio")
    assert audio["assetId"] == "audio-k"
    assert audio["audioIndex"] == 1
    assert request.prompt == authored
    assert "<Audio" not in request.prompt
    assert request.providerOptions["characterVoices"]["applied"] is True
    assert request.providerOptions["characterVoices"]["exactScriptDialogue"] is False


def test_apply_from_direct_reference_cast_identity():
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    request = _dr_request()
    batch = BatchBlock(
        sceneId="scene",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=8.0),
        promptSegments=[TimelinePromptSegment(text="Korri says hello", start=0, length=8)],
        references=[],
    )
    result = apply_approved_voices(_db(), request, batch, caps=caps)
    assert result["applied"] is True
    assert result["directReferenceAudioInjected"] is True
    slots = ((request.providerOptions or {}).get("r2v") or {}).get("slots") or []
    audio = [s for s in slots if s.get("role") == "audio"]
    assert len(audio) == 1
    assert audio[0]["assetId"] == "audio-k"
    direct = (request.providerOptions or {}).get("directReferences") or {}
    assert any(str(a.get("bindingId") or "").startswith("approved_voice:") for a in (direct.get("audio") or []))
    sockets = direct.get("sockets") or []
    assert any(str(s.get("socket") or "").startswith("ref_audio_") for s in sockets)


def test_apply_does_not_invent_voices_when_none_approved():
    db = MagicMock()
    db.get.return_value = None
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    request = _request()
    result = apply_approved_voices(db, request, _batch(), caps=caps)
    assert result["applied"] is False
    assert result["missing"] == ["Korri"]
    slots = ((request.providerOptions or {}).get("r2v") or {}).get("slots") or []
    assert not any(slot.get("role") == "audio" for slot in slots)


def test_ltx_does_not_silently_drop_or_bind_h3_audio():
    from app.director_timeline_w46.generation.adapter import validate_against_capabilities
    from app.director_timeline_w46.generation.r2v import R2VSlot

    caps = get_registry().capabilities("ltx-2.5-distilled")
    request = _request(generatorId="ltx-2.5-distilled")
    result = apply_approved_voices(_db(), request, _batch(), caps=caps)
    assert result["applied"] is False
    assert result["reason"] == "generator_has_no_audio_reference"
    request.providerOptions["r2v"]["slots"] = [
        R2VSlot(role="character", assetId="hero-k", label="Korri", pictureIndex=1).model_dump(),
        R2VSlot(role="audio", assetId="audio-k", label="Korri", audioIndex=1).model_dump(),
    ]
    blocked = validate_against_capabilities(caps, request)
    assert blocked.ok is False
    assert any("voice" in err.lower() for err in blocked.errors)


def test_submit_batch_generation_wires_apply_approved_voices():
    from app.director_timeline_w46 import orchestrator

    src = inspect.getsource(orchestrator.submit_batch_generation)
    assert "apply_approved_voices" in src
    assert "from .generation.voice_bind import apply_approved_voices" in src
    assert "apply_character_identity(" not in src


def test_retake_range_reaches_submit_batch_generation():
    from app.director_timeline_w46 import orchestrator

    src = inspect.getsource(orchestrator.retake_range)
    assert "submit_batch_generation(" in src


def test_submit_invokes_apply_approved_voices_at_runtime():
    from app.director_timeline_w46 import orchestrator
    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.director_timeline_w46.generation.direct_reference import DirectReferencePayload

    calls: list[str] = []

    def _fake_apply(db, request, batch, *, caps=None):
        calls.append(request.generatorId)
        request.providerOptions = dict(request.providerOptions or {})
        request.providerOptions["characterVoices"] = {
            "applied": True,
            "voices": [{"assetId": "audio-k"}],
            "missing": [],
            "control": "voice_timbre_ref_only",
            "exactScriptDialogue": False,
        }
        return {"ok": True, "applied": True, "voices": [{"assetId": "audio-k"}], "missing": []}

    class _Caps:
        supportsTimelineGeneration = True
        executable = True
        disabledReason = None
        readiness = "Ready"
        label = "MiniMax H3"
        id = "minimax-h3-t2v-local"
        supportsAudioReferences = True
        executionType = "local"
        supportsQueuedCancel = False
        supportsRunningCancel = False

    class _Adapter:
        id = "minimax-h3-t2v-local"
        capabilities = _Caps()

        def validate(self, request):
            return MagicMock(ok=True, errors=[], warnings=[])

        def submit(self, request):
            sub = MagicMock()
            sub.status = "queued"
            sub.providerJobId = None
            sub.internalJobId = "job-1"
            sub.queueJobId = "queue-1"
            sub.providerMetadata = {}
            sub.apiUsed = False
            return sub

    batch = BatchBlock(
        id="bb1",
        sceneId="scene",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="hi", start=0, length=5)],
        references=[],
        status="Draft",
    )
    master = SceneTimelineMaster(
        sceneId="scene",
        sceneGeneratorId="minimax-h3-t2v-local",
        batchBlocks=[batch],
        executionSnapshots={},
    )
    req = _request(batchBlockId="bb1", executionSnapshotId="snap1")
    snap = MagicMock(id="snap1", batchBlockId="bb1", immutable=True, continuityState={})
    patches = {
        "voice_apply": patch(
            "app.director_timeline_w46.generation.voice_bind.apply_approved_voices",
            side_effect=_fake_apply,
        ),
        "load_master": patch(
            "app.director_timeline_w46.orchestrator.store.load_master",
            return_value={"ok": True, "master": master.model_dump()},
        ),
        "model_validate": patch(
            "app.director_timeline_w46.orchestrator.SceneTimelineMaster.model_validate",
            return_value=master,
        ),
        "list_generators": patch(
            "app.director_timeline_w46.capabilities.list_generators",
            return_value=[_Caps()],
        ),
        "get_registry": patch("app.director_timeline_w46.generation.registry.get_registry"),
        "get_generator": patch(
            "app.director_timeline_w46.orchestrator.get_generator",
            return_value=MagicMock(locality="local"),
        ),
        "validate_duration": patch(
            "app.director_timeline_w46.orchestrator.validate_duration",
            return_value={"ok": True},
        ),
        "prep_snap": patch(
            "app.director_timeline_w46.orchestrator._prepare_and_store_snapshot",
            return_value=snap,
        ),
        "get_scene": patch(
            "app.director_timeline_w46.orchestrator.store.get_scene",
            return_value=MagicMock(aspect_ratio="16:9"),
        ),
        "load_tl": patch(
            "app.director_timeline_w46.orchestrator._load_director_timeline",
            return_value=None,
        ),
        "bind_anchor": patch(
            "app.director_timeline_w46.orchestrator._bind_video_reference_anchor",
            return_value=[],
        ),
        "bridge": patch(
            "app.director_timeline_w46.continuity.active_bridge_for_target",
            return_value=None,
        ),
        "temporal": patch(
            "app.codirector.video_intelligence.service.ensure_temporal_packet_before_submit",
            return_value=None,
        ),
        "packet_blocks": patch(
            "app.codirector.video_intelligence.service.packet_blocks_submit",
            return_value=False,
        ),
        "save_master": patch(
            "app.director_timeline_w46.orchestrator.store.save_master",
            return_value=None,
        ),
        "build_dr": patch(
            "app.director_timeline_w46.generation.direct_reference.build_direct_reference_payload",
            return_value=DirectReferencePayload(
                projectId="proj",
                sceneId="scene",
                batchId="bb1",
                generatorId="minimax-h3-t2v-local",
            ),
        ),
        "delivery_error": patch(
            "app.director_timeline_w46.generation.direct_reference.delivery_error",
            return_value=None,
        ),
        "build_req": patch(
            "app.director_timeline_w46.generation.request_builder.build_timeline_generation_request",
            return_value=req,
        ),
        "preflight": patch(
            "app.director_timeline_w46.generation.runtime_dependency_preflight.preflight_generation_dependencies",
            return_value={"ok": True},
        ),
        "watcher": patch(
            "app.director_timeline_w46.generation.watcher.start_completion_watcher",
            MagicMock(),
        ),
        "enqueue": patch(
            "app.codirector.executive.imagegen_adapter.schedule_job_queue_enqueue",
            MagicMock(),
        ),
    }

    with ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}
        mocks["get_registry"].return_value.get.return_value = _Adapter()
        db = MagicMock()
        db.commit = MagicMock()
        out = orchestrator.submit_batch_generation(db, "proj", "scene", "bb1")

    assert mocks["voice_apply"].called, out
    assert calls == ["minimax-h3-t2v-local"]


def test_entity_cast_ref_binds_approved_voice():
    """Cade is stored as kind=entity, not characterIdentity â€” still bind his voice."""
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    batch = BatchBlock(
        sceneId="scene",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[],
        references=[
            {
                "kind": "entity",
                "role": "character",
                "identityId": "char-k",
                "label": "Cade",
                "assetId": "hero-k",
            }
        ],
        speechWindows=[
            {
                "start": 15.0,
                "end": 30.0,
                "speechKind": "prompt_dialogue",
                "speakers": [{"characterId": "char-k", "speakerName": "Cade", "text": "Where is the Adept?"}],
            }
        ],
    )
    result = apply_approved_voices(_db(), _request(), batch, caps=caps)
    assert result["applied"] is True
    assert result["voices"][0]["characterId"] == "char-k"
    assert any(isinstance(ref, dict) and ref.get("kind") == "characterVoice" for ref in batch.references)
