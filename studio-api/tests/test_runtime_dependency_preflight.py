"""H3 submit preflight stages every required Library asset before queueing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.runtime_dependency_preflight import (
    preflight_generation_dependencies,
)


def _request(*, slots, voices=None, source=None) -> TimelineGenerationRequest:
    return TimelineGenerationRequest(
        projectId="proj",
        sceneId="scene",
        batchBlockId="bb",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt="<Picture 1> walk",
        duration=8.0,  # 8s = 192 frames; H3 R2V requires n ≡ 5 (mod 17), 192 mod 17 = 5
        providerOptions={
            "r2v": {"mechanism": "h3_ref2va", "slots": slots},
            "draftMode": True,
            "fast_generation": True,
            "characterVoices": voices or {"applied": True, "voices": [], "missing": []},
            "rangeReplacement": {"sourceAssetId": source} if source else None,
        },
    )


def test_preflight_blocks_missing_voice_file(tmp_path):
    picture = SimpleNamespace(id="pic-1", path=str(tmp_path / "p.png"), comfy_name="", kind="image")
    (tmp_path / "p.png").write_bytes(b"png")
    voice = SimpleNamespace(id="voice-1", path=str(tmp_path / "missing.wav"), comfy_name="", kind="audio")
    db = MagicMock()
    db.get.side_effect = lambda _model, key: {"pic-1": picture, "voice-1": voice}.get(key)
    result = preflight_generation_dependencies(
        db,
        _request(
            slots=[
                {"role": "character", "assetId": "pic-1", "label": "Hero", "pictureIndex": 1},
                {"role": "audio", "assetId": "voice-1", "label": "Hero", "audioIndex": 1},
            ]
        ),
    )
    assert result["ok"] is False
    assert result["error"] == "DEPENDENCY_NOT_READY"
    assert "missing" in result["message"].lower() or "Library" in result["message"]


def test_preflight_allows_missing_character_voice(tmp_path):
    """Voices are OPTIONAL — a character without an approved voice should NOT
    block generation. The character simply won't speak (no lip-sync audio).
    The H3 workflow runs with pictures only."""
    from app.video_runtime import comfy_asset_stage as stage_mod

    stage_mod.settings.comfy_input_dir = tmp_path / "input"
    pic = tmp_path / "face.png"
    pic.write_bytes(b"png-bytes")
    picture = SimpleNamespace(id="pic-1", path=str(pic), comfy_name="studio/old.png", kind="image")
    db = MagicMock()
    db.get.side_effect = lambda _model, key: {"pic-1": picture}.get(key)
    result = preflight_generation_dependencies(
        db,
        _request(
            slots=[{"role": "character", "assetId": "pic-1", "label": "Hero", "pictureIndex": 1}],
            voices={"applied": False, "voices": [], "missing": ["Hero"]},
        ),
    )
    # Missing voice is a WARNING, not a BLOCKER
    assert result["ok"] is True
    deps = result["dependencies"]
    assert deps["voices"][0]["status"] == "MISSING"
    assert deps["voices"][0]["label"] == "Hero"
    # Voice warnings are surfaced for the UI
    warnings = deps.get("voiceWarnings") or []
    assert any("Hero" in w.get("label", "") for w in warnings)


def test_preflight_stages_pictures_and_voices(tmp_path, monkeypatch):
    from app.video_runtime import comfy_asset_stage as stage_mod

    monkeypatch.setattr(stage_mod.settings, "comfy_input_dir", tmp_path / "input")
    pic = tmp_path / "face.png"
    wav = tmp_path / "voice.wav"
    pic.write_bytes(b"png-bytes")
    wav.write_bytes(b"wav-bytes")
    picture = SimpleNamespace(id="pic-1", path=str(pic), comfy_name="studio/old.png", kind="image")
    voice = SimpleNamespace(id="voice-1", path=str(wav), comfy_name="studio/old.wav", kind="audio")
    db = MagicMock()
    db.get.side_effect = lambda _model, key: {"pic-1": picture, "voice-1": voice}.get(key)
    request = _request(
        slots=[
            {"role": "character", "assetId": "pic-1", "label": "Hero", "pictureIndex": 1},
            {"role": "audio", "assetId": "voice-1", "label": "Hero", "audioIndex": 1},
        ]
    )
    result = preflight_generation_dependencies(db, request)
    assert result["ok"] is True
    deps = result["dependencies"]
    assert deps["workflow"] == "READY"
    assert deps["pictures"][0]["status"] == "READY"
    assert deps["voices"][0]["status"] == "READY"
    assert deps["voices"][0]["comfyName"] == "studio/voice-1.wav"
    assert (tmp_path / "input" / "studio" / "voice-1.wav").is_file()
    assert request.providerOptions["runtimeDependencies"]["workflow"] == "READY"
