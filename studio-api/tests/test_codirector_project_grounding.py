"""Co-Director project grounding + @entity resolution (surgical mission)."""

from __future__ import annotations

import json
import uuid

import pytest

from app.character_identity.crs_service import persist_crs_in_session
from app.character_identity.models import CharacterProfileRow
from app.character_identity.schemas import CharacterProfileCreate, VoiceProfileCreate
from app.character_identity.service import create_profile, create_voice_profile
from app.codirector.image_route.lock import parse_route_lock
from app.codirector.project_grounding import (
    build_project_grounding_snapshot,
    forbidden_model_tokens,
    grounding_reply,
    inspect_turn_grounding,
    parse_route_lock_excluding_entities,
    resolve_turn_entities,
    route_parse_surface,
)
from app.codirector.session_context import build_session_context
from app.db import Asset, Project, Scene, SessionLocal, init_db


PROMPT_TWO = "Create a shot with @Korri and @Anadriya walking through the Venture corridor."


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    yield


def _sse_events(payload: str) -> list[dict]:
    events = []
    for block in payload.split("\n\n"):
        line = block.strip()
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if raw:
            events.append(json.loads(raw))
    return events


def _project(db, name: str) -> str:
    pid = str(uuid.uuid4())
    db.add(Project(id=pid, name=name, settings_json="{}"))
    db.commit()
    return pid


def _scene(db, project_id: str, name: str, index: int = 0) -> str:
    sid = str(uuid.uuid4())
    db.add(Scene(id=sid, project_id=project_id, name=name, index=index))
    db.commit()
    return sid


def _asset(db, project_id: str, tag: str) -> str:
    aid = str(uuid.uuid4())
    db.add(
        Asset(
            id=aid,
            project_id=project_id,
            tag=tag,
            kind="image",
            filename=f"{tag}.png",
            path=f"/tmp/{tag}.png",
        )
    )
    db.commit()
    return aid


def _seed_cast(db, project_id: str) -> dict[str, str]:
    korri = create_profile(
        db,
        project_id,
        CharacterProfileCreate(name="Korri", slug="korri", role="lead"),
    )
    anadriya = create_profile(
        db,
        project_id,
        CharacterProfileCreate(name="Anadriya", slug="anadriya", role="lead"),
    )
    korri_crs = _asset(db, project_id, "korri-crs")
    ana_crs = _asset(db, project_id, "anadriya-crs")
    persist_crs_in_session(db, db.get(CharacterProfileRow, korri.id), asset_id=korri_crs)
    persist_crs_in_session(db, db.get(CharacterProfileRow, anadriya.id), asset_id=ana_crs)
    db.commit()
    korri_voice = create_voice_profile(
        db,
        project_id,
        korri.id,
        VoiceProfileCreate(name="Korri Venture", provider="index-tts2-local", source_mode="DESIGN"),
    )
    ana_voice = create_voice_profile(
        db,
        project_id,
        anadriya.id,
        VoiceProfileCreate(name="Anadriya Venture", provider="elevenlabs", source_mode="DESIGN"),
    )
    return {
        "korri_id": korri.id,
        "anadriya_id": anadriya.id,
        "korri_crs": korri_crs,
        "anadriya_crs": ana_crs,
        "korri_voice": korri_voice["id"],
        "anadriya_voice": ana_voice["id"],
    }


@pytest.fixture()
def db():
    init_db()
    try:
        from app.character_identity import ensure_character_identity_tables

        ensure_character_identity_tables()
    except Exception:
        pass
    session = SessionLocal()
    yield session
    session.close()


def test_unbound_session_is_legitimately_no_project(db):
    ctx = build_session_context(db)
    assert ctx["projectId"] is None
    assert ctx["sessionStatus"] == "no_project"
    assert "no_project_selected" in ctx["unresolvedBlockers"]
    snap = build_project_grounding_snapshot(db, None)
    assert snap["bound"] is False
    assert snap["sessionStatus"] == "no_project"


def test_bound_project_never_becomes_no_project(db):
    pid = _project(db, "Bound Grounding")
    ctx = build_session_context(db, project_id=pid)
    assert ctx["projectId"] == pid
    assert ctx["sessionStatus"] == "bound"
    assert "no_project_selected" not in ctx["unresolvedBlockers"]
    snap = ctx["projectSnapshot"]
    assert snap["bound"] is True
    assert snap["sessionStatus"] == "bound"
    assert snap["project"]["id"] == pid


def test_active_scene_requires_explicit_scene_id(db):
    pid = _project(db, "Scene Authority")
    first = _scene(db, pid, "Scene 1", 0)
    walk = _scene(db, pid, "Venture Corridor Walk", 1)
    empty = build_project_grounding_snapshot(db, pid, None)
    assert empty["activeScene"] is None
    assert first and walk
    walk_snap = build_project_grounding_snapshot(db, pid, walk, workspace="timeline")
    assert walk_snap["activeScene"]["id"] == walk
    assert walk_snap["activeScene"]["name"] == "Venture Corridor Walk"
    assert walk_snap["workspace"] == "timeline"


def test_scene_switch_updates_active_scene(db):
    pid = _project(db, "Scene Switch")
    scene1 = _scene(db, pid, "Scene 1", 0)
    dialogue = _scene(db, pid, "Venture Corridor Dialogue", 1)
    walk = _scene(db, pid, "Venture Corridor Walk", 2)
    assert build_project_grounding_snapshot(db, pid, scene1)["activeScene"]["name"] == "Scene 1"
    assert (
        build_project_grounding_snapshot(db, pid, dialogue)["activeScene"]["name"]
        == "Venture Corridor Dialogue"
    )
    assert (
        build_project_grounding_snapshot(db, pid, walk)["activeScene"]["name"]
        == "Venture Corridor Walk"
    )


def test_characters_and_voices_injected(db):
    pid = _project(db, "Cast Grounding")
    seeded = _seed_cast(db, pid)
    snap = build_project_grounding_snapshot(db, pid)
    names = {row["name"] for row in snap["characters"]}
    assert names == {"Korri", "Anadriya"}
    by_name = {row["name"]: row for row in snap["characters"]}
    assert by_name["Korri"]["id"] == seeded["korri_id"]
    assert by_name["Korri"]["crsAssetId"] == seeded["korri_crs"]
    assert by_name["Anadriya"]["crsAssetId"] == seeded["anadriya_crs"]
    voices = {row["characterName"]: row for row in snap["voiceAssignments"]}
    assert voices["Korri"]["voiceProfileId"] == seeded["korri_voice"]
    assert voices["Korri"]["engine"] == "index-tts2-local"
    assert voices["Anadriya"]["voiceProfileId"] == seeded["anadriya_voice"]
    assert voices["Anadriya"]["engine"] == "elevenlabs"
    chars = grounding_reply({"snapshot": snap}, "Who are the active characters in this project?")
    assert chars is not None
    assert "Korri" in chars and "Anadriya" in chars
    voices_reply = grounding_reply({"snapshot": snap}, "What voices are assigned to Korri and Anadriya?")
    assert voices_reply is not None
    assert "Korri Venture" in voices_reply
    assert "Anadriya Venture" in voices_reply
    assert "index-tts2-local" in voices_reply
    assert "elevenlabs" in voices_reply


def test_character_and_prop_view_grounding_reply() -> None:
    snap = {
        "bound": True,
        "characters": [
            {
                "name": "Cade O'Connor",
                "approvedViews": [
                    {"name": "Front", "source": "upload"},
                    {"name": "Side", "source": "uploaded"},
                    {"name": "3/4", "source": "generated"},
                ],
            },
            {"name": "CharacterGlobalTest9c1f3f", "approvedViews": []},
        ],
        "props": [
            {
                "name": "Upload Smoke Advanced Ship",
                "tag": "upload-smoke-advanced-ship",
                "approvedViews": [
                    {"name": "Front", "source": "uploaded"},
                    {"name": "Left", "source": "generated"},
                ],
            }
        ],
    }
    char_reply = grounding_reply({"snapshot": snap}, "Which character views are approved for Cade?")
    assert char_reply is not None
    assert "Cade O'Connor" in char_reply
    assert "Side (uploaded)" in char_reply
    assert "3/4 (generated)" in char_reply
    assert "CharacterGlobalTest" not in char_reply
    prop_reply = grounding_reply(
        {"snapshot": snap},
        "Which prop views are approved for Upload Smoke Advanced Ship?",
    )
    assert prop_reply is not None
    assert "Front (uploaded)" in prop_reply
    assert "Left (generated)" in prop_reply


def test_prop_ready_grounding_is_primary_only() -> None:
    snap = {
        "bound": True,
        "props": [
            {
                "name": "Upload Smoke Advanced Ship",
                "tag": "upload-smoke-advanced-ship",
                "identityReady": True,
                "propReady": True,
                "approvedPrimaryAssetId": "940be337-071f-4440-b46b-675c2a6a5276",
                "readyReason": "Primary approved. Additional views are optional.",
                "approvedViews": [{"name": "Primary", "source": "uploaded"}],
            },
            {
                "name": "Draft Cup",
                "tag": "draft-cup",
                "identityReady": False,
                "propReady": False,
                "approvedPrimaryAssetId": None,
                "readyReason": "Approve Primary to make this Prop ready. Additional views are optional.",
                "approvedViews": [],
            },
        ],
    }
    ready = grounding_reply({"snapshot": snap}, "Is this prop ready for Upload Smoke Advanced Ship?")
    assert ready is not None
    assert "Upload Smoke Advanced Ship is ready" in ready
    assert "Primary is approved" in ready
    assert "Additional views are optional" in ready
    assert "all views" not in ready.lower()
    assert "Draft Cup" not in ready
    not_ready = grounding_reply({"snapshot": snap}, "Is this prop ready for Draft Cup?")
    assert not_ready is not None
    assert "Draft Cup is not ready" in not_ready
    assert "Approve Primary" in not_ready


def test_pending_primary_grounding_names_candidate() -> None:
    snap = {
        "bound": True,
        "props": [
            {
                "name": "Cade's Starfighter",
                "tag": "cade-s-starfighter-2",
                "identityReady": True,
                "propReady": True,
                "approvedPrimaryAssetId": "old-blue",
                "pendingPrimaryAssetId": "new-real",
                "previewPrimaryAssetId": "new-real",
                "approvedViews": [{"name": "Primary", "source": "uploaded"}],
            }
        ],
    }
    reply = grounding_reply({"snapshot": snap}, "Which Primary is pending for Cade's Starfighter?")
    assert reply is not None
    assert "pending Primary candidate new-real" in reply
    assert "Approved identity is old-blue" in reply


def test_scene_grounding_reply_uses_selected_scene(db):
    pid = _project(db, "Scene Reply")
    walk = _scene(db, pid, "Venture Corridor Walk", 0)
    inspect = inspect_turn_grounding(db, pid, walk, "What scene are we working on?", workspace="timeline")
    reply = grounding_reply(inspect, "What scene are we working on?")
    assert reply == "We are working on Venture Corridor Walk."
    assert "corridor" not in (reply or "").lower() or "Venture Corridor Walk" in (reply or "")


def test_ers_generator_question_is_not_scene_grounding() -> None:
    reply = grounding_reply(
        {"snapshot": {"bound": True, "timelineSnapshot": {}}},
        "Which generator creates an Environment Reference Sheet?",
    )
    assert reply is None


def test_resolve_korri_and_anadriya_separately_and_together(db):
    pid = _project(db, "Entity Resolve")
    seeded = _seed_cast(db, pid)
    korri = resolve_turn_entities(db, pid, "Look at @Korri.")
    assert [c.name for c in korri.characters] == ["Korri"]
    assert korri.characters[0].character_id == seeded["korri_id"]
    assert korri.characters[0].crs_asset_id == seeded["korri_crs"]
    ana = resolve_turn_entities(db, pid, "Look at @Anadriya.")
    assert [c.name for c in ana.characters] == ["Anadriya"]
    assert ana.characters[0].character_id == seeded["anadriya_id"]
    assert ana.characters[0].crs_asset_id == seeded["anadriya_crs"]
    both = resolve_turn_entities(db, pid, PROMPT_TWO)
    names = [c.name for c in both.characters]
    assert names == ["Korri", "Anadriya"]
    assert {c.character_id for c in both.characters} == {seeded["korri_id"], seeded["anadriya_id"]}
    assert {c.crs_asset_id for c in both.characters} == {seeded["korri_crs"], seeded["anadriya_crs"]}
    assert both.unresolved == []


def test_entity_tokens_cannot_become_model_ids(db):
    pid = _project(db, "Model Isolation")
    seeded = _seed_cast(db, pid)
    surface = route_parse_surface(PROMPT_TWO)
    assert "@Korri" not in surface
    assert "@Anadriya" not in surface
    tagged = parse_route_lock(PROMPT_TWO)
    assert tagged.requested_model_id == ""
    inspect = inspect_turn_grounding(db, pid, None, PROMPT_TWO)
    assert inspect["routeLock"]["requestedModelId"] == ""
    untagged = "Create a shot with Korri and Anadriya walking through the Venture corridor."
    leaked = parse_route_lock(untagged)
    assert leaked.requested_model_id in {"", "korri"}
    excluded = parse_route_lock_excluding_entities(
        untagged,
        ["Korri", "Anadriya", "@Korri", "@Anadriya"],
    )
    assert excluded.requested_model_id == ""
    flux = parse_route_lock_excluding_entities(
        "use Flux with @Korri and @Anadriya",
        ["Korri", "Anadriya"],
    )
    assert flux.requested_model_id == "flux"
    banned = forbidden_model_tokens(["Korri", "Anadriya"])
    assert "korriandanadriya" in banned
    assert "anadriyaandkorri" in banned
    assert inspect["entities"]["characters"][0]["characterId"] == seeded["korri_id"]


def test_cross_project_entity_resolution_fail_closed(db):
    project_a = _project(db, "Project A")
    project_b = _project(db, "Project B")
    seeded = _seed_cast(db, project_a)
    create_profile(db, project_b, CharacterProfileCreate(name="Mieke", slug="mieke", role="lead"))
    foreign = resolve_turn_entities(db, project_b, PROMPT_TWO)
    assert foreign.characters == []
    assert "@Korri" in foreign.unresolved
    assert "@Anadriya" in foreign.unresolved
    inspect_b = inspect_turn_grounding(db, project_b, None, "@Korri")
    assert inspect_b["entities"]["characters"] == []
    ids = {row["id"] for row in inspect_b["snapshot"]["characters"]}
    assert seeded["korri_id"] not in ids
    inspect_a = inspect_turn_grounding(db, project_a, None, "@Korri")
    assert inspect_a["entities"]["characters"][0]["characterId"] == seeded["korri_id"]


def test_http_session_and_turn_grounding(client, mock_provider_env, db):
    pid = _project(db, "HTTP Grounding")
    walk = _scene(db, pid, "Venture Corridor Walk", 0)
    seeded = _seed_cast(db, pid)
    unbound = client.get("/api/codirector/session-context").json()
    assert unbound["projectId"] is None
    assert unbound["sessionStatus"] == "no_project"
    bound = client.get(
        f"/api/codirector/session-context?project_id={pid}&scene_id={walk}&workspace=timeline"
    ).json()
    assert bound["projectId"] == pid
    assert bound["sessionStatus"] == "bound"
    assert bound["activeSceneId"] == walk
    assert bound["projectSnapshot"]["activeScene"]["name"] == "Venture Corridor Walk"
    inspect = client.post(
        f"/api/codirector/projects/{pid}/turn-grounding",
        json={"text": PROMPT_TWO, "sceneId": walk, "workspace": "timeline"},
    ).json()
    names = [row["name"] for row in inspect["entities"]["characters"]]
    assert names == ["Korri", "Anadriya"]
    assert {row["crsAssetId"] for row in inspect["entities"]["characters"]} == {
        seeded["korri_crs"],
        seeded["anadriya_crs"],
    }
    assert inspect["routeLock"]["requestedModelId"] == ""
    assert inspect["sessionStatus"] == "bound"
    stream = client.post(
        "/api/codirector/chat/stream",
        json={
            "messages": [{"role": "user", "content": "Who are the active characters in this project?"}],
            "project_id": pid,
            "scene_id": walk,
            "workspaceTab": "timeline",
        },
    )
    assert stream.status_code == 200
    events = _sse_events(stream.text)
    grounding = next(ev for ev in events if ev.get("type") == "project_grounding")
    assert grounding["sessionStatus"] == "bound"
    assert grounding["projectId"] == pid
    assert grounding["activeSceneId"] == walk
    assistant = next(ev for ev in events if ev.get("type") == "assistant")
    assert "Korri" in assistant["content"]
    assert "Anadriya" in assistant["content"]
    scene_stream = client.post(
        "/api/codirector/chat/stream",
        json={
            "messages": [{"role": "user", "content": "What scene are we working on?"}],
            "project_id": pid,
            "scene_id": walk,
            "workspaceTab": "timeline",
        },
    )
    scene_events = _sse_events(scene_stream.text)
    scene_reply = next(ev for ev in scene_events if ev.get("type") == "assistant")
    assert scene_reply["content"] == "We are working on Venture Corridor Walk."
    unbound_stream = client.post(
        "/api/codirector/chat/stream",
        json={"messages": [{"role": "user", "content": "Who are the active characters in this project?"}]},
    )
    unbound_events = _sse_events(unbound_stream.text)
    unbound_ground = next(ev for ev in unbound_events if ev.get("type") == "project_grounding")
    assert unbound_ground["sessionStatus"] == "no_project"
    assert unbound_ground["projectId"] is None


def test_global_character_visible_in_other_project_grounding(db):
    owner = _project(db, "Owner Cast")
    viewer = _project(db, "Viewer Cast")
    global_char = create_profile(
        db,
        owner,
        CharacterProfileCreate(name="Cade", slug="cade", role="lead", is_global=True),
    )
    create_profile(
        db,
        owner,
        CharacterProfileCreate(name="LocalOnly", slug="localonly", role="supporting"),
    )
    snap = build_project_grounding_snapshot(db, viewer)
    names = {row["name"] for row in snap["characters"]}
    assert "Cade" in names
    assert "LocalOnly" not in names
    cade = next(row for row in snap["characters"] if row["name"] == "Cade")
    assert cade["id"] == global_char.id
    assert cade["isGlobal"] is True
    reply = grounding_reply(
        {"snapshot": snap},
        "What global characters, props, and environments can I use?",
    )
    assert reply is not None
    assert "Cade" in reply
    assert "LocalOnly" not in reply
    roster = grounding_reply({"snapshot": snap}, "Who are the active characters in this project?")
    assert "Cade" in (roster or "")
    assert "LocalOnly" not in (roster or "")
