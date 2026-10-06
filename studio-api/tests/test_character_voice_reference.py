"""Global Character approved voice reference.

The character's active Voice Profile carries only a Library asset id. Timeline
then stages that audio into MiniMax H3's standalone audio-reference slots.
"""
from __future__ import annotations

import uuid

import pytest

from app.db import Asset, SessionLocal


@pytest.fixture(autouse=True)
def _character_identity_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")


def _project(client) -> str:
    response = client.post("/api/projects", json={"name": f"VoiceRef {uuid.uuid4().hex[:6]}"})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _character(client, project_id: str, name: str = "Renkoka") -> str:
    response = client.post(
        f"/api/projects/{project_id}/characters",
        json={"name": name, "role": "lead"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _save_voice(client, project_id: str, character_id: str) -> str:
    response = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/voice-profiles",
        json={"name": "Renkoka Final", "source_mode": "PROVIDER"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _audio_asset(project_id: str, suffix: str = "wav", tag: str = "voice") -> str:
    db = SessionLocal()
    try:
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="audio",
            tag=tag,
            filename=f"{uuid.uuid4().hex}.{suffix}",
            path=f"library/audio/{uuid.uuid4().hex}.{suffix}",
        )
        db.add(asset)
        db.commit()
        return asset.id
    finally:
        db.close()


def test_voice_reference_roundtrip_and_authority(client):
    project_id = _project(client)
    character_id = _character(client, project_id)
    _save_voice(client, project_id, character_id)
    asset_id = _audio_asset(project_id)

    attach = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/voice/reference",
        json={"assetId": asset_id},
    )
    assert attach.status_code == 200, attach.text
    assert attach.json()["approvedVoiceReferenceAssetId"] == asset_id

    authority = client.get(f"/api/projects/{project_id}/characters/{character_id}/voice/authority")
    assert authority.status_code == 200, authority.text
    assert authority.json()["approvedVoiceReferenceAssetId"] == asset_id

    voices = client.get(f"/api/projects/{project_id}/characters/{character_id}/voice-profiles")
    assert voices.status_code == 200, voices.text
    assert voices.json()["items"][0]["approvedVoiceReferenceAssetId"] == asset_id


def test_voice_reference_creates_library_voice_when_none_saved(client):
    """Use Existing Voice on a character with no saved voice: the assignment
    creates a minimal approved LIBRARY VoiceProfileRow to carry the reference —
    the canonical voice store, not a parallel database."""
    project_id = _project(client)
    character_id = _character(client, project_id)
    asset_id = _audio_asset(project_id, tag="Renkoka Voice Sample")

    attach = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/voice/reference",
        json={"assetId": asset_id},
    )
    assert attach.status_code == 200, attach.text
    body = attach.json()
    assert body["approvedVoiceReferenceAssetId"] == asset_id
    assert body["approvedVoiceReferenceAssetName"] == "Renkoka Voice Sample"
    assert body["voiceProfileId"]

    authority = client.get(f"/api/projects/{project_id}/characters/{character_id}/voice/authority")
    assert authority.status_code == 200, authority.text
    auth = authority.json()
    assert auth["approvedVoiceReferenceAssetId"] == asset_id
    assert auth["approvedVoiceReferenceAssetName"] == "Renkoka Voice Sample"
    assert auth["approved"] is True

    voices = client.get(f"/api/projects/{project_id}/characters/{character_id}/voice-profiles")
    assert voices.status_code == 200, voices.text
    voice = voices.json()["items"][0]
    assert voice["source_mode"] == "LIBRARY"
    assert voice["name"] == "Renkoka Voice Sample"
    # The Library audio is immediately playable as the approved preview.
    assert voice["approved_preview_asset_id"] == asset_id

    # The Voice Creator workspace read carries the creator-facing asset name.
    workspace = client.get(f"/api/projects/{project_id}/characters/{character_id}/voice")
    assert workspace.status_code == 200, workspace.text
    active = workspace.json()["activeVoice"]
    assert active["approvedVoiceReferenceAssetId"] == asset_id
    assert active["approvedVoiceReferenceAssetName"] == "Renkoka Voice Sample"


def test_voice_reference_preserves_existing_provider_binding(client):
    """Assigning Library audio must not erase an ElevenLabs provider binding."""
    from app.character_identity import service

    project_id = _project(client)
    character_id = _character(client, project_id)
    _save_voice(client, project_id, character_id)
    db = SessionLocal()
    try:
        service.assign_provider_voice(
            db,
            project_id,
            character_id,
            provider_voice_id="el-voice-123",
            voice_name="Renkoka Final",
            model_id="eleven_v4",
        )
    finally:
        db.close()

    asset_id = _audio_asset(project_id, tag="Renkoka Voice Sample")
    attach = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/voice/reference",
        json={"assetId": asset_id},
    )
    assert attach.status_code == 200, attach.text

    authority = client.get(f"/api/projects/{project_id}/characters/{character_id}/voice/authority")
    auth = authority.json()
    assert auth["provider"] == "elevenlabs"
    assert auth["providerVoiceId"] == "el-voice-123"
    assert auth["voiceName"] == "Renkoka Final"
    assert auth["approvedVoiceReferenceAssetId"] == asset_id
    assert auth["approvedVoiceReferenceAssetName"] == "Renkoka Voice Sample"


def test_voice_reference_allows_global_character_cross_project_asset(client):
    """Global Character: the Library audio may live in the current project while
    the character's home project is elsewhere — linked by id, never copied."""
    from app.character_identity.models import CharacterProfileRow

    home_project = _project(client)
    character_id = _character(client, home_project, name=f"Global Voice Ref {uuid.uuid4().hex[:6]}")
    db = SessionLocal()
    try:
        row = db.get(CharacterProfileRow, character_id)
        row.is_global = True
        db.commit()
    finally:
        db.close()

    other_project = _project(client)
    asset_id = _audio_asset(other_project, tag="Renkoka Voice Sample")
    attach = client.post(
        f"/api/projects/{other_project}/characters/{character_id}/voice/reference",
        json={"assetId": asset_id},
    )
    assert attach.status_code == 200, attach.text
    assert attach.json()["approvedVoiceReferenceAssetId"] == asset_id


def test_voice_reference_rejects_wrong_kind(client):
    project_id = _project(client)
    character_id = _character(client, project_id)
    _save_voice(client, project_id, character_id)
    db = SessionLocal()
    try:
        image = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="image",
            tag="reference",
            filename=f"{uuid.uuid4().hex}.png",
            path=f"library/images/{uuid.uuid4().hex}.png",
        )
        db.add(image)
        db.commit()
        image_id = image.id
    finally:
        db.close()

    wrong_kind = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/voice/reference",
        json={"assetId": image_id},
    )
    assert wrong_kind.status_code == 400
    assert wrong_kind.json()["detail"]["code"] == "ASSET_NOT_AUDIO"


def test_voice_reference_rejects_other_project_asset(client):
    project_id = _project(client)
    other_project = _project(client)
    character_id = _character(client, project_id)
    _save_voice(client, project_id, character_id)
    foreign = _audio_asset(other_project)

    response = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/voice/reference",
        json={"assetId": foreign},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ASSET_NOT_IN_PROJECT"


def test_timeline_stages_voice_reference_for_character_voice_shots(client, monkeypatch):
    from app.film_timeline import orchestrator

    project_id = _project(client)
    character_id = _character(client, project_id, "Renkoka")
    _save_voice(client, project_id, character_id)
    asset_id = _audio_asset(project_id)
    attach = client.post(
        f"/api/projects/{project_id}/characters/{character_id}/voice/reference",
        json={"assetId": asset_id},
    )
    assert attach.status_code == 200, attach.text

    from app.film_timeline.contracts import ReferenceAsset

    class _FakeShotState:
        references = [
            ReferenceAsset(type="character", assetId="img-1", label="Renkoka", tag="Renkoka")
        ]
        firstFrameAssetId = None
        modelPrompt = ""
        spokenLanguage = "en"
        spokenLanguageCustom = ""
        dialogueAuthority = "character_voice"
        resolvedGeneration = {}

    class _FakeShot:
        id = "shot_1"
        timedPrompt = "Renkoka greets the crew."
        state = _FakeShotState()

    class _FakeSegment:
        id = "seg_1"
        order = 0
        durationSec = 6
        timedPrompt = "Renkoka greets the crew."
        generationMetadata = {}

    class _FakeFilm:
        references = []

    captured: dict = {}

    def _fake_build_director_refs(slots, mapped_start_asset_id=None, generator_id=None):
        captured["slots"] = list(slots)
        return {"slots": slots, "pictures": [], "videos": [], "audios": []}

    from app.film_timeline import director_refs as director_refs_module
    from app.film_timeline import dialogue_authority as dialogue_module

    monkeypatch.setattr(director_refs_module, "build_director_refs", _fake_build_director_refs)
    monkeypatch.setattr(orchestrator, "_segment_legal_resolution", lambda *a, **k: "720p")
    monkeypatch.setattr(
        dialogue_module,
        "resolve_speakers",
        lambda db, pid, shot, refs: [
            {
                "characterId": character_id,
                "name": "Renkoka",
                "provider": "local",
                "voiceName": "Renkoka Final",
                "usable": True,
                "voice": {
                    "approvedVoiceReferenceAssetId": asset_id,
                    "activeVoiceProfileId": "voice-renkoka",
                },
            }
        ],
    )

    class _FakeAdapter:
        capabilities = type(
            "Caps",
            (),
            {
                "supportsImageToVideo": True,
                "supportsVideoReferences": True,
                "supportsReferenceToVideo": True,
                "supportsTextToVideo": True,
            },
        )()

    monkeypatch.setattr(orchestrator, "_adapter", lambda generator_id: _FakeAdapter())
    monkeypatch.setattr(orchestrator, "_is_local_h3", lambda generator_id: True)

    db = SessionLocal()
    try:
        request = orchestrator._build_request(
            db,
            project_id,
            "scene_1",
            _FakeShot(),
            _FakeSegment(),
            "h3_fast",
            "reference_set",
            None,
            _FakeFilm(),
        )
    finally:
        db.close()

    audio_slots = [slot for slot in captured["slots"] if slot.get("role") == "audio"]
    assert len(audio_slots) == 1
    assert audio_slots[0]["assetId"] == asset_id
    assert "Renkoka" in str(audio_slots[0]["label"])
    assert request.providerOptions["dialogueAuthority"]["mode"] == "character_voice"
    snapshot = request.providerOptions["characterVoiceSnapshot"]
    assert snapshot[0]["voiceProfileId"] == "voice-renkoka"
    assert snapshot[0]["approvedVoiceReferenceAssetId"] == asset_id
    assert snapshot[0]["characterId"] == character_id


def test_timeline_voice_reference_limit_is_honest(client, monkeypatch):
    from app.film_timeline import orchestrator

    project_id = _project(client)

    class _FakeShotState:
        references = []
        firstFrameAssetId = None
        modelPrompt = ""
        spokenLanguage = "en"
        spokenLanguageCustom = ""
        dialogueAuthority = "character_voice"
        resolvedGeneration = {}

    class _FakeShot:
        id = "shot_1"
        timedPrompt = "Four voices argue."
        state = _FakeShotState()

    class _FakeSegment:
        id = "seg_1"
        order = 0
        durationSec = 6
        timedPrompt = "Four voices argue."
        generationMetadata = {}

    class _FakeFilm:
        references = []

    speakers = [
        {
            "characterId": f"char-{index}",
            "name": f"Character {index}",
            "provider": "local",
            "voiceName": f"Voice {index}",
            "usable": True,
            "voice": {"approvedVoiceReferenceAssetId": f"aud-{index}"},
        }
        for index in range(4)
    ]
    from app.film_timeline import dialogue_authority as dialogue_module

    monkeypatch.setattr(dialogue_module, "resolve_speakers", lambda db, pid, shot, refs: speakers)
    monkeypatch.setattr(orchestrator, "_is_local_h3", lambda generator_id: True)

    class _FakeAdapter:
        capabilities = type(
            "Caps",
            (),
            {
                "supportsImageToVideo": True,
                "supportsVideoReferences": True,
                "supportsReferenceToVideo": True,
                "supportsTextToVideo": True,
            },
        )()

    monkeypatch.setattr(orchestrator, "_adapter", lambda generator_id: _FakeAdapter())

    db = SessionLocal()
    try:
        with pytest.raises(Exception) as excinfo:
            orchestrator._build_request(
                db,
                project_id,
                "scene_1",
                _FakeShot(),
                _FakeSegment(),
                "h3_fast",
                "reference_set",
                None,
                _FakeFilm(),
            )
    finally:
        db.close()
    assert "at most 3 audio references" in str(excinfo.value)
