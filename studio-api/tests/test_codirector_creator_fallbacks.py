"""Creator fallbacks and named-surface admission."""

from __future__ import annotations

import asyncio
import json
import uuid

from app.character_identity.coverage import compute_coverage
from app.codirector.durable.admission import exposed_tool_ids, named_surface
from app.codirector.durable.bind import (
    bind_request_arguments,
    ordered_execution_plan,
    timeline_execution_plan,
)
from app.codirector.tools.definitions import ToolContext
from app.db import Project, SessionLocal, init_db


def test_missing_sheet_views_do_not_block_start():
    coverage = compute_coverage(
        present_roles=[],
        has_physical_details=True,
        has_personality=True,
        has_performance=False,
        has_wardrobe=False,
        voice_state="UNASSIGNED",
    )
    assert not any(str(item).startswith("Missing visual references") for item in coverage.critical_blockers)
    assert "reference sheet can be created" in coverage.next_action


def test_unset_generator_uses_qwen_front_path():
    from app.codirector.tools.handlers.character_creator import _crs_generator_sources

    sources = _crs_generator_sources({}, pack={})
    local = sources["local"][0]
    assert local["family"] == "qwen2512"
    assert sources.get("api") is None


def test_profile_without_image_uses_front_reference_sentence():
    from app.codirector.durable.approval import _verified_wording

    text = _verified_wording(
        "character_creator.propose_visual_sheet",
        {"characterName": "Harbor"},
    )
    assert "There isn’t an existing character image" in text
    assert "front reference" in text
    assert "multi-view" not in text.lower()


def test_existing_hero_wording_uses_that_image():
    from app.codirector.durable.approval import _verified_wording

    text = _verified_wording(
        "character_creator.propose_visual_sheet",
        {"characterName": "Harbor", "heroAssetId": "asset-1"},
    )
    assert "existing image" in text
    assert "multi-view" not in text.lower()


def test_prop_without_reference_selects_qwen():
    init_db()
    project_id = f"prop-fb-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    db.merge(Project(id=project_id, name="Prop Fallback"))
    db.commit()
    try:
        args, refusal = bind_request_arguments(
            db,
            tool_id="prop_creator.generate_view",
            arguments={},
            user_text="Use Prop Creator to create a lantern as a prop",
            project_id=project_id,
        )
    finally:
        db.close()
    assert refusal is None
    assert args["local_family"] == "qwen2512"
    assert args["generatorSources"]["local"][0]["family"] == "qwen2512"


def test_environment_without_reference_selects_qwen():
    init_db()
    project_id = f"env-fb-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    db.merge(Project(id=project_id, name="Environment Fallback"))
    db.commit()
    try:
        args, refusal = bind_request_arguments(
            db,
            tool_id="ers.generate",
            arguments={},
            user_text="Create a new environment called the night dock",
            project_id=project_id,
        )
    finally:
        db.close()
    assert refusal is None
    assert args["model"] == "qwen2512"
    assert args["forceWorkflowKey"] == "qwen2512.txt2img"
    assert not args.get("sourceAssetId")


def test_compound_timeline_plan_excludes_other_tools():
    text = "Create a scene, set it to 10 seconds, then attach a reference"
    plan = timeline_execution_plan(text)
    assert plan is not None
    assert [step["toolId"] for step in plan] == ["create_scene", "references.attach"]
    assert plan[0]["arguments"]["durationSec"] == 10
    admitted = exposed_tool_ids(surface="timeline", user_text=text)
    assert admitted == ["create_scene", "references.attach"]
    assert "timeline.propose_execute_inpaint" not in admitted
    assert ordered_execution_plan(text) == plan


def test_named_voice_and_audio_surfaces_do_not_open_the_registry():
    assert named_surface("please use Voice Studio") == "voice"
    assert named_surface("please use Audio Studio") == "audio"
    voice = exposed_tool_ids(surface="voice", user_text="use Voice Studio")
    audio = exposed_tool_ids(surface="audio", user_text="use Audio Studio")
    assert voice
    assert audio
    assert all(item.startswith(("voice.", "voice_performance.", "voice_environment.")) for item in voice)
    assert all(item.startswith("audio.") for item in audio)
    assert "voice_performance.get_status" in voice
    assert "audio.status" in audio
    assert "propose_image_generate" not in voice
    assert "create_scene" not in audio


def test_voice_status_route_returns_a_downstream_result():
    from app.codirector.tools.handlers import voice_performance

    init_db()
    db = SessionLocal()
    try:
        result = asyncio.run(voice_performance.get_status(ToolContext(db=db, project_id="voice-route"), {}))
    finally:
        db.close()
    assert result["ok"] is True
    assert "indexTts2Runtime" in result
    assert result["mock"] is False


def test_audio_status_route_returns_a_downstream_result():
    from app.codirector.tools.handlers import audio_studio_tools

    init_db()
    project_id = f"audio-fb-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    db.merge(Project(id=project_id, name="Audio Fallback"))
    db.commit()
    try:
        result = asyncio.run(audio_studio_tools.status(ToolContext(db=db, project_id=project_id), {}))
    finally:
        db.close()
    assert result["ok"] is True
    assert result["projectId"] == project_id
    assert "libraryCount" in result
    assert result["mock"] is False


def test_stored_plan_round_trip_keeps_only_planned_tools():
    from app.codirector.durable.journal import load_proposal_link, save_proposal_link

    plan = timeline_execution_plan("Create a scene, set it to 10 seconds, then attach a reference")
    proposal_id = f"plan-{uuid.uuid4().hex[:8]}"
    save_proposal_link(
        proposal_id=proposal_id,
        originating_workflow_id=f"wf-{proposal_id}",
        project_id="project",
        scene_id=None,
        tool_id="create_scene",
        intended_text="",
        approval_id=f"approve:{proposal_id}",
        plan=plan,
    )
    stored = load_proposal_link(proposal_id)
    assert stored is not None
    saved = json.loads(stored["plan_json"])
    assert [step["toolId"] for step in saved] == ["create_scene", "references.attach"]
    assert "timeline.propose_execute_inpaint" not in stored["plan_json"]


def test_timeline_scene_binds_a_unique_character_name():
    from app.character_identity.models import CharacterProfileRow

    init_db()
    project_id = f"cast-{uuid.uuid4().hex[:8]}"
    other_id = f"cast-{uuid.uuid4().hex[:8]}"
    local_id = f"local-{uuid.uuid4().hex[:8]}"
    global_id = f"global-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    db.merge(Project(id=project_id, name="Cast"))
    db.merge(Project(id=other_id, name="Elsewhere"))
    db.add(CharacterProfileRow(id=local_id, project_id=project_id, name="Harbor", slug="harbor-local"))
    db.add(
        CharacterProfileRow(
            id=global_id,
            project_id=other_id,
            name="Harbor",
            slug="harbor-global",
            is_global=True,
        )
    )
    db.commit()
    try:
        args, refusal = bind_request_arguments(
            db,
            tool_id="create_scene",
            arguments={"characterId": "invented-id"},
            user_text="Create a scene with Harbor sitting by the window, 16:9",
            project_id=project_id,
        )
    finally:
        db.close()
    assert refusal is None
    assert args["characterId"] == local_id
    assert args["characterName"] == "Harbor"
    assert args["identityId"] == local_id
    assert args["aspectRatio"] == "16:9"
    assert "invented-id" not in json.dumps(args)


def test_timeline_scene_uses_one_global_character_when_the_project_has_none():
    from app.character_identity.models import CharacterProfileRow

    init_db()
    project_id = f"cast-{uuid.uuid4().hex[:8]}"
    other_id = f"cast-{uuid.uuid4().hex[:8]}"
    global_id = f"global-{uuid.uuid4().hex[:8]}"
    unique_name = f"Quill{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    db.merge(Project(id=project_id, name="Cast"))
    db.merge(Project(id=other_id, name="Elsewhere"))
    db.add(
        CharacterProfileRow(
            id=global_id,
            project_id=other_id,
            name=unique_name,
            slug=unique_name.lower(),
            is_global=True,
        )
    )
    db.commit()
    try:
        args, refusal = bind_request_arguments(
            db,
            tool_id="create_scene",
            arguments={},
            user_text=f"Use {unique_name} in the scene",
            project_id=project_id,
        )
    finally:
        db.close()
    assert refusal is None
    assert args["characterId"] == global_id
    assert args["characterName"] == unique_name


def test_timeline_scene_refuses_a_missing_or_ambiguous_name_without_asking_for_an_id():
    from app.character_identity.models import CharacterProfileRow
    from app.codirector.durable.agent import _operation_tool

    init_db()
    project_id = f"cast-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    db.merge(Project(id=project_id, name="Cast"))
    db.commit()
    try:
        _missing, missing_refusal = bind_request_arguments(
            db,
            tool_id="create_scene",
            arguments={},
            user_text="Use Zorpqux in the scene",
            project_id=project_id,
        )
        for suffix in ("a", "b"):
            db.add(
                CharacterProfileRow(
                    id=f"dup-{suffix}-{uuid.uuid4().hex[:8]}",
                    project_id=project_id,
                    name="Alex",
                    slug=f"alex-{suffix}",
                )
            )
        db.commit()
        _duplicate, duplicate_refusal = bind_request_arguments(
            db,
            tool_id="references.attach",
            arguments={"characterId": "invented"},
            user_text="Create a scene with Alex",
            project_id=project_id,
        )
    finally:
        db.close()
    assert missing_refusal == "I couldn't find Zorpqux in the current project or available global characters."
    assert "characterId" not in missing_refusal
    assert duplicate_refusal == "I found more than one character named Alex. Which one would you like me to use?"
    assert "characterId" not in (duplicate_refusal or "")
    assert _operation_tool("Create a Timeline scene with Harbor", {"create_scene"}) == "create_scene"
