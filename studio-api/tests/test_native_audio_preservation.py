"""Regression tests for Native Audio Authority and preservation.

These tests verify that:
- trim_video_to_seconds preserves audio (uses -c:a copy)
- validate_video_output checks for audio streams (AUDIO_STREAM_PRESENT)
- Audio authority contract: no explicit track = generator-native
- Audio authority contract: explicit Timeline audio = Timeline authority
- Audio authority contract: lip sync = Timeline dialogue authority
- MiniMax H3 adapter declares audio_generation=True
- H3_REF2V_STEPS is 20 (not 8) for clean native audio
- register_native_audio_provenance produces correct provenance
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# H3_REF2V_STEPS — must be 20 for clean native audio
# ---------------------------------------------------------------------------


def test_h3_ref2v_steps_is_20():
    """H3_REF2V_STEPS must be 20 for clean native audio (root cause doc)."""
    from app.workflows.h3_ref2v_builder import H3_REF2V_STEPS

    assert H3_REF2V_STEPS == 20, f"Expected 20 steps for clean audio, got {H3_REF2V_STEPS}"


def test_h3_ref2v_builder_accepts_steps_param():
    """build_h3_ref2v should accept a steps parameter."""
    from app.workflows.h3_ref2v_builder import build_h3_ref2v

    wf = build_h3_ref2v(
        prompt="test",
        ref_comfy_names=["img1.png"],
        filename_prefix="test",
        seed=42,
        steps=20,
    )
    # Find the BasicScheduler node and check steps
    for node_id, node in wf.items():
        if isinstance(node, dict) and node.get("class_type") == "BasicScheduler":
            assert node["inputs"]["steps"] == 20
            return
    pytest.fail("BasicScheduler node not found in workflow")


# ---------------------------------------------------------------------------
# MiniMax H3 adapter — audio_generation must be True
# ---------------------------------------------------------------------------


def test_minimax_h3_local_audio_generation():
    """MiniMax H3 Local adapter must declare audio_generation=True."""
    from app.director_timeline_w46.generation.adapters.minimax_h3_local import _capabilities

    caps = _capabilities()
    assert caps.audio_generation is True, "MiniMax H3 Local must declare audio_generation=True"
    assert caps.qualityControl == "h3_megapixels"


def test_minimax_h3_local_audio_metadata():
    """MiniMax H3 Local adapter must declare native synchronized audio."""
    from app.director_timeline_w46.generation.adapters.minimax_h3_local import _capabilities

    caps = _capabilities()
    audio = caps.audio or {}
    assert audio.get("generation") is True
    assert audio.get("synchronized") is True
    assert audio.get("native") is True


def test_minimax_h3_i2v_local_audio_generation():
    """MiniMax H3 I2V Local adapter must declare audio_generation=True."""
    from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import _capabilities

    caps = _capabilities()
    assert caps.audio_generation is True, "MiniMax H3 I2V Local must declare audio_generation=True"
    assert caps.qualityControl == "h3_megapixels"


def test_ltx25_quality_control_and_audio_come_from_adapter():
    from app.director_timeline_w46.generation.adapters.ltx_25_local import _ltx25_capabilities
    from app.director_timeline_w46.generation.registry import get_registry

    caps = _ltx25_capabilities()
    assert caps.qualityControl == "ltx_quality"
    assert caps.audio_generation is True
    live = get_registry().capabilities("ltx-2.5-distilled")
    assert live.qualityControl == "ltx_quality"
    h3 = get_registry().capabilities("minimax-h3")
    assert h3.qualityControl == "h3_megapixels"
    assert h3.audio_generation is True


# ---------------------------------------------------------------------------
# trim_video_to_seconds — must preserve audio
# ---------------------------------------------------------------------------


def test_trim_video_to_seconds_uses_copy_audio():
    """trim_video_to_seconds should use -c:a copy to preserve audio."""
    import inspect
    from app.media_clip import trim_video_to_seconds

    source = inspect.getsource(trim_video_to_seconds)
    assert "-c:a" in source, "trim must specify audio codec"
    assert "copy" in source, "trim must use -c:a copy to preserve audio"


def test_trim_video_to_seconds_has_aac_fallback():
    """trim_video_to_seconds should have an AAC fallback for incompatible codecs."""
    import inspect
    from app.media_clip import trim_video_to_seconds

    source = inspect.getsource(trim_video_to_seconds)
    assert "aac" in source, "trim must have AAC fallback for audio re-encoding"


# ---------------------------------------------------------------------------
# validate_video_output — must check audio stream
# ---------------------------------------------------------------------------


def test_output_gate_has_audio_stream_check():
    """OutputGateResult checks must include AUDIO_STREAM_PRESENT."""
    from app.video_runtime.output_gate import validate_video_output

    # We can verify the check key exists by inspecting the function
    import inspect

    source = inspect.getsource(validate_video_output)
    assert "AUDIO_STREAM_PRESENT" in source, "Output gate must check audio stream"


# ---------------------------------------------------------------------------
# Audio authority contract — _resolve_audio_authority
# ---------------------------------------------------------------------------


def test_audio_authority_no_explicit_tracks_generator_native():
    """No explicit Timeline audio → generator-native authority."""
    from app.director_timeline_w46.generation.request_builder import _resolve_audio_authority
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import VideoGeneratorCapabilities

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.audioClips = []
    batch.sfxClips = []

    caps = VideoGeneratorCapabilities(
        id="minimax-h3-local",
        label="MiniMax H3",
        aliases=[],
        audio_generation=True,
    )

    with patch("app.db.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_scene = MagicMock()
        mock_scene.lipsync_audio_asset_id = None
        mock_db.get.return_value = mock_scene

        result = _resolve_audio_authority("p1", "s1", batch, caps)

    assert result["authority"] == "generator_native"
    assert result["generateAudio"] is True


def test_audio_authority_explicit_audio_clips_timeline():
    """Explicit audio clips → Timeline authority."""
    from app.director_timeline_w46.generation.request_builder import _resolve_audio_authority
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import VideoGeneratorCapabilities

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.audioClips = [MagicMock()]
    batch.sfxClips = []

    caps = VideoGeneratorCapabilities(
        id="minimax-h3-local",
        label="MiniMax H3",
        aliases=[],
        audio_generation=True,
    )

    with patch("app.db.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_scene = MagicMock()
        mock_scene.lipsync_audio_asset_id = None
        mock_db.get.return_value = mock_scene

        result = _resolve_audio_authority("p1", "s1", batch, caps)

    assert result["authority"] == "timeline"
    assert result["generateAudio"] is False


def test_audio_authority_explicit_sfx_clips_timeline():
    """Explicit SFX clips → Timeline authority."""
    from app.director_timeline_w46.generation.request_builder import _resolve_audio_authority
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import VideoGeneratorCapabilities

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.audioClips = []
    batch.sfxClips = [MagicMock()]

    caps = VideoGeneratorCapabilities(
        id="minimax-h3-local",
        label="MiniMax H3",
        aliases=[],
        audio_generation=True,
    )

    with patch("app.db.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_scene = MagicMock()
        mock_scene.lipsync_audio_asset_id = None
        mock_db.get.return_value = mock_scene

        result = _resolve_audio_authority("p1", "s1", batch, caps)

    assert result["authority"] == "timeline"


def test_audio_authority_lip_sync_timeline():
    """Lip sync tracks → Timeline dialogue authority."""
    from app.director_timeline_w46.generation.request_builder import _resolve_audio_authority
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import VideoGeneratorCapabilities

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.audioClips = []
    batch.sfxClips = []

    caps = VideoGeneratorCapabilities(
        id="minimax-h3-local",
        label="MiniMax H3",
        aliases=[],
        audio_generation=True,
    )

    with patch("app.db.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_scene = MagicMock()
        mock_scene.lipsync_audio_asset_id = "audio-asset-id"
        mock_db.get.return_value = mock_scene

        result = _resolve_audio_authority("p1", "s1", batch, caps)

    assert result["authority"] == "timeline"
    assert result["dialogue"] == "lip_sync"


def test_audio_authority_generator_no_native_audio():
    """Generator without native audio → generateAudio=False."""
    from app.director_timeline_w46.generation.request_builder import _resolve_audio_authority
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import VideoGeneratorCapabilities

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.audioClips = []
    batch.sfxClips = []

    caps = VideoGeneratorCapabilities(
        id="ltx-25-local",
        label="LTX 2.5",
        aliases=[],
        audio_generation=False,
    )

    with patch("app.db.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_scene = MagicMock()
        mock_scene.lipsync_audio_asset_id = None
        mock_db.get.return_value = mock_scene

        result = _resolve_audio_authority("p1", "s1", batch, caps)

    assert result["authority"] == "generator_native"
    assert result["generateAudio"] is False
    assert result["nativeAudio"] == "unsupported"


# ---------------------------------------------------------------------------
# register_native_audio_provenance
# ---------------------------------------------------------------------------


def test_register_native_audio_provenance_with_audio():
    """register_native_audio_provenance should record audio metadata."""
    from app.minimax_h3.audio_import import register_native_audio_provenance

    audio_meta = {"channels": 2, "sampleRateHz": 32000}
    result = register_native_audio_provenance({}, audio_meta)
    audio = result.get("audio", {})
    assert audio.get("nativeStereoDetected") is True
    assert audio.get("channels") == 2
    assert audio.get("sampleRateHz") == 32000


def test_register_native_audio_provenance_without_audio():
    """register_native_audio_provenance should record absent audio."""
    from app.minimax_h3.audio_import import register_native_audio_provenance

    result = register_native_audio_provenance({}, {})
    audio = result.get("audio", {})
    assert audio.get("nativeStereoDetected") is False
    assert audio.get("channels") is None
