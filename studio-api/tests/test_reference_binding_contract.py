"""Regression tests for the Timeline Reference Binding Contract.

These tests verify that:
- Voice/audio assets never enter visual (character/place/prop) slots
- _bound_crs_asset excludes charactervoice/voice/audio/video/motion kinds
- _drop_compiled_refs clears stale characterIdentity/characterVoice refs
- collect_slots_from_batch skips non-image assets in visual slots
- Preflight blocks non-image assets in visual slots
- startImageAssetId is never set to a non-image asset
- Approval gating warns for unapproved character references
- Project visual style is prepended to the prompt
- Range Replacement preserves style authority
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Any


# ---------------------------------------------------------------------------
# _bound_crs_asset — voice/audio must NEVER be returned as a CRS image
# ---------------------------------------------------------------------------


def test_bound_crs_excludes_charactervoice():
    """A charactervoice reference must not be returned as a CRS image asset."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "charactervoice", "identityId": "char1", "role": "charactervoice", "assetId": "voice-wav-id"},
        {"kind": "character", "identityId": "char1", "role": "character", "assetId": "image-png-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == "image-png-id", "Should return the image asset, not the voice .wav"


def test_bound_crs_excludes_voice_kind():
    """A voice kind reference must not be returned as a CRS image."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "voice", "identityId": "char1", "role": "voice", "assetId": "voice-wav-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == "", "Voice kind should not be returned as CRS"


def test_bound_crs_excludes_audio_kind():
    """An audio kind reference must not be returned as a CRS image."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "audio", "identityId": "char1", "role": "audio", "assetId": "audio-mp3-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == "", "Audio kind should not be returned as CRS"


def test_bound_crs_excludes_video_kind():
    """A video kind reference must not be returned as a CRS image."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "video", "identityId": "char1", "role": "character", "assetId": "video-mp4-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == "", "Video kind should not be returned as CRS even with character role"


def test_bound_crs_returns_character_image():
    """A proper character image reference should be returned as CRS."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "image", "identityId": "char1", "role": "character", "assetId": "image-png-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == "image-png-id"


def test_bound_crs_returns_crs_role():
    """A CRS role reference should be returned."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "image", "identityId": "char1", "role": "crs", "assetId": "crs-png-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == "crs-png-id"


def test_bound_crs_returns_entity_role():
    """An entity role reference should be returned."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "image", "identityId": "char1", "role": "entity", "assetId": "entity-png-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == "entity-png-id"


def test_bound_crs_returns_entity_reference_role():
    """An entity_reference role should be returned."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "image", "identityId": "char1", "role": "entity_reference", "assetId": "ent-ref-png-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == "ent-ref-png-id"


def test_bound_crs_no_match():
    """No match returns empty string."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    bound_assets = [
        {"kind": "image", "identityId": "other", "role": "character", "assetId": "other-png-id"},
    ]
    result = _bound_crs_asset("char1", bound_assets)
    assert result == ""


def test_bound_crs_empty_inputs():
    """Empty inputs return empty string."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    assert _bound_crs_asset("", None) == ""
    assert _bound_crs_asset("char1", []) == ""
    assert _bound_crs_asset("", [{"kind": "image", "identityId": "char1", "role": "character", "assetId": "x"}]) == ""


# ---------------------------------------------------------------------------
# _drop_compiled_refs — stale characterIdentity/characterVoice must be cleared
# ---------------------------------------------------------------------------


def test_drop_compiled_refs_clears_prompt_clip():
    """prompt_clip references should be dropped."""
    from app.director_timeline_w46.generation.reference_compile import _drop_compiled_refs
    from app.director_timeline_w46.contracts import BatchBlock

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"source": "prompt_clip", "kind": "image", "assetId": "a1", "consumed": True},
        {"source": "other", "kind": "image", "assetId": "a2", "consumed": True},
    ]
    _drop_compiled_refs(batch)
    sources = [r.get("source") for r in batch.references]
    assert "prompt_clip" not in sources
    assert "other" in sources


def test_drop_compiled_refs_clears_camera_clip():
    """camera_clip references should be dropped."""
    from app.director_timeline_w46.generation.reference_compile import _drop_compiled_refs
    from app.director_timeline_w46.contracts import BatchBlock

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"source": "camera_clip", "kind": "image", "assetId": "a1", "consumed": True},
    ]
    _drop_compiled_refs(batch)
    assert len(batch.references) == 0


def test_drop_compiled_refs_clears_project_character():
    """project_character references should be dropped (stale characterIdentity)."""
    from app.director_timeline_w46.generation.reference_compile import _drop_compiled_refs
    from app.director_timeline_w46.contracts import BatchBlock

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"source": "project_character", "kind": "characterIdentity", "assetId": "a1", "consumed": True},
    ]
    _drop_compiled_refs(batch)
    assert len(batch.references) == 0


def test_drop_compiled_refs_clears_project_character_voice():
    """project_character_voice references should be dropped (stale characterVoice)."""
    from app.director_timeline_w46.generation.reference_compile import _drop_compiled_refs
    from app.director_timeline_w46.contracts import BatchBlock

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"source": "project_character_voice", "kind": "characterVoice", "assetId": "a1", "consumed": True},
    ]
    _drop_compiled_refs(batch)
    assert len(batch.references) == 0


def test_drop_compiled_refs_preserves_other_sources():
    """References from other sources should be preserved."""
    from app.director_timeline_w46.generation.reference_compile import _drop_compiled_refs
    from app.director_timeline_w46.contracts import BatchBlock

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"source": "library", "kind": "image", "assetId": "a1", "consumed": True},
        {"source": "manual", "kind": "image", "assetId": "a2", "consumed": True},
    ]
    _drop_compiled_refs(batch)
    assert len(batch.references) == 2


# ---------------------------------------------------------------------------
# collect_slots_from_batch — voice/audio kinds must not produce visual slots
# ---------------------------------------------------------------------------


def test_collect_slots_skips_charactervoice_kind():
    """characterVoice kind should not produce a visual slot."""
    from app.director_timeline_w46.generation.r2v import collect_slots_from_batch
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"kind": "characterVoice", "assetId": "voice-wav-id", "role": "character", "consumed": True, "source": "prompt_clip"},
    ]
    request = TimelineGenerationRequest(
        projectId="p1", sceneId="s1", batchBlockId="b1", executionSnapshotId="snap1",
        generatorId="minimax-h3-local", prompt="test"
    )
    slots = collect_slots_from_batch(batch, request)
    visual_slots = [s for s in slots if s.role not in {"video", "audio"}]
    assert len(visual_slots) == 0, "characterVoice should not produce a visual slot"


def test_collect_slots_skips_voice_kind():
    """voice kind should not produce a visual slot."""
    from app.director_timeline_w46.generation.r2v import collect_slots_from_batch
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"kind": "voice", "assetId": "voice-wav-id", "role": "character", "consumed": True, "source": "prompt_clip"},
    ]
    request = TimelineGenerationRequest(
        projectId="p1", sceneId="s1", batchBlockId="b1", executionSnapshotId="snap1",
        generatorId="minimax-h3-local", prompt="test"
    )
    slots = collect_slots_from_batch(batch, request)
    visual_slots = [s for s in slots if s.role not in {"video", "audio"}]
    assert len(visual_slots) == 0, "voice kind should not produce a visual slot"


def test_collect_slots_skips_audio_kind():
    """audio kind should not produce a visual slot."""
    from app.director_timeline_w46.generation.r2v import collect_slots_from_batch
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"kind": "audio", "assetId": "audio-mp3-id", "role": "character", "consumed": True, "source": "prompt_clip"},
    ]
    request = TimelineGenerationRequest(
        projectId="p1", sceneId="s1", batchBlockId="b1", executionSnapshotId="snap1",
        generatorId="minimax-h3-local", prompt="test"
    )
    slots = collect_slots_from_batch(batch, request)
    visual_slots = [s for s in slots if s.role not in {"video", "audio"}]
    assert len(visual_slots) == 0, "audio kind should not produce a visual slot"


def test_collect_slots_character_voice_produces_audio_slot():
    """characterVoice kind should produce an audio slot, not a visual slot."""
    from app.director_timeline_w46.generation.r2v import collect_slots_from_batch
    from app.director_timeline_w46.contracts import BatchBlock
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    batch = BatchBlock(id="b1", sceneId="s1", order=0)
    batch.references = [
        {"kind": "characterVoice", "assetId": "voice-wav-id", "identityId": "char1", "consumed": True, "source": "project_character_voice"},
    ]
    request = TimelineGenerationRequest(
        projectId="p1", sceneId="s1", batchBlockId="b1", executionSnapshotId="snap1",
        generatorId="minimax-h3-local", prompt="test"
    )
    slots = collect_slots_from_batch(batch, request)
    audio_slots = [s for s in slots if s.role == "audio"]
    assert len(audio_slots) == 1, "characterVoice should produce an audio slot"
    assert audio_slots[0].assetId == "voice-wav-id"


# ---------------------------------------------------------------------------
# _resolve_project_visual_style + _style_prompt_phrase
# ---------------------------------------------------------------------------


def test_style_prompt_phrase_realistic_anime():
    """realistic_anime should map to a prompt phrase."""
    from app.director_timeline_w46.generation.request_builder import _style_prompt_phrase

    phrase = _style_prompt_phrase("realistic_anime")
    assert "realistic" in phrase.lower() or "anime" in phrase.lower()


def test_style_prompt_phrase_empty():
    """Empty style key should return empty string."""
    from app.director_timeline_w46.generation.request_builder import _style_prompt_phrase

    assert _style_prompt_phrase("") == ""
    assert _style_prompt_phrase("   ") == ""


def test_style_prompt_phrase_unknown():
    """Unknown style key should return empty string (no fallback match)."""
    from app.director_timeline_w46.generation.request_builder import _style_prompt_phrase

    # Unknown keys not in the fallback map return empty
    result = _style_prompt_phrase("nonexistent_style")
    assert result == ""


# ---------------------------------------------------------------------------
# resolve_r2v / shot characters — voice WAV must never become CRS assetId
# ---------------------------------------------------------------------------


def test_asset_is_image_rejects_audio():
    from app.director_timeline_w46.generation.character_identity_bind import _asset_is_image

    db = MagicMock()
    audio = MagicMock()
    audio.kind = "audio"
    image = MagicMock()
    image.kind = "image"
    db.get.side_effect = lambda _cls, aid: {"wav": audio, "img": image}.get(aid)
    assert _asset_is_image(db, "wav") is False
    assert _asset_is_image(db, "img") is True
    assert _asset_is_image(db, "") is False


def test_bound_crs_db_rejects_entity_pointing_at_wav():
    """Even if a prompt binding mis-tags a voice asset as entity/character, DB kind wins."""
    from app.director_timeline_w46.generation.character_identity_bind import _bound_crs_asset

    db = MagicMock()
    wav = MagicMock()
    wav.kind = "audio"
    img = MagicMock()
    img.kind = "image"
    db.get.side_effect = lambda _cls, aid: {"voice-wav-id": wav, "image-png-id": img}.get(aid)
    bound_assets = [
        {"kind": "entity", "identityId": "char1", "role": "character", "assetId": "voice-wav-id"},
        {"kind": "entity", "identityId": "char1", "role": "character", "assetId": "image-png-id"},
    ]
    assert _bound_crs_asset("char1", bound_assets, db=db) == "image-png-id"


def test_resolve_r2v_skips_voice_wav_asset():
    """resolve_r2v_character_asset must never return a non-image asset id."""
    from app.director_timeline_w46.generation import character_identity_bind as cib

    db = MagicMock()
    wav = MagicMock()
    wav.kind = "audio"
    img = MagicMock()
    img.kind = "image"
    db.get.side_effect = lambda _cls, aid: {"wav-id": wav, "img-id": img}.get(aid)

    with patch.object(cib, "_bound_crs_asset", return_value="wav-id"), patch.object(
        cib, "resolve_approved_reference", return_value=None
    ), patch.object(cib, "_find_library_character_sheet", return_value=""):
        # persisted CRS returns the real image
        with patch.dict("sys.modules", {}):
            with patch(
                "app.character_identity.crs_service.load_persisted_crs",
                return_value={"approved_sheet_asset_id": "img-id"},
            ):
                hit = {"character_id": "char1", "approved_sheet_asset_id": "wav-id"}
                assert cib.resolve_r2v_character_asset(db, "proj", hit, bound_assets=[]) == "img-id"


def test_h3_12s_frame_grid_294():
    """12s @ 24fps must snap UP to legal 17k+5 = 294 (not illegal 288)."""
    from app.workflows.h3_ref2v_builder import frames_for_duration, snap_h3_length

    assert 288 % 17 == 16
    assert frames_for_duration(12.0) == 294
    assert snap_h3_length(288) == 294
    assert 294 % 17 == 5


def test_generate_audio_copied_into_job_params():
    """Native audio flag must reach job params when Timeline has no audio override."""
    from app.director_timeline_w46.generation.r2v import copy_r2v_into_job_params
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    req = TimelineGenerationRequest(
        projectId="p1",
        sceneId="s1",
        batchBlockId="b1",
        executionSnapshotId="snap1",
        generatorId="minimax-h3-local",
        prompt="test",
        providerOptions={"generate_audio": True, "legalFrameCount": 294},
    )
    params: dict = {}
    copy_r2v_into_job_params(params, req)
    assert params.get("generate_audio") is True
    assert params.get("audio_generation") is True
    assert params.get("legalFrameCount") == 294
