"""A successful character search is consumed. The chat never shows the receipt."""

import json
import uuid

from app.character_identity.models import CharacterProfileRow
from app.codirector.durable.agent import _continue_after_lookup, set_turn_deps
from app.codirector.durable.bind import _best_visible_label, bind_request_arguments, visible_character_matches
from app.codirector.durable.deps import TurnDeps
from app.codirector.durable.wording import project_creator_reply
from app.db import Project, SessionLocal, init_db

SCENE = (
    "I want you to create a scene in Timeline where we see the character, {name} sitting at a table "
    "inside the Schnick Coffee shop with the silver thermos filled with green slimy liquid. "
    "He is sitting cross legged with his arms crossed looking out a nearby window on a bright sunny day."
)


def _profile(db, project_id: str, name: str, *, global_profile: bool) -> str:
    profile_id = str(uuid.uuid4())
    db.add(
        CharacterProfileRow(
            id=profile_id,
            project_id=project_id,
            name=name,
            slug=name.lower(),
            is_global=global_profile,
        )
    )
    db.commit()
    return profile_id


def test_incidental_words_do_not_discard_a_unique_global_match():
    init_db()
    home = f"home-{uuid.uuid4().hex[:8]}"
    other = f"other-{uuid.uuid4().hex[:8]}"
    name = f"Quill{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    db.merge(Project(id=home, name="Home"))
    db.merge(Project(id=other, name="Other"))
    db.commit()
    try:
        profile_id = _profile(db, other, name, global_profile=True)
        args, refusal = bind_request_arguments(
            db,
            tool_id="create_scene",
            arguments={},
            user_text=SCENE.format(name=name),
            project_id=home,
        )
    finally:
        db.close()
    assert refusal is None
    assert args["characterId"] == profile_id
    assert args["characterName"] == name
    assert "characterId" not in str(refusal)


def test_use_minimax_does_not_replace_the_named_character():
    """'Use MiniMax H3' names the generator. The character is the one after with."""

    init_db()
    project_id = f"gen-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    db.merge(Project(id=project_id, name="Feature"))
    db.commit()
    text = (
        "Create a new scene called FINAL SYSTEMS CERT \u2014 RENKOKA. Use MiniMax H3 Local, "
        "1 megapixel, 21:9. Create the first 15-second shot with Renkoka."
    )
    try:
        profile_id = _profile(db, project_id, "Renkoka", global_profile=False)
        args, refusal = bind_request_arguments(
            db,
            tool_id="create_scene",
            arguments={"characterName": "MiniMax", "engine": "MiniMax H3 Local"},
            user_text=text,
            project_id=project_id,
        )
    finally:
        db.close()
    assert refusal is None
    assert args["characterName"] == "Renkoka"
    assert args["characterId"] == profile_id
    assert args["aspectRatio"] == "21:9"
    assert args["durationSec"] == 15
    assert args["name"] == "FINAL SYSTEMS CERT \u2014 RENKOKA"
    assert args["engine"] == "minimax-h3"


def test_generate_that_shot_is_the_timeline_generate_tool():
    from app.codirector.durable.admission import classify_turn_mode, exposed_tool_ids
    from app.codirector.durable.agent import _operation_tool
    from app.codirector.durable.bind import bind_request_arguments

    text = "Generate that shot. MiniMax H3 Local, 1 megapixel, 21:9."
    assert classify_turn_mode(text) == "MUTATE"
    exposed = exposed_tool_ids(surface=None, user_text=text)
    assert "timeline.generate_shot" in exposed
    assert _operation_tool(text, set(exposed)) == "timeline.generate_shot"
    args, refusal = bind_request_arguments(
        None,
        tool_id="timeline.generate_shot",
        arguments={},
        user_text=text,
        project_id="project",
    )
    assert refusal is None
    assert args["megapixels"] == 1


def test_shot_after_continues_the_finished_shot():
    from app.codirector.durable.admission import exposed_tool_ids
    from app.codirector.durable.agent import _operation_tool
    from app.codirector.durable.bind import bind_request_arguments

    text = (
        "Create the next 15-second shot after the first one. "
        "Renkoka says: The path continues from here. MiniMax H3 Local, 1 megapixel, 21:9."
    )
    exposed = exposed_tool_ids(surface=None, user_text=text)
    assert "timeline.continue_shot" in exposed
    assert _operation_tool(text, set(exposed)) == "timeline.continue_shot"
    args, refusal = bind_request_arguments(
        None,
        tool_id="timeline.continue_shot",
        arguments={},
        user_text=text,
        project_id="project",
    )
    assert refusal is None
    assert args["durationSec"] == 15
    assert "path continues" in args["prompt"]


def test_opening_shot_before_the_first_uses_prepend():
    from app.codirector.durable.admission import classify_turn_mode, exposed_tool_ids, resolve_admitted_tool
    from app.codirector.durable.agent import _operation_tool
    from app.codirector.durable.bind import bind_request_arguments

    text = (
        "Create a 15-second opening shot that comes before the original first shot. "
        "Renkoka says: This story begins before the greeting. MiniMax H3 Local, 1 megapixel, 21:9."
    )
    assert classify_turn_mode(text) == "MUTATE"
    exposed = exposed_tool_ids(surface=None, user_text=text)
    assert "timeline.prepend_shot" in exposed
    assert _operation_tool(text, set(exposed)) == "timeline.prepend_shot"
    decision = resolve_admitted_tool(
        text,
        {"mode": "CONVERSATION", "confidence": "high", "reply": "15 seconds is blocked."},
        allowed=set(exposed),
        fallback=_operation_tool(text, set(exposed)),
    )
    assert decision.tool_id == "timeline.prepend_shot"
    args, refusal = bind_request_arguments(
        None,
        tool_id="timeline.prepend_shot",
        arguments={"sceneId": "<current_scene>", "shotId": "<next_shot_id>"},
        user_text=text,
        project_id="project",
    )
    assert refusal is None
    assert args["durationSec"] == 15
    assert "begins before the greeting" in args["prompt"]


def test_publish_this_scene_uses_the_publish_owner():
    from app.codirector.durable.admission import classify_turn_mode, exposed_tool_ids, resolve_admitted_tool
    from app.codirector.durable.agent import _operation_tool

    text = "Publish this scene."
    assert classify_turn_mode(text) == "MUTATE"
    exposed = exposed_tool_ids(surface=None, user_text=text)
    assert "timeline.publish_scene" in exposed
    assert _operation_tool(text, set(exposed)) == "timeline.publish_scene"
    decision = resolve_admitted_tool(
        text,
        {"mode": "CONVERSATION", "confidence": "high", "reply": "I don't have a publish action."},
        allowed=set(exposed),
        fallback=_operation_tool(text, set(exposed)),
    )
    assert decision.tool_id == "timeline.publish_scene"
    from app.codirector.tools.handlers.scenes import _usable_id

    assert _usable_id("current") == ""
    assert _usable_id("<current_scene>") == ""
    assert _usable_id("11111111-1111-1111-1111-111111111111") == "11111111-1111-1111-1111-111111111111"
    assert _usable_id("shot_a710f8eeaa98") == "shot_a710f8eeaa98"


def test_send_the_published_scene_uses_the_magi_owner():
    from app.codirector.durable.admission import classify_turn_mode, exposed_tool_ids, resolve_admitted_tool
    from app.codirector.durable.agent import _operation_tool

    text = "Send the published scene to MAGI."
    assert classify_turn_mode(text) == "MUTATE"
    exposed = exposed_tool_ids(surface=None, user_text=text)
    assert "film_timeline.send_to_magi" in exposed
    assert _operation_tool(text, set(exposed)) == "film_timeline.send_to_magi"
    decision = resolve_admitted_tool(
        text,
        {"mode": "CONVERSATION", "confidence": "high", "reply": "I'll check Scene 22."},
        allowed=set(exposed),
        fallback=_operation_tool(text, set(exposed)),
    )
    assert decision.tool_id == "film_timeline.send_to_magi"
    assert decision.mode == "READ"
    named = resolve_admitted_tool(
        text,
        {
            "mode": "MUTATE",
            "confidence": "high",
            "tool_id": "film_timeline.send_to_magi",
            "reply": "I'll send the published scene to MAGI.",
        },
        allowed=set(exposed),
        fallback=_operation_tool(text, set(exposed)),
    )
    assert named.tool_id == "film_timeline.send_to_magi"
    assert named.mode == "READ"


def test_magi_handoff_reaches_the_completed_event():
    from app.codirector.durable.execute import _invocation_for_receipt
    from app.codirector.durable.models import ToolReceipt

    receipt = ToolReceipt(
        requested_action="read:film_timeline.send_to_magi",
        target="scene",
        tool_id="film_timeline.send_to_magi",
        execution_status="succeeded",
        mutation_status="none",
        verification_status="not_applicable",
        evidence={
            "read": {
                "result": {
                    "status": "success",
                    "data": {
                        "uiAction": "open_magi",
                        "workspaceUrl": "/project/p?workspace=magi&sceneId=scene",
                        "publishedAssetId": "master",
                    },
                }
            }
        },
    )
    invocation = _invocation_for_receipt(receipt)
    assert invocation is not None
    assert invocation["result"]["uiAction"] == "open_magi"
    assert "workspace=magi" in invocation["result"]["workspaceUrl"]


def test_unique_local_character_is_accepted():
    init_db()
    project_id = f"local-{uuid.uuid4().hex[:8]}"
    name = f"Local{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    db.merge(Project(id=project_id, name="Local"))
    db.commit()
    try:
        profile_id = _profile(db, project_id, name, global_profile=False)
        args, refusal = bind_request_arguments(
            db,
            tool_id="create_scene",
            arguments={},
            user_text=f"Create a scene with {name}",
            project_id=project_id,
        )
    finally:
        db.close()
    assert refusal is None
    assert args["characterId"] == profile_id


def test_unique_prop_overlap_binds_and_a_tied_place_does_not_guess():
    text = (
        "Cade sitting inside the Schnick Coffee shop with the silver thermos "
        "filled with green slimy liquid"
    )
    assert _best_visible_label(text, ["Schnick Coffee Thermos", "Silver Metal Mug"]) == "Schnick Coffee Thermos"
    assert _best_visible_label(text, ["Schnick Coffee House", "Coffee House - Schnick Coffee"]) == ""


def test_search_envelope_matches_are_consumed_when_source_name_is_null():
    payload = {
        "requested_action": "read:character.search",
        "tool_id": "character.search",
        "execution_status": "succeeded",
        "evidence": {
            "read": {
                "result": {
                    "status": "success",
                    "summary": "1 character match(es)",
                    "data": {
                        "matches": [
                            {
                                "characterId": "93145921-28cb-46d1-86fc-28c213192a42",
                                "displayName": "Cade",
                                "sourceName": None,
                            }
                        ]
                    },
                    "evidence": [{"sourceType": "character", "sourceId": "93145921-28cb-46d1-86fc-28c213192a42", "sourceName": None}],
                }
            }
        },
    }
    matches = visible_character_matches(payload)
    assert matches == [{"displayName": "Cade", "characterId": "93145921-28cb-46d1-86fc-28c213192a42"}]
    spoken = project_creator_reply(json.dumps(payload))
    assert "Cade" in spoken
    assert "requested_action" not in spoken
    assert "93145921" not in spoken
    assert "{" not in spoken


def test_raw_receipt_never_becomes_the_chat_sentence():
    receipt = {
        "requested_action": "read:character.search",
        "tool_id": "character.search",
        "execution_status": "succeeded",
        "projectId": "06b04b34-f3de-46fa-9d90-64c8932bab4b",
        "workflowId": "msg-1",
    }
    spoken = project_creator_reply(json.dumps(receipt))
    lowered = spoken.lower()
    assert "requested_action" not in lowered
    assert "toolreceipt" not in lowered
    assert "character.search" not in lowered
    assert "06b04b34" not in spoken
    assert "traceback" not in lowered


def test_successful_lookup_continues_the_original_scene_request():
    class ToolReturnPart:
        def __init__(self, content: str):
            self.content = content

    class Message:
        def __init__(self, content: str):
            self.parts = [ToolReturnPart(content)]

    name = "Cade"
    receipt = json.dumps(
        {
            "tool_id": "character.search",
            "requested_action": "read:character.search",
            "execution_status": "succeeded",
            "evidence": {
                "read": {
                    "result": {
                        "data": {
                            "matches": [
                                {"displayName": name, "characterId": "abc", "sourceName": None}
                            ]
                        }
                    }
                }
            },
        }
    )
    deps = TurnDeps(
        envelope={
            "user_text": "Cade is listed as a global character available in this project.",
            "conversation_for_model": [{"role": "user", "content": SCENE.format(name=name)}],
            "exposed_tool_ids": [],
            "turn_mode": "CONVERSATION",
        },
        exposed_tool_ids=(),
    )
    set_turn_deps(deps)
    try:
        continued = _continue_after_lookup([Message(receipt)])
    finally:
        set_turn_deps(None)
    assert continued is not None
    part = continued.parts[0]
    assert part.tool_name == "create_scene"
    assert part.args["characterName"] == name
    assert deps.envelope["turn_mode"] == "MUTATE"
    assert "create_scene" in deps.envelope["exposed_tool_ids"]
