from __future__ import annotations

from pathlib import Path

import pytest

from app import avatar_studio as avatar
from app.avatar_runtimes import list_avatar_generator_capabilities


def _create_project(client, name: str = "Avatar Compact") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def _create_session(client, project_id: str, **bootstrap) -> dict:
    payload = {
        "name": "Schnick Compact",
        "character_profile_id": bootstrap.get("character_profile_id", "char-korri"),
        "character_name": bootstrap.get("character_name", "Korri"),
        "mode": "talking_portrait",
        "bootstrap": {
            "character_profile_id": bootstrap.get("character_profile_id", "char-korri"),
            "character_name": bootstrap.get("character_name", "Korri"),
            "dialogue_original": bootstrap.get("dialogue_original", "Hello from Korri."),
            "source_still_asset_id": bootstrap.get("source_still_asset_id"),
            "source_kind": bootstrap.get("source_kind", "character"),
            "mode_kind": bootstrap.get("mode_kind", "single"),
            "speakers": bootstrap.get("speakers"),
            "conversation": bootstrap.get("conversation"),
            "provider_choice": "infinitetalk-local",
            "model_id": "infinitetalk-local",
            "look": {"aspect": bootstrap.get("aspect", "9:16")},
            "camera": {"aspect": bootstrap.get("aspect", "9:16"), "shot_size": "medium close-up", "lens": "50mm", "height": "eye level", "angle": "direct-to-camera", "movement": "static"},
            "input_mode": "script",
        },
    }
    response = client.post(f"/api/projects/{project_id}/avatar-sessions", json=payload)
    assert response.status_code == 200
    return response.json()


def test_avatar_runtime_capabilities_exclude_generic_i2v() -> None:
    payload = list_avatar_generator_capabilities()
    by_id = {item["id"]: item for item in payload}
    assert by_id["infinitetalk-local"]["listedAsAvatarGenerator"] is True
    assert by_id["longcat-video-avatar-1-5-local"]["listedAsAvatarGenerator"] is True
    assert by_id["infinitetalk-local"]["supportsNativeMultiSpeaker"] is False
    assert by_id["infinitetalk-local"]["supportsConversation"] is True
    assert by_id["musetalk-1-5-local"]["listedAsAvatarGenerator"] is False
    assert by_id["echomimic-v2-local"]["listedAsAvatarGenerator"] is False
    assert "minimax-h3" not in by_id
    assert "ltx_2_5_distilled" not in by_id


def test_avatar_runtimes_endpoint(client) -> None:
    response = client.get("/api/avatar-runtimes")
    assert response.status_code == 200
    listed = [item["id"] for item in response.json()["runtimes"] if item["listedAsAvatarGenerator"]]
    assert listed == ["longcat-video-avatar-1-5-local", "infinitetalk-local"]


def test_detect_speakers_one_and_two_faces(client, monkeypatch) -> None:
    from app.db import Asset, SessionLocal
    import uuid

    project_id = _create_project(client, "Avatar Detect")
    still_id = f"still-detect-{uuid.uuid4().hex[:12]}"
    session = _create_session(client, project_id, source_still_asset_id=still_id)
    db = SessionLocal()
    try:
        db.add(Asset(id=still_id, project_id=project_id, kind="image", filename="still.png", path=__file__))
        db.commit()
    finally:
        db.close()

    faces = [
        {"id": "speaker-a", "label": "Person 1", "character_id": None, "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.3}, "mask_asset_id": None}
    ]

    def one_face(_path, max_faces=2):
        del _path, max_faces
        return list(faces)

    monkeypatch.setattr("app.mouth_tracker.detect_face_rois_in_image", one_face)
    one = client.post(f"/api/projects/{project_id}/avatar-sessions/{session['id']}/detect-speakers")
    assert one.status_code == 200
    assert one.json()["faceCount"] == 1
    assert one.json()["speakers"][0]["label"] in {"Korri", "Person 1"}

    def two_faces(_path, max_faces=2):
        del _path, max_faces
        return [
            {"id": "speaker-a", "label": "Person 1", "character_id": None, "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.3}, "mask_asset_id": None},
            {"id": "speaker-b", "label": "Person 2", "character_id": None, "bbox": {"x": 0.6, "y": 0.1, "w": 0.2, "h": 0.3}, "mask_asset_id": None},
        ]

    monkeypatch.setattr("app.mouth_tracker.detect_face_rois_in_image", two_faces)
    two = client.post(f"/api/projects/{project_id}/avatar-sessions/{session['id']}/detect-speakers")
    assert two.status_code == 200
    assert two.json()["faceCount"] == 2
    assert [item["label"] for item in two.json()["speakers"]] == ["Person 1", "Person 2"]


def test_conversation_job_plans_a_then_b_order(client) -> None:
    project_id = _create_project(client, "Avatar Conversation Plan")
    session = _create_session(
        client,
        project_id,
        mode_kind="conversation",
        speakers=[
            {"id": "speaker-a", "label": "Person 1", "character_id": None},
            {"id": "speaker-b", "label": "Person 2", "character_id": None},
        ],
        conversation={
            "order": "a_then_b",
            "turns": [
                {"speakerId": "speaker-a", "dialogue": "Speaker A line only."},
                {"speakerId": "speaker-b", "dialogue": "Speaker B line only."},
            ],
        },
        dialogue_original="Speaker A line only.\n\nSpeaker B line only.",
    )
    job = client.post(
        f"/api/projects/{project_id}/avatar-sessions/{session['id']}/jobs",
        json={"providerId": "infinitetalk-local", "startImmediately": False},
    )
    assert job.status_code == 200
    sections = job.json()["sections"]
    assert len(sections) == 2
    assert sections[0]["speakerId"] == "speaker-a"
    assert sections[0]["scriptText"] == "Speaker A line only."
    assert sections[1]["speakerId"] == "speaker-b"
    assert sections[1]["scriptText"] == "Speaker B line only."


def test_codirector_create_job_writes_conversation_fields(client, monkeypatch) -> None:
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import avatar_m412
    from app.db import SessionLocal

    project_id = _create_project(client, "Avatar CD Compact")
    session = _create_session(client, project_id)
    monkeypatch.setattr(
        avatar_m412,
        "runtime_gate_line",
        lambda _provider_id: (False, "InfiniteTalk needs repair — Open Runtime Setup"),
    )
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id=project_id)
        result = avatar_m412.apply_create_job(
            ctx,
            {
                "sessionId": session["id"],
                "generatorId": "infinitetalk-local",
                "sourceKind": "library",
                "sourceAssetId": "still-library-1",
                "aspect": "9:16",
                "conversationOrder": "a_then_b",
                "speakerALabel": "Person 1",
                "speakerADialogue": "A asks.",
                "speakerBLabel": "Person 2",
                "speakerBDialogue": "B answers.",
                "startImmediately": True,
            },
        )
        assert result["ok"] is True
        assert result["executed"] is False
        assert result["runtimeGate"] == "InfiniteTalk needs repair — Open Runtime Setup"
        assert result["sections"][0]["speakerId"] == "speaker-a"
        assert result["sections"][1]["speakerId"] == "speaker-b"
        refreshed = client.get(f"/api/projects/{project_id}/avatar-sessions/{session['id']}").json()
        assert refreshed["source_kind"] == "library"
        assert refreshed["source_still_asset_id"] == "still-library-1"
        assert refreshed["look"]["aspect"] == "9:16"
        assert refreshed["conversation"]["order"] == "a_then_b"
        assert refreshed["speakers"][1]["label"] == "Person 2"
    finally:
        db.close()


def test_generate_blocked_when_runtime_not_certified(monkeypatch) -> None:
    from app import avatar_runtimes

    monkeypatch.setattr(
        avatar_runtimes,
        "inspect_runtime",
        lambda _provider_id: {
            "displayName": "InfiniteTalk",
            "healthState": "repair_required",
            "certifiedReady": False,
        },
    )
    ready, line = avatar_runtimes.runtime_gate_line("infinitetalk-local")
    assert ready is False
    assert line == "InfiniteTalk needs repair — Open Runtime Setup"
