from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.character_identity.models import CharacterProfileRow, VoiceProfileRow
from app.db import Asset, Base, Project, Scene
from app.voice_performance.emotion_presets import get_preset, normalize_mix
from app.voice_performance.m410_models import VoicePerformanceRecordRow, VoicePerformanceTakeRow
from app.voice_performance.m410_schemas import (
    PerformancePlanPatchBody,
    RuntimeInstallBody,
    VoicePerformanceRecordCreate,
)
from app.voice_performance import m410_service as svc


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-m410", name="M410 Test", settings_json="{}"))
    session.add(Scene(id="scene-m410", project_id="proj-m410", name="Scene M410"))
    monkeypatch.setattr("app.voice_performance.runtime.index_tts2.settings.data_dir", tmp_path, raising=False)
    yield session
    session.close()


def seed_character_and_voice(db, *, approved: bool = True, voice_id: str = "voice-approved") -> tuple[str, str]:
    db.add(
        CharacterProfileRow(
            id="char-m410",
            project_id="proj-m410",
            name="Korri",
            status="APPROVED",
            approval_status="approved",
        )
    )
    db.add(
        VoiceProfileRow(
            id=voice_id,
            project_id="proj-m410",
            character_profile_id="char-m410",
            version_number=2,
            name="Korri Voice",
            provider="index-tts2-local",
            source_mode="DESIGN",
            status="APPROVED" if approved else "DRAFT",
            approval_status="approved" if approved else "draft",
            language="en",
        )
    )
    db.commit()
    return "char-m410", voice_id


def make_record(db, *, voice_id: str = "voice-approved", scene_id: str | None = "scene-m410"):
    character_id, voice_id = seed_character_and_voice(db, voice_id=voice_id)
    return svc.create_record(
        db,
        VoicePerformanceRecordCreate(
            projectId="proj-m410",
            sceneId=scene_id,
            characterId=character_id,
            voiceIdentityId=voice_id,
            dialogueText="(softly) I thought we had more time...",
            directionMode="codirector",
            manualPlan={"source": "manual", "notes": "fallback manual plan"},
            codirectorPlan={"source": "codirector", "emotionVector": {"sadness": 1.0}},
            performancePlan={"source": "codirector", "emotionVector": {"sadness": 1.0}},
        ),
    )


def seed_audio_asset(db, asset_id: str = "asset-audio-1") -> str:
    db.add(
        Asset(
            id=asset_id,
            project_id="proj-m410",
            tag="dialogue",
            kind="audio",
            filename="line.wav",
            path="line.wav",
        )
    )
    db.commit()
    return asset_id


def test_emotion_preset_mapping():
    preset = get_preset("quiet-grief")
    assert preset is not None
    assert preset["emotionVector"]["sadness"] > preset["emotionVector"].get("fear", 0.0)
    mix = normalize_mix({"hate": 1, "anger": 1})
    assert "contempt" in mix
    assert pytest.approx(sum(mix.values()), rel=1e-3) == 1.0


def test_emotion_vector_validation():
    patched = PerformancePlanPatchBody(
        performancePlan={"summary": "test"},
        emotionVector={"hate": 1.0, "joy": 1.0},
    )
    assert "contempt" in patched.emotionVector
    with pytest.raises(ValidationError):
        VoicePerformanceRecordCreate(
            projectId="proj-m410",
            characterId="char-m410",
            voiceIdentityId="voice-approved",
            dialogueText="Hello",
            emotionVector={"sarcasm": 1.0},
        )


def test_direction_mode_switching_preserves_data(db):
    record = make_record(db)
    manual_plan = {"source": "manual", "notes": "nudge toward restraint"}
    manual = svc.set_direction_mode(db, record.id, "manual", performance_plan=manual_plan)
    assert manual.directionMode == "manual"
    assert manual.manualPlan == manual_plan
    assert manual.codirectorPlan["source"] == "codirector"

    switched_back = svc.set_direction_mode(db, record.id, "codirector")
    assert switched_back.directionMode == "codirector"
    assert switched_back.performancePlan["source"] == "codirector"
    assert switched_back.manualPlan == manual_plan


def test_voice_identity_required(db):
    character_id, voice_id = seed_character_and_voice(db, approved=False, voice_id="voice-draft")
    with pytest.raises(HTTPException) as exc:
        svc.create_record(
            db,
            VoicePerformanceRecordCreate(
                projectId="proj-m410",
                characterId=character_id,
                voiceIdentityId=voice_id,
                dialogueText="You cannot use this yet.",
            ),
        )
    assert exc.value.detail["code"] == "VOICE_IDENTITY_REQUIRED"


def test_global_character_voice_can_create_record_in_open_project(db):
    db.add(Project(id="proj-open", name="Open Project", settings_json="{}"))
    db.add(
        CharacterProfileRow(
            id="char-global",
            project_id="proj-m410",
            name="Anadriya",
            status="APPROVED",
            approval_status="approved",
            is_global=True,
            active_voice_profile_id="voice-home",
        )
    )
    db.add(
        VoiceProfileRow(
            id="voice-home",
            project_id="proj-m410",
            character_profile_id="char-global",
            version_number=1,
            name="Anadriya Clone",
            provider="qwen3-tts",
            source_mode="CLONE",
            status="APPROVED",
            approval_status="approved",
            language="en",
        )
    )
    db.commit()
    record = svc.create_record(
        db,
        VoicePerformanceRecordCreate(
            projectId="proj-open",
            characterId="char-global",
            voiceIdentityId="voice-home",
            dialogueText="Hello. My name is Anadriya.",
        ),
    )
    assert record.projectId == "proj-open"
    assert record.voiceIdentityId == "voice-home"
    assert record.dialogueText == "Hello. My name is Anadriya."


def test_foreign_project_voice_stays_isolated(db):
    db.add(Project(id="proj-other", name="Other Project", settings_json="{}"))
    character_id, voice_id = seed_character_and_voice(db, voice_id="voice-local")
    with pytest.raises(HTTPException) as exc:
        svc.create_record(
            db,
            VoicePerformanceRecordCreate(
                projectId="proj-other",
                characterId=character_id,
                voiceIdentityId=voice_id,
                dialogueText="This character is not visible here.",
            ),
        )
    assert exc.value.detail["code"] == "VOICE_IDENTITY_REQUIRED"


def test_take_approval_exclusivity(db):
    record = make_record(db)
    first_asset = seed_audio_asset(db, "asset-audio-1")
    second_asset = seed_audio_asset(db, "asset-audio-2")
    db.add_all(
        [
            VoicePerformanceTakeRow(
                id="take-1",
                record_id=record.id,
                take_number=1,
                label="Take 1",
                audio_asset_id=first_asset,
                duration_ms=900,
                status="completed",
                direction_snapshot_json={"source": "codirector"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
            VoicePerformanceTakeRow(
                id="take-2",
                record_id=record.id,
                take_number=2,
                label="Take 2",
                audio_asset_id=second_asset,
                duration_ms=950,
                status="completed",
                direction_snapshot_json={"source": "codirector"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        ]
    )
    db.commit()

    first = svc.approve_take(db, record.id, "take-1")
    assert first["approvedTakeId"] == "take-1"

    second = svc.approve_take(db, record.id, "take-2")
    assert second["approvedTakeId"] == "take-2"
    row1 = db.get(VoicePerformanceTakeRow, "take-1")
    row2 = db.get(VoicePerformanceTakeRow, "take-2")
    record_row = db.get(VoicePerformanceRecordRow, record.id)
    assert row1.status == "completed"
    assert row2.status == "approved"
    assert record_row.approved_take_id == "take-2"


def test_timeline_and_lipsync_payload_shape(db):
    record = make_record(db)
    asset_id = seed_audio_asset(db, "asset-dialogue")
    db.add(
        VoicePerformanceTakeRow(
            id="take-approved",
            record_id=record.id,
            take_number=1,
            label="Hero Take",
            audio_asset_id=asset_id,
            duration_ms=1337,
            status="approved",
            direction_snapshot_json={"source": "codirector"},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    record_row = db.get(VoicePerformanceRecordRow, record.id)
    record_row.approved_take_id = "take-approved"
    db.commit()

    proposal = svc.prepare_timeline_dialogue(db, record.id, start_ms=240)
    assert proposal["clip"]["assetId"] == asset_id
    assert proposal["clip"]["recordId"] == record.id
    assert proposal["clip"]["startMs"] == 240

    placed = svc.place_timeline_dialogue(db, record.id, start_ms=240, confirm_replace=True)
    assert placed["persisted"] is True
    assert placed["timelineLinkage"]["approvedTakeId"] == "take-approved"

    lipsync = svc.prepare_lipsync(db, record.id, confirm=True, set_scene_audio_asset=True)
    scene = db.get(Scene, "scene-m410")
    assert lipsync["lipsyncLinkage"]["audioAssetId"] == asset_id
    assert scene.lipsync_audio_asset_id == asset_id
    assert scene.audio_asset_id == asset_id


def test_capability_metadata_honesty(monkeypatch):
    monkeypatch.setattr(
        "app.voice_performance.m410_service.index_tts2.runtime_status",
        lambda: {
            "ok": True,
            "providerId": "index-tts2-local",
            "providerVersion": "m410-contract-1",
            "installed": False,
            "ready": False,
            "availableOnDisk": False,
            "modelRevision": None,
            "runtimeRoot": "x",
            "manifestPath": "y",
            "message": "Not ready.",
            "mock": False,
        },
    )
    monkeypatch.setattr(
        "app.character_identity.voice.provider_readiness",
        lambda: {
            "qwenVoiceClone": {"ready": False},
            "qwenVoiceDesign": {"ready": False},
        },
    )
    caps = svc.get_capabilities()
    assert caps["status"] == "requires_setup"
    assert caps["supportsLiveGeneration"] is False
    assert caps["qwenReady"] is False
    assert caps["sharedWarmWorker"] is False
    assert "contempt" in caps["supportedEmotionVectors"]


def test_capabilities_ready_when_qwen_warm_worker_is_ready(monkeypatch):
    monkeypatch.setattr(
        "app.voice_performance.m410_service.index_tts2.runtime_status",
        lambda: {
            "ok": True,
            "providerId": "index-tts2-local",
            "providerVersion": "m410-contract-1",
            "installed": False,
            "ready": False,
            "availableOnDisk": False,
            "modelRevision": None,
            "runtimeRoot": "x",
            "manifestPath": "y",
            "message": "IndexTTS2 is not ready.",
            "mock": False,
        },
    )
    monkeypatch.setattr(
        "app.character_identity.voice.provider_readiness",
        lambda: {
            "qwenVoiceClone": {"ready": True},
            "qwenVoiceDesign": {"ready": False},
        },
    )
    caps = svc.get_capabilities()
    assert caps["ready"] is True
    assert caps["qwenReady"] is True
    assert caps["sharedWarmWorker"] is True
    assert caps["providerId"] == "qwen3-tts"
    assert "warm" in caps["message"].lower()


def test_create_takes_uses_warm_qwen_for_approved_qwen_voice(db, tmp_path, monkeypatch):
    from app.voice_performance.m410_schemas import GenerateTakesBody

    wav = tmp_path / "take.wav"
    wav.write_bytes(b"RIFF0000WAVEfmt ")
    character_id, voice_id = seed_character_and_voice(db, voice_id="voice-qwen")
    voice = db.get(VoiceProfileRow, voice_id)
    voice.provider = "qwen3-tts"
    voice.source_mode = "CLONE"
    profile = db.get(CharacterProfileRow, character_id)
    profile.active_voice_profile_id = voice_id
    db.commit()
    record = svc.create_record(
        db,
        VoicePerformanceRecordCreate(
            projectId="proj-m410",
            characterId=character_id,
            voiceIdentityId=voice_id,
            dialogueText="Light circuitry, not tattoos, doofus.",
        ),
    )
    assert record.providerId == "qwen3-tts"

    monkeypatch.setattr(
        svc,
        "generate_approved_voice_speech",
        lambda *args, **kwargs: {
            "path": str(wav),
            "complete_ms": 6400,
            "engine": "qwen3-tts",
            "warm_worker": True,
        },
    )
    monkeypatch.setattr(svc, "_wav_duration_ms", lambda path: 3200)
    out = svc.create_takes(db, record.id, GenerateTakesBody(count=2, labels=["Take 1", "Take 2"]))
    assert out["ok"] is True
    assert out["providerId"] == "qwen3-tts"
    assert len(out["takes"]) == 2
    assert out["takes"][0]["status"] == "completed"
    assert out["takes"][0]["audioAssetId"]


def test_create_takes_keeps_first_qwen_take_if_later_take_fails(db, tmp_path, monkeypatch):
    from app.voice_performance.m410_schemas import GenerateTakesBody

    wav = tmp_path / "take.wav"
    wav.write_bytes(b"RIFF0000WAVEfmt ")
    character_id, voice_id = seed_character_and_voice(db, voice_id="voice-qwen-partial")
    voice = db.get(VoiceProfileRow, voice_id)
    voice.provider = "qwen3-tts"
    voice.source_mode = "CLONE"
    profile = db.get(CharacterProfileRow, character_id)
    profile.active_voice_profile_id = voice_id
    db.commit()
    record = svc.create_record(
        db,
        VoicePerformanceRecordCreate(
            projectId="proj-m410",
            characterId=character_id,
            voiceIdentityId=voice_id,
            dialogueText="Hello. My name is Anadriya. I'm the Adept.",
        ),
    )
    calls = {"n": 0}

    def _speech(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("second take failed")
        return {
            "path": str(wav),
            "complete_ms": 6400,
            "engine": "qwen3-tts",
            "warm_worker": True,
        }

    monkeypatch.setattr(svc, "generate_approved_voice_speech", _speech)
    monkeypatch.setattr(svc, "_wav_duration_ms", lambda path: 3200)
    out = svc.create_takes(db, record.id, GenerateTakesBody(count=2, labels=["Take 1", "Take 2"]))
    assert out["ok"] is True
    assert [take["status"] for take in out["takes"]] == ["completed", "failed"]
    assert out["takes"][0]["audioAssetId"]
    assert out["takes"][1]["errorMessage"] == "second take failed"
    rows = (
        db.query(VoicePerformanceTakeRow)
        .filter(VoicePerformanceTakeRow.record_id == record.id)
        .order_by(VoicePerformanceTakeRow.take_number.asc())
        .all()
    )
    assert [row.status for row in rows] == ["completed", "failed"]
    assert rows[0].audio_asset_id


def test_runtime_install_body_defaults_model_download_false():
    body = RuntimeInstallBody(confirm=True)
    assert body.confirm is True
    assert body.confirm_download_models is False
    camel = RuntimeInstallBody.model_validate({"confirm": True, "confirmDownloadModels": True})
    assert camel.confirm_download_models is True


def test_install_runtime_rejects_without_confirm(monkeypatch):
    called = {"install": 0}

    def _boom(**_kwargs):
        called["install"] += 1
        raise AssertionError("install_runtime must not be called without confirm")

    monkeypatch.setattr("app.voice_performance.m410_service.index_tts2.install_runtime", _boom)
    with pytest.raises(HTTPException) as exc:
        svc.install_runtime(confirm=False, confirm_download_models=True)
    assert exc.value.status_code == 409
    assert (exc.value.detail or {}).get("code") == "CONFIRM_REQUIRED"
    assert called["install"] == 0


def test_install_runtime_propagates_confirm_download_models(monkeypatch):
    seen: dict[str, bool] = {}

    def _fake(*, confirm: bool, confirm_download_models: bool = False):
        seen["confirm"] = confirm
        seen["confirm_download_models"] = confirm_download_models
        return {"ok": True, "downloadDeferred": not confirm_download_models}

    monkeypatch.setattr("app.voice_performance.m410_service.index_tts2.install_runtime", _fake)
    out = svc.install_runtime(confirm=True, confirm_download_models=True)
    assert out["ok"] is True
    assert seen == {"confirm": True, "confirm_download_models": True}


def test_m410_records_collection_requires_project_id():
    from app.voice_performance.router import m410_list_records_query

    with pytest.raises(HTTPException) as exc:
        m410_list_records_query(project_id=None, db=None)
    assert exc.value.status_code == 400
    assert (exc.value.detail or {}).get("code") == "PROJECT_ID_REQUIRED"
