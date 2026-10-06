from __future__ import annotations

import asyncio

import pytest

from app.codirector.tools.definitions import ToolContext
from app.codirector.tools.handlers import avatar_m412
from app.db import Asset, SessionLocal
from app.production_events import recent_production_events


RUNTIME = {
    "displayName": "InfiniteTalk",
    "healthState": "repair_required",
    "certifiedReady": False,
}
GATE = (False, "InfiniteTalk needs repair — Open Runtime Setup")


def _create_project(client, name: str = "Avatar Orchestration") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def _create_session(client, project_id: str, **bootstrap) -> dict:
    payload = {
        "name": "Schnick Orchestration",
        "character_profile_id": bootstrap.get("character_profile_id", "char-korri"),
        "character_name": bootstrap.get("character_name", "Korri"),
        "mode": "talking_portrait",
        "bootstrap": {
            "character_profile_id": bootstrap.get("character_profile_id", "char-korri"),
            "character_name": bootstrap.get("character_name", "Korri"),
            "dialogue_original": bootstrap.get("dialogue_original", "Welcome to Schnick Coffee."),
            "source_still_asset_id": bootstrap.get("source_still_asset_id"),
            "source_kind": bootstrap.get("source_kind", "character"),
            "mode_kind": bootstrap.get("mode_kind", "single"),
            "speakers": bootstrap.get("speakers"),
            "conversation": bootstrap.get("conversation"),
            "provider_choice": "infinitetalk-local",
            "model_id": "infinitetalk-local",
            "look": {"aspect": bootstrap.get("aspect", "16:9")},
            "camera": {
                "aspect": bootstrap.get("aspect", "16:9"),
                "shot_size": "medium close-up",
                "lens": "50mm",
                "height": "eye level",
                "angle": "direct-to-camera",
                "movement": "static",
            },
            "input_mode": "script",
        },
    }
    response = client.post(f"/api/projects/{project_id}/avatar-sessions", json=payload)
    assert response.status_code == 200
    return response.json()


def _patch_runtime(monkeypatch) -> None:
    monkeypatch.setattr("app.avatar_runtimes.inspect_runtime", lambda _provider_id: dict(RUNTIME))
    monkeypatch.setattr("app.avatar_studio.inspect_runtime", lambda _provider_id: dict(RUNTIME))
    monkeypatch.setattr(avatar_m412, "inspect_runtime", lambda _provider_id: dict(RUNTIME))
    monkeypatch.setattr(avatar_m412, "runtime_gate_line", lambda _provider_id: GATE)
    monkeypatch.setattr("app.avatar_studio.runtime_gate_line", lambda _provider_id: GATE)


def test_avatar_tools_registered() -> None:
    from app.codirector.tools import registry

    assert registry.get("avatar.inspect").kind == "read"
    assert registry.get("avatar.open_studio").kind == "read"
    assert registry.get("avatar.detect_speakers").kind == "mutating"
    assert registry.get("avatar.create_plan").kind == "mutating"


def test_avatar_configure_capability_and_routine_tools() -> None:
    from app.codirector.capabilities.registry import get_capability
    from app.codirector.execution_authority import ROUTINE_TOOLS
    from app.codirector.tools.exposure import _BASELINE_READ_TOOL_IDS, expose

    configure = get_capability("avatar.configure")
    generate = get_capability("avatar.generate")
    assert configure is not None
    assert "avatar.create_plan" in configure.tool_ids
    assert generate is not None
    assert generate.tool_ids == ("avatar.create_job",)
    assert "avatar.create_plan" in ROUTINE_TOOLS
    assert "avatar.detect_speakers" in ROUTINE_TOOLS
    assert "avatar.create_job" not in ROUTINE_TOOLS
    assert "avatar.assemble" not in ROUTINE_TOOLS
    assert "avatar.inspect" in _BASELINE_READ_TOOL_IDS
    exposed = expose(workspace_surface="avatar", intent="make Korri say hello")
    assert "avatar.create_plan" in exposed
    assert "avatar.inspect" in exposed


def test_public_catalog_hides_shelved_avatar_tools() -> None:
    from app.codirector.tools import registry
    from app.codirector.tools.exposure import expose

    assert registry.get("avatar.inspect").kind == "read"
    public = registry.catalog()
    assert public
    assert all(not str(row.get("toolId") or "").startswith("avatar.") for row in public)
    exposed = expose(intent="check the timeline")
    assert all(not tid.startswith("avatar.") for tid in exposed)


def test_avatar_intent_beats_bare_aspect_ratio() -> None:
    from app.codirector.routing.unified_intent import _resolve_capability

    capability_id, tool_ids = _resolve_capability("Make Korri say Welcome to Schnick Coffee in InfiniteTalk 16:9")
    assert capability_id == "avatar.configure"
    assert "avatar.create_plan" in tool_ids


def test_character_voice_intent_routes_to_avatar_configure() -> None:
    from app.codirector.routing.unified_intent import _resolve_capability

    capability_id, tool_ids = _resolve_capability("use Korri's character voice")
    assert capability_id == "avatar.configure"
    assert "avatar.create_plan" in tool_ids


def test_snapshot_packet_after_create_plan(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    from app.codirector.production_state.snapshot import build_production_snapshot, render_production_snapshot_block

    project_id = _create_project(client, "Avatar Snapshot")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        result = avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "generatorId": "infinitetalk-local",
                "aspect": "16:9",
                "speakerALabel": "Korri",
                "speakerAId": "char-korri",
                "speakerADialogue": "Welcome to Schnick Coffee.",
            },
        )
        assert result["ok"] is True
        assert result["executed"] is False
        assert result["runtimeGate"] == GATE[1]
        snap = build_production_snapshot(db, project_id)
        packet = snap["avatar"]
        assert packet["present"] is True
        assert packet["sessionId"] == session["id"]
        assert packet["dialogueA"] == "Welcome to Schnick Coffee."
        assert packet["generator"] == "infinitetalk-local"
        assert packet["aspect"] == "16:9"
        assert packet["certifiedReady"] is False
        block = render_production_snapshot_block(db, project_id)
        assert "Welcome to Schnick Coffee." in block
        assert "Avatar" in block
    finally:
        db.close()


def test_inspect_returns_speakers_and_dialogue(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar Inspect")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "modeKind": "conversation",
                "conversationOrder": "a_then_b",
                "speakerALabel": "Korri",
                "speakerAId": "char-korri",
                "speakerADialogue": "Korri opens the shop.",
                "speakerBLabel": "Anadriya",
                "speakerBId": "char-anadriya",
                "speakerBDialogue": "Anadriya answers the counter.",
                "aspect": "9:16",
                "generatorId": "infinitetalk-local",
            },
        )
        inspected = asyncio.run(avatar_m412.inspect(ctx, {"sessionId": session["id"]}))
        assert inspected["ok"] is True
        assert inspected["mode"] == "conversation"
        assert inspected["dialogueA"] == "Korri opens the shop."
        assert inspected["dialogueB"] == "Anadriya answers the counter."
        assert inspected["speakerA"]["label"] == "Korri"
        assert inspected["speakerB"]["label"] == "Anadriya"
        assert inspected["sourceCharacterId"] == "char-korri"
        assert inspected["aspect"] == "9:16"
        assert inspected["generator"] == "infinitetalk-local"
        script = asyncio.run(avatar_m412.get_script_context(ctx, {"sessionId": session["id"]}))
        assert script["dialogueA"] == "Korri opens the shop."
        assert script["dialogueB"] == "Anadriya answers the counter."
        status = asyncio.run(avatar_m412.get_provider_status(ctx, {"sessionId": session["id"]}))
        assert status["certifiedReady"] is False
        assert status["supportsLiveGeneration"] is False
        assert status["runtimeGate"] == GATE[1]
    finally:
        db.close()


def test_conversation_switch_order_does_not_mix_lines(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar Switch")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "speakerADialogue": "Korri line stays Korri.",
                "speakerBDialogue": "Anadriya line stays Anadriya.",
                "conversationOrder": "a_then_b",
            },
        )
        avatar_m412.apply_create_plan(
            ctx,
            {"sessionId": session["id"], "conversationOrder": "b_then_a"},
        )
        inspected = asyncio.run(avatar_m412.inspect(ctx, {"sessionId": session["id"]}))
        assert inspected["order"] == "b_then_a"
        assert inspected["dialogueA"] == "Korri line stays Korri."
        assert inspected["dialogueB"] == "Anadriya line stays Anadriya."
    finally:
        db.close()


def test_dialogue_patch_updates_only_named_speaker(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar Dialogue Patch")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "speakerADialogue": "Original Korri.",
                "speakerBDialogue": "Original Anadriya.",
            },
        )
        avatar_m412.apply_create_plan(
            ctx,
            {"sessionId": session["id"], "speakerADialogue": "Changed Korri only."},
        )
        inspected = asyncio.run(avatar_m412.inspect(ctx, {"sessionId": session["id"]}))
        assert inspected["dialogueA"] == "Changed Korri only."
        assert inspected["dialogueB"] == "Original Anadriya."
    finally:
        db.close()


def test_voice_b_refuses_korri_take_for_anadriya(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar Voice Isolation")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "speakerAId": "char-korri",
                "speakerALabel": "Korri",
                "speakerBId": "char-anadriya",
                "speakerBLabel": "Anadriya",
                "speakerADialogue": "A",
                "speakerBDialogue": "B",
                "speakerAVoiceRecordId": "rec-korri",
                "speakerAVoiceTakeId": "take-korri",
                "speakerAVoiceAssetId": "audio-korri",
            },
        )
        with pytest.raises(ValueError, match="different character"):
            avatar_m412.apply_create_plan(
                ctx,
                {
                    "sessionId": session["id"],
                    "speakerBVoiceRecordId": "rec-korri",
                    "speakerBVoiceTakeId": "take-korri",
                    "speakerBVoiceAssetId": "audio-korri",
                },
            )
    finally:
        db.close()


def test_lora_refused_when_generator_has_no_support(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar LoRA Refuse")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        with pytest.raises(ValueError, match="does not support LoRA"):
            avatar_m412.apply_create_plan(
                ctx,
                {
                    "sessionId": session["id"],
                    "generatorId": "infinitetalk-local",
                    "loraId": "lora-not-allowed",
                    "loraName": "Not Allowed",
                    "loraStrength": 0.8,
                },
            )
    finally:
        db.close()


def test_create_job_refuses_runtime_without_inventing_library_asset(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar Job Gate")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        before = db.query(Asset).filter(Asset.project_id == project_id).count()
        ctx = ToolContext(db=db, project_id=project_id)
        result = avatar_m412.apply_create_job(
            ctx,
            {
                "sessionId": session["id"],
                "generatorId": "infinitetalk-local",
                "speakerADialogue": "Welcome to Schnick Coffee.",
                "startImmediately": True,
            },
        )
        assert result["ok"] is True
        assert result["executed"] is False
        assert result["runtimeGate"] == GATE[1]
        after = db.query(Asset).filter(Asset.project_id == project_id).count()
        assert after == before
        events = recent_production_events(db, project_id, limit=20)
        types = {item.get("eventType") for item in events}
        assert "avatar.job.runtime_refused" in types
    finally:
        db.close()


def test_events_and_memory_mention_session(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    from app.codirector.production_state.memory import production_memory_block

    project_id = _create_project(client, "Avatar Memory")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "speakerADialogue": "Welcome to Schnick Coffee.",
            },
        )
        events = recent_production_events(db, project_id, limit=20)
        assert any(item.get("eventType") == "avatar.session.updated" for item in events)
        assert any(session["id"] == item.get("subjectId") for item in events)
        block = production_memory_block(db, project_id)
        assert "Avatar Studio session" in block or session["id"] in block
    finally:
        db.close()


def test_manual_patch_then_inspect_parity(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar Manual Parity")
    session = _create_session(client, project_id)
    patched = client.patch(
        f"/api/projects/{project_id}/avatar-sessions/{session['id']}",
        json={
            "mode_kind": "conversation",
            "look": {**(session.get("look") or {}), "aspect": "16:9"},
            "speakers": [
                {"id": "speaker-a", "label": "Korri", "character_id": "char-korri"},
                {"id": "speaker-b", "label": "Anadriya", "character_id": "char-anadriya"},
            ],
            "conversation": {
                "order": "a_then_b",
                "turns": [
                    {"speakerId": "speaker-a", "dialogue": "Manual Korri line."},
                    {"speakerId": "speaker-b", "dialogue": "Manual Anadriya line."},
                ],
            },
            "model_id": "infinitetalk-local",
            "provider_choice": "infinitetalk-local",
        },
    )
    assert patched.status_code == 200
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        inspected = asyncio.run(avatar_m412.inspect(ctx, {"sessionId": session["id"]}))
        assert inspected["dialogueA"] == "Manual Korri line."
        assert inspected["dialogueB"] == "Manual Anadriya line."
        assert inspected["aspect"] == "16:9"
        events = recent_production_events(db, project_id, limit=20)
        assert any(item.get("eventType") == "avatar.session.updated" for item in events)
    finally:
        db.close()


def test_open_studio_returns_ui_action(client) -> None:
    project_id = _create_project(client, "Avatar Open")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        result = asyncio.run(avatar_m412.open_studio(ctx, {"sessionId": session["id"]}))
        assert result["uiAction"] == "open_avatar_studio"
        assert "workspace=avatar" in result["workspaceUrl"]
        assert result["sessionId"] == session["id"]
    finally:
        db.close()


def test_performance_direction_does_not_rewrite_dialogue(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar Direction")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "speakerADialogue": "Welcome to Schnick Coffee.",
            },
        )
        avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "performanceDirection": "Keep Korri still and warm.",
            },
        )
        inspected = asyncio.run(avatar_m412.inspect(ctx, {"sessionId": session["id"]}))
        assert inspected["dialogueA"] == "Welcome to Schnick Coffee."
        assert inspected["directionPrompt"] == "Keep Korri still and warm."
    finally:
        db.close()


def test_create_plan_character_voice_and_library_frame(client, monkeypatch) -> None:
    _patch_runtime(monkeypatch)
    project_id = _create_project(client, "Avatar Character Voice Plan")
    session = _create_session(client, project_id)
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        avatar_m412.apply_create_plan(
            ctx,
            {
                "sessionId": session["id"],
                "sourceKind": "library",
                "sourceAssetId": "still-library-frame",
                "speakerAId": "char-korri",
                "speakerALabel": "Korri",
                "voiceMode": "character",
                "speakerADialogue": "Welcome to Schnick Coffee.",
            },
        )
        inspected = asyncio.run(avatar_m412.inspect(ctx, {"sessionId": session["id"]}))
        assert inspected["sourceKind"] == "library"
        assert inspected["sourceAssetId"] == "still-library-frame"
        assert inspected["voiceMode"] == "character"
        assert inspected["voiceA"]["mode"] == "character"
        refreshed = client.get(f"/api/projects/{project_id}/avatar-sessions/{session['id']}").json()
        assert refreshed["voice_mode"] == "character"
        assert refreshed["source_still_asset_id"] == "still-library-frame"
    finally:
        db.close()
