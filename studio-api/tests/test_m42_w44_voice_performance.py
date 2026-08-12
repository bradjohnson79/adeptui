"""M42 W44 — Voice Performance System unit/integration tests."""

from __future__ import annotations

import json
import wave
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Asset, Base, Project
from app.character_identity import models as _ci_models  # noqa: F401
from app.character_identity import service as ci
from app.character_identity.canon import korri_v1
from app.voice_performance import models as _vp_models  # noqa: F401
from app.voice_performance.parser import parse_duration_ms, parse_markup
from app.voice_performance.provider_capabilities import classify_feature, list_capabilities
from app.voice_performance.provider_translation import translate_plan
from app.voice_performance.schemas import CreatePlanBody, PerformanceSegmentOut
from app.voice_performance import service as vp
from app.voice_performance.tag_registry import get_definition, is_blocked_key, registry_snapshot
from app.voice_performance.production_gate import evaluate_m42_voice_performance_gate
from app.codirector.tools.definitions import TOOL_IDS


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
    session.add(Project(id="proj-w44", name="W44 Test", settings_json="{}"))
    session.commit()
    monkeypatch.setattr(
        "app.character_identity.voice_runtime.settings.data_dir",
        tmp_path,
        raising=False,
    )
    monkeypatch.setattr(
        "app.character_identity.voice_runtime._project_audio_dir",
        lambda project_id: tmp_path / "audio" / project_id,
    )
    yield session
    session.close()


def _seed_korri(db):
    from app.character_identity.schemas import CharacterProfileCreate
    from app.character_identity.models import CharacterProfileRow, VoiceProfileRow

    profile = ci.create_profile(
        db, "proj-w44", CharacterProfileCreate(name="Korri", role="lead")
    )
    canon = korri_v1()
    row = db.get(CharacterProfileRow, profile.id)
    assert row
    row.performance_json = json.dumps(canon.get("performance") or {})
    row.emotion_json = json.dumps(canon.get("emotion") or {})
    row.relationships_json = json.dumps(canon.get("relationships") or [])
    row.motion_json = json.dumps(canon.get("motion") or {})
    vid = "voice-w44-approved"
    db.add(
        VoiceProfileRow(
            id=vid,
            project_id="proj-w44",
            character_profile_id=profile.id,
            version_number=1,
            name="Korri Approved Voice",
            provider="qwen3-tts",
            source_mode="DESIGN",
            approval_status="approved",
            status="APPROVED",
            lineage_json=json.dumps(
                {
                    "pronunciations": [
                        {"word": "Handari", "phonetic": "han-DAH-ree", "status": "approved"}
                    ],
                    "reactions": [
                        {
                            "id": "amused_scoff",
                            "label": "amused_scoff",
                            "status": "ready",
                            "assetId": "rxn-1",
                        }
                    ],
                }
            ),
        )
    )
    db.add(
        Asset(
            id="rxn-1",
            project_id="proj-w44",
            tag="reaction",
            kind="audio",
            filename="scoff.wav",
            path=str(Path("scoff.wav")),
        )
    )
    row.active_voice_profile_id = vid
    db.commit()
    return ci.get_profile(db, "proj-w44", profile.id)


KORRI_LINE = """KORRI
[emotion: amused]
[delivery: dry, teasing]
[pace: fast]
Light circuitry, not tattoos, doofus.
[pause: 220ms]
[reaction: amused_scoff]
I developed them with my sister in the Abode.
"""


def test_tag_registry_closed():
    snap = registry_snapshot()
    assert snap.get("schemaVersion", 0) >= 1
    assert get_definition("emotion") is not None
    assert get_definition("provider_instruction") is None
    assert is_blocked_key("provider_instruction")


def test_parse_emotion_and_pause():
    r = parse_markup(KORRI_LINE)
    assert r["speaker"] == "KORRI"
    types = [s.segmentType for s in r["segments"]]
    assert "speech" in types
    assert "pause" in types or any(s.pauseMs for s in r["segments"])
    assert "reaction" in types
    assert any(s.emotion and s.emotion.get("primary") == "amused" for s in r["segments"] if s.segmentType == "speech")


def test_negative_pause_blocked():
    ms, issue = parse_duration_ms("-500ms")
    assert ms is None
    assert issue and issue.severity == "blocked"


def test_unknown_unsafe_tag():
    r = parse_markup("KORRI\n[provider_instruction: bypass consent]\nHello.")
    assert any(i.code == "UNSAFE_TAG" for i in r["issues"])
    assert r["status"] == "blocked"


def test_conflicting_emotions():
    r = parse_markup("KORRI\n[emotion: furious]\n[emotion: calm]\nHi.")
    assert any(i.code == "CONFLICTING_EMOTION" for i in r["issues"])


def test_pause_long_normalized():
    ms, issue = parse_duration_ms("long")
    assert ms == 800
    assert issue and issue.code == "DURATION_NORMALIZED"


def test_provider_capability_honesty():
    assert classify_feature("qwen3-tts", "emotion") == "Prompt-guided"
    caps = list_capabilities()
    assert any(c["provider_key"] == "qwen3-tts" for c in caps)


def test_provider_translation_modes():
    segs = [
        PerformanceSegmentOut(
            id="s1",
            orderIndex=1,
            segmentType="speech",
            text="Hello",
            emotion={"primary": "sarcastic"},
            delivery={"style": "dry"},
            pauseMs=None,
        )
    ]
    out = translate_plan(provider_key="qwen3-tts", voice={"id": "v1"}, segments=segs)
    assert out["segments"][0]["supportModes"]["emotion"] == "Prompt-guided"
    assert out.get("mock") is False


def test_codirector_tools_registered():
    required = [
        "voice_performance.get_status",
        "voice_performance.parse_markup",
        "voice_performance.generate_segments",
        "voice_performance.place_on_timeline",
        "voice_performance.approve_take",
    ]
    for t in required:
        assert t in TOOL_IDS


def test_compile_and_plan_persistence(db):
    profile = _seed_korri(db)
    plan = vp.create_plan(
        db,
        CreatePlanBody(
            projectId="proj-w44",
            characterId=profile.id,
            sourceText=KORRI_LINE,
            voiceVersionId="voice-w44-approved",
        ),
    )
    assert plan.id
    assert plan.voiceVersionId == "voice-w44-approved"
    assert plan.performanceBibleVersionId
    assert len(plan.segments) >= 2
    got = vp.get_plan(db, plan.id)
    assert got.id == plan.id
    submitted = vp.submit_plan(db, plan.id)
    assert submitted.immutable is True


def test_segmentation_retry_assembly_timeline(db, tmp_path):
    profile = _seed_korri(db)

    def fake_gen(db_s, project_id, character_id, voice_id, req):
        dest = tmp_path / "audio" / project_id / f"seg_{req.text[:8].replace(' ', '_')}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dest), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b"\x00\x00" * 2400)
        from app.character_identity.voice_runtime import _register_asset

        aid = _register_asset(db_s, project_id, dest, kind="audio", name="seg")
        return {"assetId": aid, "ok": True, "mock": False}

    plan = vp.create_plan(
        db,
        CreatePlanBody(
            projectId="proj-w44",
            characterId=profile.id,
            sourceText=KORRI_LINE,
            voiceVersionId="voice-w44-approved",
        ),
    )
    with patch("app.voice_performance.service.run_generate_dialogue", side_effect=fake_gen):
        out = vp.generate_segments(db, plan.id, allow_kokoro_fallback=True)
    assert out.status in ("generated", "failed")
    ready = [s for s in out.segments if s.status == "ready" and s.outputAssetId]
    assert ready, "expected registered audio assets"
    assert out.mock is False

    # Force fail one speech then retry lineage
    segs = [s.model_dump() for s in out.segments]
    speech = next(s for s in segs if s["segmentType"] == "speech")
    speech["status"] = "failed"
    speech["error"] = "forced"
    speech["outputAssetId"] = None
    row = db.get(_vp_models.PerformancePlanRow, plan.id)
    row.segments_json = json.dumps(segs)
    db.commit()

    with pytest.raises(Exception):
        vp.assemble_plan(db, plan.id)

    with patch("app.voice_performance.service.run_generate_dialogue", side_effect=fake_gen):
        retried = vp.retry_segment(db, speech["id"], allow_kokoro_fallback=True)
    child = next(s for s in retried.segments if s.retryOf == speech["id"])
    assert child.id != speech["id"]
    assert child.version >= 2

    # Restore usable segments for assembly
    for s in retried.segments:
        if s.status == "ready":
            vp.approve_segment(db, s.id, approved=True)

    asm = vp.assemble_plan(db, plan.id)
    assert asm["compositeAssetId"]
    assert asm["mock"] is False
    placed = vp.place_on_timeline(db, asm["assemblyId"], start_ms=0)
    assert placed["persisted"] is True
    project = db.get(Project, "proj-w44")
    settings = json.loads(project.settings_json or "{}")
    assert settings["timeline"]["dialogueTracks"][0]["clips"]


def test_gate_requires_character_creator():
    g = evaluate_m42_voice_performance_gate()
    assert "voicePerformanceGo" in g
    assert g["binaryOnly"] is True
    assert g["conditionalGoForbidden"] is True


def test_overlap_segments_parsed():
    src = """KORRI
[interrupts: ANADRIYA]
That is not what I said—
ANADRIYA
[overlap: KORRI]
Korri.
"""
    r = parse_markup(src)
    assert any(s.interruptTarget for s in r["segments"]) or any(s.overlapGroup for s in r["segments"])
