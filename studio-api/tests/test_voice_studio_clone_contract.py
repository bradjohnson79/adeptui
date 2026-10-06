"""Voice Studio clone contract — no creator transcript, one permission checkbox."""

from __future__ import annotations

import io
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.character_identity.schemas import VoiceConsentCreate
from app.character_identity.voice import validate_voice_reference
from app.character_identity import voice_runtime
from app.character_identity.voice_runtime import (
    _clone_spoken_line,
    _clone_wanted_count,
    _comfy_queue_busy,
    _require_voice_vram,
    release_idle_comfy_models_for_voice,
    studio_clone_consent,
)
from app.character_identity.api import CloneVoiceBody


def _wav(seconds: float = 11.0, rate: int = 24000) -> bytes:
    frames = int(rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        samples = bytearray()
        for n in range(frames):
            value = int(6000 * (1 if (n // 40) % 2 == 0 else -1))
            samples += struct.pack("<h", value)
        handle.writeframes(bytes(samples))
    return buf.getvalue()


def test_validate_voice_reference_does_not_require_transcript(tmp_path: Path):
    path = tmp_path / "korri.wav"
    path.write_bytes(_wav(11.0))
    report = validate_voice_reference(path, transcript="")
    assert report["ok"] is True
    assert report["transcript_present"] is False


def test_studio_clone_consent_checkbox_implies_synthetic():
    consent = VoiceConsentCreate(
        source_owner_name="Korri",
        performer_name="Korri",
        consent_confirmed=True,
        synthetic_generation_allowed=False,
        confirmed_by="owner",
    )
    normalized = studio_clone_consent(consent)
    assert normalized.consent_confirmed is True
    assert normalized.synthetic_generation_allowed is True


def test_clone_body_accepts_missing_transcript_and_visible_sample_count():
    body = CloneVoiceBody.model_validate(
        {
            "name": "Korri Clone",
            "reference_path": "C:/tmp/korri.wav",
            "reference_asset_id": "asset-1",
            "testLine": "Light circuitry, not tattoos, doofus.",
            "sampleCount": 2,
            "consent": {
                "source_owner_name": "Korri",
                "performer_name": "Korri",
                "consent_confirmed": True,
                "confirmed_by": "owner",
            },
        }
    )
    assert body.transcript == ""
    assert body.testLine == "Light circuitry, not tattoos, doofus."
    assert body.sampleCount == 2
    assert body.consent.consent_confirmed is True
    assert body.consent.synthetic_generation_allowed is False


def test_comfy_queue_busy_when_a_prompt_is_running():
    assert _comfy_queue_busy({"queue_running": [["prompt"]], "queue_pending": []}) is True
    assert _comfy_queue_busy({"queue_running": [], "queue_pending": []}) is False
    assert _comfy_queue_busy(None) is True


def test_release_idle_comfy_skips_a_busy_queue(monkeypatch):
    calls = []

    class FakeComfy:
        async def get_queue(self):
            return {"queue_running": [["live"]], "queue_pending": []}

        async def free_memory(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr("app.comfy_client.comfy", FakeComfy())
    assert release_idle_comfy_models_for_voice() is False
    assert calls == []


def test_release_idle_comfy_frees_when_the_queue_is_empty(monkeypatch):
    calls = []

    class FakeComfy:
        async def get_queue(self):
            return {"queue_running": [], "queue_pending": []}

        async def free_memory(self, **kwargs):
            calls.append(kwargs)
            return {"ok": True}

    monkeypatch.setattr("app.comfy_client.comfy", FakeComfy())
    assert release_idle_comfy_models_for_voice() is True
    assert calls == [{"unload_models": True, "free_memory": True}]


def test_voice_vram_frees_idle_comfy_before_refusing(monkeypatch):
    seen = {"free": 1800}
    calls = []

    def free_mib():
        return seen["free"]

    def release():
        calls.append("free")
        seen["free"] = 8000
        return True

    monkeypatch.setattr(voice_runtime, "_gpu_free_mib", free_mib)
    monkeypatch.setattr(voice_runtime, "release_idle_comfy_models_for_voice", release)
    monkeypatch.setattr(voice_runtime.time, "sleep", lambda _seconds: None)
    _require_voice_vram(4096, kind="clone")
    assert calls == ["free"]


def test_voice_vram_does_not_touch_comfy_when_memory_is_already_free(monkeypatch):
    monkeypatch.setattr(voice_runtime, "_gpu_free_mib", lambda: 20000)

    def release():
        raise AssertionError("Comfy free should stay idle when memory is already available")

    monkeypatch.setattr(voice_runtime, "release_idle_comfy_models_for_voice", release)
    _require_voice_vram(4096, kind="clone")


def test_voice_vram_still_refuses_without_switching_engine(monkeypatch):
    monkeypatch.setattr(voice_runtime, "_gpu_free_mib", lambda: 1000)
    monkeypatch.setattr(voice_runtime, "release_idle_comfy_models_for_voice", lambda: True)
    monkeypatch.setattr(voice_runtime.time, "sleep", lambda _seconds: None)
    with pytest.raises(HTTPException) as exc:
        _require_voice_vram(4096, kind="clone")
    detail = exc.value.detail
    assert exc.value.status_code == 503
    assert detail["code"] == "GPU_MEMORY"
    assert "did not switch to another engine or CPU" in detail["message"]
    assert "1000 MiB" in detail["message"]


def test_clone_wanted_count_prefers_just_clicked_sample_count():
    body = SimpleNamespace(sampleCount=1, candidateCount=4, candidate_count=3)
    assert _clone_wanted_count(body) == 1
    assert _clone_wanted_count(SimpleNamespace(sampleCount=4, candidateCount=2)) == 4
    assert _clone_spoken_line(SimpleNamespace(testLine="Hey.", test_line="Nope")) == "Hey."
