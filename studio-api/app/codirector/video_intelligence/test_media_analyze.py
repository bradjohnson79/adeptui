"""Phase C tests — Qwen2.5-Omni AV perception for the Media Intelligence Service.

Covers:
- extract_av_clip keeps the audio track (no ``-an``); VideoChat3 path still strips.
- worker_client routes qwen2-5-omni-7b to the AV clip + Qwen model dir/markers.
- C2: build_packet_from_payload populates summary/visualEvents/audioEvents/
  speechSegments/motionEvents/modelEvidence.qwenOmni.
- Timeline Media Intelligence: contactEvents/characterActions/environmentEvents/
  sceneChanges/cameraMotion/cueOpportunities/musicOpportunities coerced from
  the payload; no "[object Object]" junk and no silent drop of contactEvents.
- Full-duration default: analyze_asset analyzes the FULL probed clip
  (facts.durationSec) unless a Timeline range/explicit duration narrows it;
  TimelineAnalysisContext attaches when scene/range/playhead kwargs arrive.
- C3: deterministic media facts come from media_probe ONLY — VLM payload
  claims about codec/sampleRate/colorspace/frameCount never leak into
  packet.media.
- GPU admission: generation-active and insufficient-VRAM both yield explicit
  unavailable packets without invoking the model.

Pure unit tests (mocked subprocess / monkeypatched GPU probes). No GPU, no
ComfyUI, no Studio API. Live C1/C2 proof is a separate scripted run.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Asset, Base, Project, ProjectTraitRow  # noqa: F401  (register tables)
from app.codirector.video_intelligence import clip_extract, media_analyze, worker_client
from app.codirector.video_intelligence.media_packet import (
    QWEN_OMNI_MODEL_ID,
    MediaFacts,
    MediaIntelligencePacket,
)
from app.codirector.video_intelligence.media_persist import load_packet


# ── clip_extract: audio-retaining vs audio-stripped ─────────────────────────


def _fake_run_factory(record: list[list[str]]):
    def _run(cmd, **kwargs):
        record.append(list(cmd))
        dest = Path(cmd[-1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-mp4")

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Proc()

    return _run


def test_extract_av_clip_keeps_audio(monkeypatch, tmp_path):
    record: list[list[str]] = []
    monkeypatch.setattr(clip_extract, "ffmpeg_bin", lambda: "ffmpeg")
    monkeypatch.setattr(clip_extract.subprocess, "run", _fake_run_factory(record))
    src = tmp_path / "source.mp4"
    src.write_bytes(b"src")
    out = clip_extract.extract_av_clip(str(src), str(tmp_path / "clip.avreview512.mp4"), duration_sec=4.0)
    cmd = record[0]
    assert "-an" not in cmd, "Qwen AV clip must NOT strip audio"
    assert "-c:a" in cmd and "aac" in cmd
    assert "-ar" in cmd and "16000" in cmd
    assert "-ac" in cmd and "1" in cmd
    assert Path(out).is_file()


def test_extract_review_clip_still_strips_audio(monkeypatch, tmp_path):
    """Regression: VideoChat3 low-res path keeps the -an audio strip."""
    record: list[list[str]] = []
    monkeypatch.setattr(clip_extract, "ffmpeg_bin", lambda: "ffmpeg")
    monkeypatch.setattr(clip_extract.subprocess, "run", _fake_run_factory(record))
    src = tmp_path / "source.mp4"
    src.write_bytes(b"src")
    clip_extract.extract_review_clip(str(src), str(tmp_path / "clip.review512.mp4"), duration_sec=3.0)
    assert "-an" in record[0]


def test_cleanup_av_clip_allowed_and_source_protected(tmp_path):
    src = tmp_path / "approved.mp4"
    src.write_bytes(b"src")
    av = tmp_path / "approved.avreview512.mp4"
    av.write_bytes(b"clip")
    assert clip_extract.cleanup_extracted_clip(str(av), source_path=str(src)) is True
    assert not av.exists()
    # Never deletes the source approved MP4.
    assert clip_extract.cleanup_extracted_clip(str(src), source_path=str(src)) is False
    assert src.exists()


# ── worker_client routing ────────────────────────────────────────────────────


def test_model_route_qwen_is_audio_retaining():
    model_dir, markers, audio_retaining = worker_client._model_route(QWEN_OMNI_MODEL_ID)
    assert audio_retaining is True
    assert model_dir.name == "qwen2-5-omni-7b"
    assert "config.json" in markers
    _, _, av_vc3 = worker_client._model_route("videochat3-4b")
    _, _, av_iv3 = worker_client._model_route("internvideo3-8b-instruct")
    assert av_vc3 is False and av_iv3 is False


def test_run_av_perception_uses_av_clip_and_qwen_worker(monkeypatch, tmp_path):
    """Full wiring: av extract (not review extract) -> worker cmd carries the
    qwen model id + qwen model path -> payload dict returned verbatim."""
    src = tmp_path / "shot.mp4"
    src.write_bytes(b"src")
    calls = {"av": 0, "review": 0, "cmd": None}

    def fake_av(video_path, dest_path, **kwargs):
        calls["av"] += 1
        Path(dest_path).write_bytes(b"clip")
        return dest_path

    def fake_review(video_path, dest_path, **kwargs):
        calls["review"] += 1
        Path(dest_path).write_bytes(b"clip")
        return dest_path

    def fake_run(cmd, **kwargs):
        calls["cmd"] = list(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(json.dumps({"ok": True, "mode": "live", "modelId": QWEN_OMNI_MODEL_ID, "parseOk": True}), encoding="utf-8")

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Proc()

    monkeypatch.setattr(worker_client, "extract_av_clip", fake_av)
    monkeypatch.setattr(worker_client, "extract_review_clip", fake_review)
    monkeypatch.setattr(worker_client.subprocess, "run", fake_run)
    monkeypatch.setattr(worker_client, "model_present", lambda *a, **k: True)

    payload = worker_client.run_av_perception(str(src), question="q", duration_sec=6.0)
    assert calls["av"] == 1 and calls["review"] == 0
    cmd = calls["cmd"]
    assert cmd[cmd.index("--model-id") + 1] == QWEN_OMNI_MODEL_ID
    assert cmd[cmd.index("--model-path") + 1].endswith("qwen2-5-omni-7b")
    assert ".avreview512." in cmd[cmd.index("--video") + 1]
    assert payload["modelId"] == QWEN_OMNI_MODEL_ID


def test_worker_qwen_branch_static_guard():
    """C1 regression guard: use_audio_in_video=True must stay in ALL THREE
    places (process_mm_info, processor, generate) plus return_audio=False."""
    source = (Path(worker_client.__file__).with_name("worker.py")).read_text(encoding="utf-8")
    assert "_live_infer_qwen_omni" in source
    assert source.count("use_audio_in_video=True") >= 3
    assert "return_audio=False" in source
    assert "Qwen2_5OmniForConditionalGeneration" in source
    assert "CPU_ONLY_TORCH" in source


# ── C2 / C3 packet compilation ───────────────────────────────────────────────


def _qwen_payload() -> dict:
    return {
        "ok": True,
        "mode": "live",
        "modelId": QWEN_OMNI_MODEL_ID,
        "parseOk": True,
        "rawText": '{"summary": "x"}',
        "summary": "A tester walks left while a tone beeps and a voice says hello.",
        "visualEvents": [
            {"startTime": 0.0, "endTime": 2.0, "label": "walk", "detail": "subject walks left", "phase": "early", "confidence": 0.9}
        ],
        "audioEvents": [
            {"startTime": 1.0, "endTime": 3.0, "eventType": "beep", "intensity": 0.5, "material": "sine",
             "context": "test tone", "presentInAudio": True, "confidence": 0.95}
        ],
        "speechSegments": [
            {"startTime": 0.5, "endTime": 2.5, "speaker": "narrator", "transcription": "hello adept",
             "isSilence": False, "overlap": False, "confidence": 0.9}
        ],
        "motionEvents": [
            {"startTime": 0.0, "endTime": 2.0, "subject": "character", "motionType": "walk", "direction": "left",
             "velocity": "slow", "confidence": 0.8}
        ],
        "characterActions": [
            {"startTime": 0.0, "endTime": 2.0, "characterLabel": "tester", "action": "walk",
             "actionCompletion": 0.8, "movementDirection": "left", "confidence": 0.85}
        ],
        "contactEvents": [
            {"startTime": 0.4, "endTime": 0.55, "characterLabel": "tester", "foot": "left",
             "surface": "concrete", "intensity": 0.6, "timingSource": "visible_contact", "confidence": 0.9},
            {"startTime": 0.95, "endTime": 1.1, "characterLabel": "tester", "foot": "right",
             "surface": "concrete", "intensity": 0.5, "timingSource": "visible_contact", "confidence": 0.88},
        ],
        "environmentEvents": [
            {"startTime": 0.0, "endTime": 6.0, "ambienceType": "room_tone",
             "description": "quiet studio room tone", "confidence": 0.7}
        ],
        "sceneChanges": [
            {"startTime": 3.0, "endTime": 3.1, "label": "cut", "detail": "hard cut to closer framing",
             "phase": "mid", "confidence": 0.75}
        ],
        "cameraMotion": [
            {"startTime": 0.0, "endTime": 6.0, "subject": "camera", "motionType": "dolly",
             "direction": "in", "velocity": "slow", "confidence": 0.8}
        ],
        "cueOpportunities": [
            {"startTime": 0.4, "endTime": 0.6, "kind": "footstep", "label": "left footstep",
             "suggestedQuery": "footstep on concrete", "presentInAudio": False,
             "characterLabel": "tester", "confidence": 0.9}
        ],
        "musicOpportunities": [
            {"startTime": 4.5, "endTime": 6.0, "role": "enter", "intensity": "low",
             "dialogueDensity": "sparse", "emotionalTone": "tense", "duckUnderDialogue": True,
             "confidence": 0.65}
        ],
        "confidence": 0.88,
        "ingestion": {"useAudioInVideo": True, "audioStreamCount": 1, "videoStreamCount": 1,
                      "audios": [{"shape": [96000], "dtype": "float32"}], "videos": [{"shape": [12, 360, 640, 3]}]},
        "loadToInferSec": 42.0,
        "device": "NVIDIA GeForce RTX 5090",
        "vramUsedGb": 21.5,
        "attnImplementation": "sdpa",
    }


def _facts() -> MediaFacts:
    return MediaFacts(
        container="mov,mp4,m4a,3gp,3g2,mj2",
        videoCodec="h264",
        audioCodec="aac",
        width=640,
        height=360,
        fps=24.0,
        frameCount=144,
        durationSec=6.0,
        sampleRate=48000,
        channels=2,
        bitrate=500000,
        hasAudio=True,
    )


def test_c2_packet_populates_perceptual_fields_and_evidence():
    packet = media_analyze.build_packet_from_payload(
        project_id="p1",
        asset_id="a1",
        facts=_facts(),
        payload=_qwen_payload(),
        fingerprint=media_analyze.build_fingerprint("a1", "hash"),
    )
    assert packet.availability == "ready"
    assert "tone beeps" in packet.summary
    assert packet.visualEvents and packet.visualEvents[0].label == "walk"
    assert packet.audioEvents and packet.audioEvents[0].eventType == "beep"
    assert packet.audioEvents[0].presentInAudio is True
    assert packet.speechSegments and packet.speechSegments[0].transcription == "hello adept"
    assert packet.motionEvents and packet.motionEvents[0].motionType == "walk"
    ev = packet.modelEvidence.qwenOmni
    assert ev.invoked is True and ev.parseOk is True
    assert ev.modelId == QWEN_OMNI_MODEL_ID
    assert ev.device == "NVIDIA GeForce RTX 5090"
    assert ev.vramUsedGb == 21.5
    assert packet.extras["qwenIngestion"]["audioStreamCount"] == 1
    assert packet.extras["qwenIngestion"]["useAudioInVideo"] is True


def test_c3_deterministic_facts_come_from_probe_not_vlm():
    """The VLM payload claims contradictory media facts; none may leak."""
    payload = _qwen_payload()
    payload["media"] = {"videoCodec": "vlm-invented-codec", "sampleRate": 99999, "frameCount": 7}
    payload["videoCodec"] = "vlm-invented-codec"
    payload["sampleRate"] = 99999
    payload["rawText"] = '{"summary": "x", "videoCodec": "vlm-invented-codec", "colorspace": {"colorSpace": "vlm"}}'
    facts = _facts()
    packet = media_analyze.build_packet_from_payload(
        project_id="p1",
        asset_id="a1",
        facts=facts,
        payload=payload,
        fingerprint=media_analyze.build_fingerprint("a1", "hash"),
    )
    assert packet.media.model_dump() == facts.model_dump()
    assert packet.media.videoCodec == "h264"
    assert packet.media.sampleRate == 48000
    assert packet.media.frameCount == 144
    assert packet.media.colorspace.colorSpace == "unknown"
    # The VLM text is retained as EVIDENCE, never as fact.
    assert "vlm-invented-codec" in packet.modelEvidence.qwenOmni.rawText


def test_coerce_event_list_salvages_bad_literals_and_numbers():
    items = [
        {"startTime": "1.5", "endTime": 2.0, "label": "turn", "phase": "beginning", "confidence": "high"},
        "not-a-dict",
        {"label": "ok", "phase": "mid"},
    ]
    from app.codirector.video_intelligence.media_packet import VisualEvent

    out = media_analyze._coerce_event_list(items, VisualEvent)
    assert len(out) == 2
    assert out[0].phase == "unknown"  # invalid Literal salvaged to default
    assert out[0].startTime == 1.5
    assert out[0].confidence is None  # unparseable number dropped
    assert out[1].label == "ok" and out[1].phase == "mid"


def test_c2_packet_populates_timeline_perceptual_fields():
    """Timeline Media Intelligence mapping: the Qwen payload populates
    contactEvents / characterActions / environmentEvents / sceneChanges /
    cameraMotion / cueOpportunities / musicOpportunities on the frozen packet."""
    packet = media_analyze.build_packet_from_payload(
        project_id="p1",
        asset_id="a1",
        facts=_facts(),
        payload=_qwen_payload(),
        fingerprint=media_analyze.build_fingerprint("a1", "hash"),
    )
    assert packet.availability == "ready"
    # Contact events keep foot/surface/timingSource (contact-first SFX timing).
    assert len(packet.contactEvents) == 2
    contact = packet.contactEvents[0]
    assert contact.foot == "left" and contact.surface == "concrete"
    assert contact.timingSource == "visible_contact"
    assert contact.startTime == 0.4 and contact.intensity == 0.6
    # Character actions.
    assert packet.characterActions[0].action == "walk"
    assert packet.characterActions[0].actionCompletion == 0.8
    assert packet.characterActions[0].movementDirection == "left"
    # Ambience beds.
    assert packet.environmentEvents[0].ambienceType == "room_tone"
    assert packet.environmentEvents[0].endTime == 6.0
    # Scene changes + camera motion ride the VisualEvent/MotionEvent models.
    assert packet.sceneChanges[0].label == "cut"
    assert packet.sceneChanges[0].phase == "mid"
    assert packet.cameraMotion[0].subject == "camera"
    assert packet.cameraMotion[0].motionType == "dolly"
    # Cue + music opportunities (Co-Director decides placement; Qwen only suggests).
    cue = packet.cueOpportunities[0]
    assert cue.kind == "footstep"
    assert cue.suggestedQuery == "footstep on concrete"
    assert cue.presentInAudio is False
    music = packet.musicOpportunities[0]
    assert music.role == "enter"
    assert music.duckUnderDialogue is True
    assert music.emotionalTone == "tense"


def test_coerce_contact_events_no_object_object_no_silent_drop():
    """A JS-stringified field ("[object Object]") or a nested junk value must
    never kill the whole contact event, and never reach the packet."""
    payload = _qwen_payload()
    payload["contactEvents"] = [
        {"startTime": 0.4, "endTime": 0.55, "characterLabel": "tester", "foot": "left",
         "surface": "[object Object]", "intensity": {"value": 0.6}, "confidence": 0.9},
        {"startTime": 1.0, "characterLabel": "tester", "foot": "right", "surface": "wood"},
    ]
    packet = media_analyze.build_packet_from_payload(
        project_id="p1",
        asset_id="a1",
        facts=_facts(),
        payload=payload,
        fingerprint=media_analyze.build_fingerprint("a1", "hash"),
    )
    assert len(packet.contactEvents) == 2, "contactEvents must never be silently dropped"
    assert packet.contactEvents[0].surface is None  # "[object Object]" field dropped
    assert packet.contactEvents[0].intensity is None  # nested junk dropped
    assert packet.contactEvents[0].foot == "left"  # real fields survive
    assert packet.contactEvents[1].surface == "wood"
    assert "[object Object]" not in packet.model_dump_json()


def test_coerce_event_list_salvages_bad_literals_on_new_models():
    """Invalid Literals on the new event models salvage to model defaults."""
    from app.codirector.video_intelligence.media_packet import (
        ContactEvent,
        CueOpportunity,
        MusicOpportunity,
    )

    contacts = media_analyze._coerce_event_list(
        [{"startTime": 0.1, "foot": "third", "timingSource": "guessed"}], ContactEvent
    )
    assert contacts[0].foot == "unknown"
    assert contacts[0].timingSource == "visible_contact"
    cues = media_analyze._coerce_event_list([{"startTime": 0.1, "kind": "laser"}], CueOpportunity)
    assert cues[0].kind == "other"
    music = media_analyze._coerce_event_list([{"startTime": 0.1, "role": "explosion"}], MusicOpportunity)
    assert music[0].role == "bed"


def test_worker_qwen_payload_forwards_timeline_keys_static_guard():
    """Silent-drop guard: _live_infer_qwen_omni must forward the Timeline
    Media Intelligence keys from the model JSON into the worker payload —
    otherwise ANALYZE_QUESTION's new keys would die between worker and packet."""
    source = (Path(worker_client.__file__).with_name("worker.py")).read_text(encoding="utf-8")
    for key in (
        "characterActions",
        "contactEvents",
        "environmentEvents",
        "sceneChanges",
        "cameraMotion",
        "cueOpportunities",
        "musicOpportunities",
    ):
        assert f'"{key}": _as_dict_list(parsed.get("{key}"))' in source, key


def test_run_av_perception_passes_window_to_av_extract(monkeypatch, tmp_path):
    """The analysis window reaches the audio-RETAINING extract unchanged."""
    src = tmp_path / "shot.mp4"
    src.write_bytes(b"src")
    seen: dict = {}

    def fake_av(video_path, dest_path, **kwargs):
        seen.update(kwargs)
        Path(dest_path).write_bytes(b"clip")
        return dest_path

    def fake_run(cmd, **kwargs):
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(
            json.dumps({"ok": True, "mode": "live", "modelId": QWEN_OMNI_MODEL_ID, "parseOk": True}),
            encoding="utf-8",
        )

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Proc()

    monkeypatch.setattr(worker_client, "extract_av_clip", fake_av)
    monkeypatch.setattr(worker_client.subprocess, "run", fake_run)
    monkeypatch.setattr(worker_client, "model_present", lambda *a, **k: True)
    worker_client.run_av_perception(str(src), question="q", start_sec=2.0, duration_sec=12.0)
    assert seen["start_sec"] == 2.0
    assert seen["duration_sec"] == 12.0


# ── analyze_asset GPU admission + persistence ────────────────────────────────


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    session.add(Project(id="proj-mi", name="Media Intelligence Test"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _asset(db: Session, tmp_path: Path) -> str:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-a-real-mp4")  # probe_media degrades to zeroed facts
    asset_id = uuid.uuid4().hex
    db.add(Asset(id=asset_id, project_id="proj-mi", kind="video", filename="clip.mp4", path=str(video)))
    db.commit()
    return asset_id


def test_analyze_asset_blocks_when_generation_active(db, tmp_path, monkeypatch):
    asset_id = _asset(db, tmp_path)
    monkeypatch.setattr(media_analyze, "comfy_generation_active", lambda: {"active": True, "running": 1, "pending": 0})

    def _boom(*a, **k):
        raise AssertionError("model must never load while a generation is active")

    monkeypatch.setattr(media_analyze, "run_av_perception", _boom)
    packet = media_analyze.analyze_asset(db, "proj-mi", asset_id)
    assert packet.availability == "unavailable"
    assert packet.reason == "GENERATION_ACTIVE"
    assert packet.modelEvidence.qwenOmni.invoked is False
    assert load_packet(db, "proj-mi", asset_id).reason == "GENERATION_ACTIVE"


def test_analyze_asset_blocks_on_insufficient_vram(db, tmp_path, monkeypatch):
    asset_id = _asset(db, tmp_path)
    monkeypatch.setattr(media_analyze, "comfy_generation_active", lambda: {"active": False, "running": 0, "pending": 0})
    monkeypatch.setattr(media_analyze, "best_effort_free_generator", lambda: {"comfyFreeRequested": True})
    monkeypatch.setattr(
        media_analyze,
        "preflight_for_review",
        lambda *, min_gb: {"ok": False, "freeVramGb": 4.2, "reason": "INSUFFICIENT_VRAM", "minGb": min_gb},
    )
    packet = media_analyze.analyze_asset(db, "proj-mi", asset_id)
    assert packet.availability == "unavailable"
    assert packet.reason == "INSUFFICIENT_VRAM"
    assert packet.extras["gpuPreflight"]["minGb"] == media_analyze.MIN_QWEN_OMNI_VRAM_GB


def test_analyze_asset_success_probe_facts_plus_qwen_perception(db, tmp_path, monkeypatch):
    asset_id = _asset(db, tmp_path)
    monkeypatch.setattr(media_analyze, "comfy_generation_active", lambda: {"active": False, "running": 0, "pending": 0})
    monkeypatch.setattr(media_analyze, "best_effort_free_generator", lambda: {"comfyFreeRequested": True})
    monkeypatch.setattr(
        media_analyze, "preflight_for_review", lambda *, min_gb: {"ok": True, "freeVramGb": 31.0, "reason": None}
    )
    calls = {"n": 0}

    def fake_perception(video_path, **kwargs):
        calls["n"] += 1
        return _qwen_payload()

    monkeypatch.setattr(media_analyze, "run_av_perception", fake_perception)
    packet = media_analyze.analyze_asset(db, "proj-mi", asset_id)
    assert packet.availability == "ready"
    assert calls["n"] == 1
    # C3 at the wiring level: junk file -> probe degrades to zeroed facts; the
    # VLM payload's codec claims must not leak.
    assert packet.media.videoCodec == ""
    assert packet.media.hasAudio is False
    assert packet.summary.startswith("A tester walks left")
    # Persistence + cache: second call returns the cached packet, no re-run.
    again = media_analyze.analyze_asset(db, "proj-mi", asset_id)
    assert calls["n"] == 1
    assert again.packetId == packet.packetId
    loaded = load_packet(db, "proj-mi", asset_id)
    assert loaded is not None and loaded.summary == packet.summary


def test_analyze_asset_missing_source_is_explicit(db):
    packet = media_analyze.analyze_asset(db, "proj-mi", "no-such-asset")
    assert packet.availability == "unavailable"
    assert packet.reason == "SOURCE_VIDEO_MISSING"


# ── analyze_asset analysis window + TimelineAnalysisContext ─────────────────


def _gpu_open(monkeypatch):
    """GPU admission mocked open (no :8188 contact, no real VRAM probe)."""
    monkeypatch.setattr(
        media_analyze, "comfy_generation_active", lambda: {"active": False, "running": 0, "pending": 0}
    )
    monkeypatch.setattr(media_analyze, "best_effort_free_generator", lambda: {"comfyFreeRequested": True})
    monkeypatch.setattr(
        media_analyze,
        "preflight_for_review",
        lambda *, min_gb: {"ok": True, "freeVramGb": 31.0, "reason": None},
    )


def _probed_facts(monkeypatch, duration_sec: float) -> None:
    facts = _facts()
    facts.durationSec = duration_sec
    monkeypatch.setattr(media_analyze, "probe_media", lambda path: facts)


def test_analyze_asset_defaults_to_full_probed_duration(db, tmp_path, monkeypatch):
    """No silent 6s cap: with no explicit duration/range, the analysis window
    is the FULL probed clip (facts.durationSec = 12 -> duration_sec == 12)."""
    asset_id = _asset(db, tmp_path)
    _gpu_open(monkeypatch)
    _probed_facts(monkeypatch, 12.0)
    calls: dict = {}

    def fake_perception(video_path, **kwargs):
        calls.update(kwargs)
        return _qwen_payload()

    monkeypatch.setattr(media_analyze, "run_av_perception", fake_perception)
    packet = media_analyze.analyze_asset(db, "proj-mi", asset_id)
    assert packet.availability == "ready"
    assert calls["duration_sec"] == 12.0, "full probed duration, not the old 6s cap"
    assert calls["start_sec"] == 0.0
    assert packet.extras["analysisWindow"] == {
        "startSec": 0.0,
        "durationSec": 12.0,
        "source": "probeFullDuration",
    }
    # AV ingestion evidence still lands on the packet (C1).
    assert packet.extras["qwenIngestion"]["useAudioInVideo"] is True
    assert packet.extras["qwenIngestion"]["audioStreamCount"] == 1
    # No Timeline kwargs -> no context attached.
    assert packet.timelineContext is None


def test_analyze_asset_timeline_range_window_overrides_full_duration(db, tmp_path, monkeypatch):
    """Timeline range kwargs narrow the window: range 2s..7s on a 12s clip ->
    start_sec=2, duration_sec=5 (not the full 12, not a 6s cap)."""
    asset_id = _asset(db, tmp_path)
    _gpu_open(monkeypatch)
    _probed_facts(monkeypatch, 12.0)
    calls: dict = {}

    def fake_perception(video_path, **kwargs):
        calls.update(kwargs)
        return _qwen_payload()

    monkeypatch.setattr(media_analyze, "run_av_perception", fake_perception)
    packet = media_analyze.analyze_asset(
        db, "proj-mi", asset_id, range_start_sec=2.0, range_end_sec=7.0
    )
    assert calls["start_sec"] == 2.0
    assert calls["duration_sec"] == 5.0
    assert packet.extras["analysisWindow"]["source"] == "timelineRange"


def test_analyze_asset_explicit_duration_still_honored(db, tmp_path, monkeypatch):
    """An explicit duration_sec override beats the probe (legacy callers)."""
    asset_id = _asset(db, tmp_path)
    _gpu_open(monkeypatch)
    _probed_facts(monkeypatch, 12.0)
    calls: dict = {}

    def fake_perception(video_path, **kwargs):
        calls.update(kwargs)
        return _qwen_payload()

    monkeypatch.setattr(media_analyze, "run_av_perception", fake_perception)
    packet = media_analyze.analyze_asset(db, "proj-mi", asset_id, duration_sec=4.0)
    assert calls["duration_sec"] == 4.0
    assert packet.extras["analysisWindow"]["source"] == "explicit"


def test_analyze_asset_attaches_timeline_context_and_persists(db, tmp_path, monkeypatch):
    """scene_id / range / playhead kwargs attach a TimelineAnalysisContext;
    a cache hit with a moved playhead refreshes it without re-inference."""
    asset_id = _asset(db, tmp_path)
    _gpu_open(monkeypatch)
    monkeypatch.setattr(media_analyze, "run_av_perception", lambda *a, **k: _qwen_payload())
    packet = media_analyze.analyze_asset(
        db,
        "proj-mi",
        asset_id,
        scene_id="scene-1",
        execution_id="exec-9",
        range_start_sec=1.0,
        range_end_sec=4.0,
        playhead_sec=2.5,
    )
    ctx = packet.timelineContext
    assert ctx is not None
    assert ctx.projectId == "proj-mi"
    assert ctx.sceneId == "scene-1"
    assert ctx.clipAssetId == asset_id
    assert ctx.executionId == "exec-9"
    assert ctx.rangeStartSec == 1.0 and ctx.rangeEndSec == 4.0
    assert ctx.playheadSec == 2.5
    # Persisted: reload returns the same context.
    loaded = load_packet(db, "proj-mi", asset_id)
    assert loaded is not None and loaded.timelineContext is not None
    assert loaded.timelineContext.sceneId == "scene-1"
    assert loaded.timelineContext.playheadSec == 2.5
    # Cache hit with a moved playhead: no re-inference, context refreshed + saved.
    calls = {"n": 0}

    def _counting(*a, **k):
        calls["n"] += 1
        return _qwen_payload()

    monkeypatch.setattr(media_analyze, "run_av_perception", _counting)
    again = media_analyze.analyze_asset(db, "proj-mi", asset_id, scene_id="scene-1", playhead_sec=5.0)
    assert calls["n"] == 0
    assert again.packetId == packet.packetId
    assert again.timelineContext is not None
    assert again.timelineContext.playheadSec == 5.0
    assert again.timelineContext.rangeEndSec is None  # latest-request-wins
    reloaded = load_packet(db, "proj-mi", asset_id)
    assert reloaded is not None and reloaded.timelineContext is not None
    assert reloaded.timelineContext.playheadSec == 5.0


def test_analyze_asset_unavailable_still_carries_timeline_context(db, tmp_path, monkeypatch):
    """GPU-admission degrade keeps the Timeline context — the Timeline knows
    WHICH scene/range was refused, not just that it was refused."""
    asset_id = _asset(db, tmp_path)
    monkeypatch.setattr(
        media_analyze, "comfy_generation_active", lambda: {"active": True, "running": 1, "pending": 0}
    )
    packet = media_analyze.analyze_asset(
        db, "proj-mi", asset_id, scene_id="scene-2", range_start_sec=0.0, range_end_sec=3.0
    )
    assert packet.availability == "unavailable"
    assert packet.reason == "GENERATION_ACTIVE"
    assert packet.timelineContext is not None
    assert packet.timelineContext.sceneId == "scene-2"
    assert packet.timelineContext.rangeEndSec == 3.0


# ── CREATE inspection service: router + diagnose path (additive) ────────────
# Added by the CREATE inspection mission (inspection_report + media_router).
# Phase C tests above are untouched. No GPU, no ComfyUI contact: GPU admission
# is monkeypatched open and run_av_perception is mocked.

import shutil  # noqa: E402
import subprocess  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings as _settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.codirector.video_intelligence import media_router  # noqa: E402
from app.codirector.video_intelligence.inspection_report import (  # noqa: E402
    DIAGNOSTIC_VERSION,
    PERCEPTION_UNAVAILABLE_REASON,
)


def _ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"))


def _make_clean_mp4(path: Path) -> None:
    """testsrc video + 0.5-amplitude stereo sine (peaks clear of the clip rail)."""
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=1",
        "-f", "lavfi", "-i", "aevalsrc=sin(2*PI*440*t)|sin(2*PI*440*t):s=48000:d=1",
        "-af", "volume=0.5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-movflags", "+faststart", str(path),
    ], check=True, capture_output=True, timeout=120)


def _make_distorted_mov(path: Path) -> None:
    """testsrc video + 3x-overdriven sine into pcm_s16le -> hard-clipped rails
    (~78% of samples pinned). Deterministic across ffmpeg builds."""
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=1",
        "-f", "lavfi", "-i", "aevalsrc=sin(2*PI*440*t)|sin(2*PI*440*t):s=48000:d=1",
        "-af", "volume=3.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "pcm_s16le", "-movflags", "+faststart", str(path),
    ], check=True, capture_output=True, timeout=120)


def _route_asset(db: Session, project_id: str, path: Path) -> str:
    """Register a real file as an asset of a UUID project (the resolver
    requires canonical UUID ids and an in-data_dir path)."""
    asset_id = str(uuid.uuid4())
    db.add(Asset(id=asset_id, project_id=project_id, kind="video", filename=path.name, path=str(path)))
    db.commit()
    return asset_id


@pytest.fixture()
def route_client(db: Session, tmp_path: Path, monkeypatch):
    """TestClient over ONLY the media-intelligence router (mounted exactly like
    production: /api/codirector). GPU admission is mocked open (no :8188
    contact); run_av_perception is a counting fake; settings.data_dir is
    redirected to tmp_path so asset resolution stays in scope."""
    if not _ffmpeg_available():
        pytest.skip("ffmpeg not available on PATH")
    monkeypatch.setattr(_settings, "data_dir", tmp_path)
    project_id = str(uuid.uuid4())
    db.add(Project(id=project_id, name="CREATE Inspection Route Test"))
    db.commit()
    monkeypatch.setattr(
        media_analyze, "comfy_generation_active", lambda: {"active": False, "running": 0, "pending": 0}
    )
    monkeypatch.setattr(media_analyze, "best_effort_free_generator", lambda: {"comfyFreeRequested": False})
    monkeypatch.setattr(
        media_analyze,
        "preflight_for_review",
        lambda *, min_gb: {"ok": True, "freeVramGb": 31.0, "reason": None},
    )
    calls = {"n": 0}

    def fake_perception(video_path, **kwargs):
        calls["n"] += 1
        return _qwen_payload()

    monkeypatch.setattr(media_analyze, "run_av_perception", fake_perception)

    app = FastAPI()
    app.include_router(media_router.router, prefix="/api/codirector")

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    return TestClient(app), project_id, calls


def test_route_analyze_returns_enriched_packet(route_client, db: Session, tmp_path: Path):
    client, project_id, calls = route_client
    video = tmp_path / "clean.mp4"
    _make_clean_mp4(video)
    asset_id = _route_asset(db, project_id, video)
    resp = client.post(
        "/api/codirector/media-intelligence/analyze",
        json={
            "projectId": project_id,
            "assetId": asset_id,
            "mode": "full",
            "createContext": {
                "surface": "one_frame",
                "prompt": "a test pattern",
                "referenceAssetIds": [],
                "referenceRoles": [],
                "adherenceNotes": [],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Deterministic facts from the probe (C3)...
    assert body["media"]["videoCodec"] == "h264"
    assert body["media"]["sampleRate"] == 48000
    # ...plus the deterministic diagnostics stage enrichment.
    assert body["diagnostics"]["video"]["codec"] == "h264"
    assert body["diagnostics"]["audio"]["sampleRate"] == 48000
    assert body["diagnostics"]["audio"]["clippingFraction"] == 0.0
    assert body["extras"]["deterministicDiagnostics"]["version"] == DIAGNOSTIC_VERSION
    # CREATE surface context echoed onto the packet.
    assert body["createContext"]["surface"] == "one_frame"
    # Perception (mocked) ran once and compiled perceptual fields.
    assert body["availability"] == "ready"
    assert body["summary"].startswith("A tester walks left")
    assert calls["n"] == 1


def test_route_analyze_with_reference_measures_gamma(route_client, db: Session, tmp_path: Path):
    client, project_id, _calls = route_client
    video = tmp_path / "clean.mp4"
    _make_clean_mp4(video)
    reference = tmp_path / "reference.mp4"
    _make_clean_mp4(reference)
    asset_id = _route_asset(db, project_id, video)
    ref_id = _route_asset(db, project_id, reference)
    resp = client.post(
        "/api/codirector/media-intelligence/analyze",
        json={
            "projectId": project_id,
            "assetId": asset_id,
            "mode": "full",
            "createContext": {
                "surface": "one_frame",
                "referenceAssetIds": [ref_id],
                "referenceRoles": ["source"],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    gamma = body["diagnostics"]["video"]["color"]["gammaShiftEstimate"]
    assert gamma is not None
    assert 0.8 <= gamma <= 1.25, "identical generative params -> no color shift"
    assert body["extras"]["deterministicDiagnostics"]["referenceUsed"] is True


def test_route_analyze_cache_hit_skips_perception_and_redecode(
    route_client, db: Session, tmp_path: Path, monkeypatch
):
    client, project_id, calls = route_client
    enrich_calls = {"n": 0}
    real_enrich = media_router.enrich_packet_diagnostics

    def counting_enrich(packet, video_path, **kwargs):
        enrich_calls["n"] += 1
        return real_enrich(packet, video_path, **kwargs)

    monkeypatch.setattr(media_router, "enrich_packet_diagnostics", counting_enrich)
    video = tmp_path / "clean.mp4"
    _make_clean_mp4(video)
    asset_id = _route_asset(db, project_id, video)
    payload = {"projectId": project_id, "assetId": asset_id, "mode": "full"}
    first = client.post("/api/codirector/media-intelligence/analyze", json=payload)
    assert first.status_code == 200, first.text
    second = client.post("/api/codirector/media-intelligence/analyze", json=payload)
    assert second.status_code == 200, second.text
    assert calls["n"] == 1, "fresh fingerprint -> cached packet, no re-inference"
    assert enrich_calls["n"] == 1, "diagnostics marker -> no ffmpeg re-decode on cache hit"
    assert second.json()["packetId"] == first.json()["packetId"]


def test_route_analyze_surface_only_synthesizes_context(route_client, db: Session, tmp_path: Path):
    client, project_id, _calls = route_client
    video = tmp_path / "clean.mp4"
    _make_clean_mp4(video)
    asset_id = _route_asset(db, project_id, video)
    resp = client.post(
        "/api/codirector/media-intelligence/analyze",
        json={"projectId": project_id, "assetId": asset_id, "surface": "three_frame"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["createContext"]["surface"] == "three_frame"


def test_route_analyze_wrong_project_is_403(route_client, db: Session, tmp_path: Path):
    client, project_id, _calls = route_client
    video = tmp_path / "clean.mp4"
    _make_clean_mp4(video)
    asset_id = _route_asset(db, project_id, video)
    other_project = str(uuid.uuid4())
    db.add(Project(id=other_project, name="Other Project"))
    db.commit()
    resp = client.post(
        "/api/codirector/media-intelligence/analyze",
        json={"projectId": other_project, "assetId": asset_id},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "ASSET_PROJECT_MISMATCH"


def test_route_packet_get_and_404(route_client, db: Session, tmp_path: Path):
    client, project_id, _calls = route_client
    video = tmp_path / "clean.mp4"
    _make_clean_mp4(video)
    asset_id = _route_asset(db, project_id, video)
    created = client.post(
        "/api/codirector/media-intelligence/analyze",
        json={"projectId": project_id, "assetId": asset_id},
    )
    assert created.status_code == 200, created.text
    resp = client.get(
        "/api/codirector/media-intelligence/packet",
        params={"projectId": project_id, "assetId": asset_id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["packetId"] == created.json()["packetId"]
    missing = client.get(
        "/api/codirector/media-intelligence/packet",
        params={"projectId": project_id, "assetId": str(uuid.uuid4())},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "PACKET_NOT_FOUND"


def test_route_diagnose_distorted_inspection_pass_quality_fail(route_client, db: Session, tmp_path: Path):
    """The mandatory distinction, end to end through the route: a detected
    defect is inspection PASS + generated-media-quality FAIL."""
    client, project_id, _calls = route_client
    video = tmp_path / "distorted.mov"
    _make_distorted_mov(video)
    asset_id = _route_asset(db, project_id, video)
    resp = client.post(
        "/api/codirector/media-intelligence/diagnose",
        json={"projectId": project_id, "assetId": asset_id},
    )
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["mode"] == "diagnose"
    assert report["inspection"] == "PASS"
    assert report["generatedMediaQuality"] == "FAIL"
    assert report["firstSuspectBoundary"] == "asset-decode"
    assert report["audio"]["verdict"] == "FAIL"
    assert report["audio"]["clippingFraction"] > 0.3


def test_route_diagnose_qwen_unavailable_degrades_honestly(
    route_client, db: Session, tmp_path: Path, monkeypatch
):
    """Qwen-unavailable failure policy through the route: deterministic
    diagnostics completed, perception did not -> DEGRADED, never an AV PASS."""

    def _boom(*args, **kwargs):
        raise RuntimeError("MODEL_NOT_INSTALLED")

    monkeypatch.setattr(media_analyze, "run_av_perception", _boom)
    client, project_id, _calls = route_client
    video = tmp_path / "clean.mp4"
    _make_clean_mp4(video)
    asset_id = _route_asset(db, project_id, video)
    resp = client.post(
        "/api/codirector/media-intelligence/diagnose",
        json={"projectId": project_id, "assetId": asset_id},
    )
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["availability"] == "unavailable"  # Phase C packet semantics preserved
    assert report["inspection"] == "DEGRADED"
    assert report["generatedMediaQuality"] == "PASS"  # clean asset, measured
    assert PERCEPTION_UNAVAILABLE_REASON in report["perceptualEvidence"]
    assert "qwenOmni.invoked=False" in report["perceptualEvidence"]


def test_route_status_reports_model_availability(route_client):
    client, _project_id, _calls = route_client
    resp = client.get("/api/codirector/media-intelligence/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["models"]["qwenOmni"]["modelId"] == QWEN_OMNI_MODEL_ID
    assert isinstance(body["models"]["qwenOmni"]["installed"], bool)
    assert isinstance(body["models"]["videoChat3"]["installed"], bool)
    assert body["deterministicDiagnostics"]["ffmpeg"] is True
    assert body["deterministicDiagnostics"]["ffprobe"] is True
    assert body["analysisVersion"]


def test_diagnose_asset_alias_uses_same_canonical_authority(db, tmp_path, monkeypatch):
    """diagnose_asset is a thin alias: analyze_asset(..., mode='diagnose')."""
    asset_id = _asset(db, tmp_path)
    monkeypatch.setattr(
        media_analyze, "comfy_generation_active", lambda: {"active": False, "running": 0, "pending": 0}
    )
    monkeypatch.setattr(media_analyze, "best_effort_free_generator", lambda: {"comfyFreeRequested": True})
    monkeypatch.setattr(
        media_analyze,
        "preflight_for_review",
        lambda *, min_gb: {"ok": True, "freeVramGb": 31.0, "reason": None},
    )
    calls = {"n": 0}

    def fake_perception(video_path, **kwargs):
        calls["n"] += 1
        return _qwen_payload()

    monkeypatch.setattr(media_analyze, "run_av_perception", fake_perception)
    packet = media_analyze.diagnose_asset(db, "proj-mi", asset_id)
    assert packet.mode == "diagnose"
    assert packet.availability == "ready"
    assert calls["n"] == 1
    # Same cache authority as analyze_asset: second call is a cache hit.
    again = media_analyze.diagnose_asset(db, "proj-mi", asset_id)
    assert calls["n"] == 1
    assert again.packetId == packet.packetId
