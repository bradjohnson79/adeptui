"""Co-Director admits the existing Voice Studio and Audio Studio tools."""

import json
import uuid

from app.character_identity.models import CharacterProfileRow
from app.codirector.durable.admission import (
    audio_operation,
    classify_turn_mode,
    exposed_tool_ids,
    named_surface,
    resolve_admitted_tool,
)
from app.codirector.durable.bind import bind_request_arguments
from app.codirector.durable.execute import durable_approval_required
from app.codirector.durable.wording import project_creator_reply
from app.codirector.tools.registry import find
from app.db import Project, SessionLocal, init_db


def test_bare_studio_names_do_not_open_the_registry():
    voice = exposed_tool_ids(surface="voice", user_text="use Voice Studio")
    audio = exposed_tool_ids(surface="audio", user_text="use Audio Studio")
    assert voice
    assert audio
    assert all(item.startswith(("voice.", "voice_performance.", "voice_environment.")) for item in voice)
    assert all(item.startswith("audio.") for item in audio)
    assert "character_creator.generate_voice_candidates" not in voice
    assert "propose_image_generate" not in voice
    assert "create_scene" not in audio


def test_voice_studio_command_admits_the_existing_voice_creator_tool():
    text = "Use Voice Studio to give Lar a deep, compassionate, heroic masculine voice."
    assert named_surface(text) == "voice"
    assert classify_turn_mode(text) == "MUTATE"
    admitted = exposed_tool_ids(surface="voice", user_text=text)
    assert admitted[0] == "character_creator.generate_voice_candidates"
    assert "character_creator.get_voice_status" in admitted
    assert "propose_image_generate" not in admitted
    assert "create_scene" not in admitted
    decision = resolve_admitted_tool(
        text,
        {
            "mode": "CONVERSATION",
            "confidence": "high",
            "reply": "I don't currently have access to a Voice Creator tool in this environment.",
        },
        allowed=set(admitted),
        fallback="character_creator.generate_voice_candidates",
    )
    assert decision.mode == "MUTATE"
    assert decision.tool_id == "character_creator.generate_voice_candidates"


def test_voice_question_is_a_read():
    text = "What voice is currently assigned to Lar?"
    assert classify_turn_mode(text) == "READ"
    admitted = exposed_tool_ids(surface=None, user_text=text)
    assert admitted[0] == "character_creator.get_voice_status"
    decision = resolve_admitted_tool(
        text,
        {"mode": "CONVERSATION", "confidence": "high", "reply": "I don't have access to Voice Studio."},
        allowed=set(admitted),
        fallback="character_creator.get_voice_status",
    )
    assert decision.mode == "READ"
    assert decision.tool_id == "character_creator.get_voice_status"


def test_audio_studio_commands_select_the_existing_generator():
    ambience = "Use Audio Studio to create subtle coffee-shop ambience with distant chatter and cups."
    impact = "Use Audio Studio to create a short metallic impact sound."
    music = "Use Audio Studio to create a low, restrained cinematic underscore."
    assert audio_operation(ambience) == "ambience"
    assert audio_operation(impact) == "sfx"
    assert audio_operation(music) == "music"
    assert classify_turn_mode(ambience) == "MUTATE"
    for text, tool_id in (
        (ambience, "audio.generate_ambience"),
        (impact, "audio.generate_sfx"),
        (music, "audio.generate_music"),
    ):
        admitted = exposed_tool_ids(surface="audio", user_text=text)
        assert admitted[0] == tool_id
        assert all(item.startswith("audio.") or item in {"audio.generate_ambience", "audio.generate_sfx", "audio.generate_music"} for item in admitted)
        assert "create_scene" not in admitted
        decision = resolve_admitted_tool(
            text,
            {"mode": "CONVERSATION", "confidence": "high", "reply": "I don't have an Audio Studio tool."},
            allowed=set(admitted),
            fallback=tool_id,
        )
        assert decision.mode == "MUTATE"
        assert decision.tool_id == tool_id
        assert find(tool_id).requires_approval is False
        assert durable_approval_required(tool_id, requires_approval=False) is True


def test_voice_and_audio_arguments_use_names_not_ids():
    init_db()
    project_id = f"voice-audio-{uuid.uuid4().hex[:8]}"
    name = f"Quill{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    try:
        db.add(Project(id=project_id, name="Voice audio bind"))
        db.add(
            CharacterProfileRow(
                id=str(uuid.uuid4()),
                project_id=project_id,
                name=name,
                slug=name.lower(),
                is_global=False,
            )
        )
        db.commit()
        voice_text = (
            f"Use Voice Studio to have {name} say, \"We should leave before sunrise.\" "
            "in a calm but serious tone."
        )
        args, refusal = bind_request_arguments(
            db,
            tool_id="character_creator.generate_voice_candidates",
            arguments={},
            user_text=voice_text,
            project_id=project_id,
        )
        assert refusal is None
        assert args["characterName"] == name
        assert args["characterId"]
        assert args["testLine"] == "We should leave before sunrise."
        assert args["performance"] == "calm but serious"
        assert args["candidateCount"] == 1
        invented, invented_refusal = bind_request_arguments(
            db,
            tool_id="character_creator.generate_voice_candidates",
            arguments={"testLine": "I will stand with you, no matter the cost.", "name": name},
            user_text=f"Use Voice Studio to give {name} a deep, compassionate, heroic masculine voice.",
            project_id=project_id,
        )
        assert invented_refusal is None
        assert "testLine" not in invented
        assert invented["characterName"] == name
        assert "deep" in invented["performance"]
        brief = json.loads(args["designBriefJson"])
        assert "characterId" not in brief
        audio_text = "Use Audio Studio to create subtle coffee-shop ambience with distant chatter and cups."
        audio_args, audio_refusal = bind_request_arguments(
            db,
            tool_id="audio.generate_ambience",
            arguments={},
            user_text=audio_text,
            project_id=project_id,
            scene_id="scene-current",
        )
        assert audio_refusal is None
        assert audio_args["prompt"] == audio_text
        assert audio_args["sceneId"] == "scene-current"
        assert audio_args["loopRequired"] is True
        assert "characterId" not in audio_args
    finally:
        db.close()


def test_voice_status_receipt_uses_the_handler_sentence():
    receipt = {
        "tool_id": "character_creator.get_voice_status",
        "execution_status": "succeeded",
        "evidence": {
            "read": {
                "result": {
                    "summary": "`character_creator.get_voice_status` completed successfully.",
                    "data": {
                        "characterId": "hidden-character",
                        "message": "Lar doesn't have an approved default voice yet.",
                    },
                }
            }
        },
    }
    spoken = project_creator_reply(json.dumps(receipt))
    assert spoken == "Lar doesn't have an approved default voice yet."
    assert "character_creator" not in spoken


def test_invalid_audio_duration_is_left_to_the_studio_default():
    init_db()
    db = SessionLocal()
    try:
        args, refusal = bind_request_arguments(
            db,
            tool_id="audio.generate_ambience",
            arguments={"durationSec": 0},
            user_text="Use Audio Studio to create subtle coffee-shop ambience.",
            project_id="duration-check",
        )
        assert refusal is None
        assert "durationSec" not in args
        assert project_creator_reply("'durationSec' must be at least 1.") == (
            "Audio Studio couldn't create that sound yet."
        )
    finally:
        db.close()


def test_voice_status_result_is_spoken_in_plain_language():
    receipt = {
        "toolId": "character_creator.get_voice_status",
        "status": "success",
        "summary": "`character_creator.get_voice_status` completed successfully.",
        "data": {
            "characterId": "hidden-character",
            "characterName": "Lar",
            "message": "Lar doesn't have an approved default voice yet.",
        },
    }
    spoken = project_creator_reply(json.dumps(receipt))
    assert spoken == "Lar doesn't have an approved default voice yet."
    assert "character_creator" not in spoken
    assert "hidden-character" not in spoken


def test_voice_and_audio_jobs_count_only_when_a_handler_id_exists():
    from app.codirector.durable.approval import _STORED_PROPOSAL_TOOLS, _studio_job_started, _verified_wording

    assert "audio.generate_ambience" in _STORED_PROPOSAL_TOOLS
    assert "character_creator.generate_voice_candidates" in _STORED_PROPOSAL_TOOLS
    assert _studio_job_started({"toolResult": {"ok": True}}) is False
    assert _studio_job_started({"toolResult": {"batchId": "batch-1", "status": "queued"}}) is True
    assert _studio_job_started({"candidateCount": 1, "persisted": True, "mock": False}) is True
    spoken = _verified_wording(
        "audio.generate_ambience",
        {"prompt": "Quiet coffee-shop chatter."},
    )
    assert spoken == "Audio Studio started that ambience. The clip is not ready yet."
    assert "batch-1" not in spoken


def test_magi_workspace_places_music_and_sfx_on_the_magi_owner():
    from app.codirector.durable.agent import _operation_tool

    music = (
        "Add a soft music track underneath this Renkoka scene for the full scene. "
        "Keep it subtle so it doesn't overpower her dialogue."
    )
    sfx = "At 40 seconds, add a sound effect for an object vanishing from Renkoka's hand."
    assert audio_operation(music) == "music"
    assert audio_operation(sfx) == "sfx"
    for text in (music, sfx):
        admitted = exposed_tool_ids(surface="magi", user_text=text)
        assert admitted[0] == "magi.audio.generate"
        assert "audio.generate_music" not in admitted
        assert "audio.generate_sfx" not in admitted
        assert _operation_tool(text, set(admitted)) == "magi.audio.generate"
        chosen = resolve_admitted_tool(
            text,
            {
                "mode": "MUTATE",
                "confidence": "high",
                "tool_id": "audio.generate_music",
                "reply": "A new music cue will be created in Audio Studio.",
            },
            allowed=set(admitted),
            fallback=_operation_tool(text, set(admitted)),
        )
        assert chosen.tool_id == "magi.audio.generate"
        assert chosen.mode == "MUTATE"
        refused = resolve_admitted_tool(
            text,
            {"mode": "CONVERSATION", "confidence": "high", "reply": "I can't add that."},
            allowed=set(admitted),
            fallback=_operation_tool(text, set(admitted)),
        )
        assert refused.tool_id == "magi.audio.generate"
    outside = exposed_tool_ids(surface=None, user_text=music)
    assert outside[0] == "audio.generate_music"
    studio = "Use Audio Studio to create a low, restrained cinematic underscore."
    named = exposed_tool_ids(surface="magi", user_text=studio)
    assert named[0] == "audio.generate_music"
    init_db()
    db = SessionLocal()
    try:
        music_args, music_refusal = bind_request_arguments(
            db,
            tool_id="magi.audio.generate",
            arguments={},
            user_text=music,
            project_id="magi-audio-bind",
        )
        sfx_args, sfx_refusal = bind_request_arguments(
            db,
            tool_id="magi.audio.generate",
            arguments={},
            user_text=sfx,
            project_id="magi-audio-bind",
        )
    finally:
        db.close()
    assert music_refusal is None
    assert music_args["kind"] == "music"
    assert music_args["range"] == "entire"
    assert music_args["prompt"] == music
    assert sfx_refusal is None
    assert sfx_args["kind"] == "sfx"
    assert sfx_args["prompt"] == sfx
    assert sfx_args["startSeconds"] == 40
    assert sfx_args["duration"] == 2.0
    assert "startSeconds" not in music_args


def test_magi_final_render_uses_the_magi_render_owner():
    from app.codirector.durable.agent import _operation_tool
    from app.codirector.durable.approval import _STORED_PROPOSAL_TOOLS

    text = "Final render this Renkoka scene with the dialogue, music, and sound effect that are already on it."
    admitted = exposed_tool_ids(surface="magi", user_text=text)
    assert admitted[0] == "magi.render"
    assert "magi.propose_finish" not in admitted
    assert "magi.upscale" not in admitted
    assert "magi.color.apply" not in admitted
    assert _operation_tool(text, set(admitted)) == "magi.render"
    chosen = resolve_admitted_tool(
        text,
        {"mode": "CONVERSATION", "confidence": "high", "tool_id": None, "reply": "I can't render that."},
        allowed=set(admitted),
        fallback=_operation_tool(text, set(admitted)),
    )
    assert chosen.tool_id == "magi.render"
    assert chosen.mode == "MUTATE"
    assert "magi.render" in _STORED_PROPOSAL_TOOLS
    init_db()
    db = SessionLocal()
    try:
        args, refusal = bind_request_arguments(
            db,
            tool_id="magi.render",
            arguments={"upscale": {"enabled": True, "target": "2560x1440"}},
            user_text=text,
            project_id="magi-render-bind",
        )
    finally:
        db.close()
    assert refusal is None
    assert args["profile"] == "final"
    assert "upscale" not in args


def test_voice_and_audio_failures_stay_in_plain_language():
    assert project_creator_reply("VOICE_PROVIDER_ERROR") == "Voice Studio couldn't start that voice generation."
    assert (
        project_creator_reply("audio.generate_ambience failed")
        == "Audio Studio couldn't create that sound yet."
    )
