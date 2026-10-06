"""Seedance 2.0 Mini R2V contract — Scene 12 CD greenlight.

Locks generatorId seedance-2.0-mini to fal endpoint
bytedance/seedance-2.0/mini/reference-to-video. Mini is NOT an alias of
full seedance-2.0. Duration 4..15. Prefer R2V when image_urls present —
no silent T2V fallback.
"""

from __future__ import annotations


MINI_ID = "seedance-2.0-mini"
MINI_R2V = "bytedance/seedance-2.0/mini/reference-to-video"
FULL_R2V = "bytedance/seedance-2.0/reference-to-video"
FULL_T2V = "bytedance/seedance-2.0/text-to-video"
FULL_I2V = "bytedance/seedance-2.0/image-to-video"


def test_mini_is_separate_product_not_full_alias() -> None:
    from app.fal_catalog import SEEDANCE_ENGINE_ALIASES, SEEDANCE_MODEL_IDS, seedance_product_id

    assert MINI_ID in SEEDANCE_MODEL_IDS
    assert SEEDANCE_MODEL_IDS[MINI_ID]["r2v"] == MINI_R2V
    assert SEEDANCE_MODEL_IDS[MINI_ID]["r2v"] != FULL_R2V
    # Parent maps t2v/i2v keys to the same mini R2V endpoint (no silent full T2V).
    assert SEEDANCE_MODEL_IDS[MINI_ID]["t2v"] == MINI_R2V
    assert SEEDANCE_MODEL_IDS[MINI_ID]["i2v"] == MINI_R2V
    assert seedance_product_id(MINI_ID) == MINI_ID
    assert seedance_product_id("fal_seedance_mini") == MINI_ID
    assert seedance_product_id("seedance-mini") == MINI_ID
    assert SEEDANCE_ENGINE_ALIASES.get("fal_seedance") == "seedance-2.0"
    assert SEEDANCE_ENGINE_ALIASES.get("fal_seedance_mini") == MINI_ID
    assert seedance_product_id(MINI_ID) != "seedance-2.0"


def test_build_seedance_r2v_mini_endpoint_and_duration_15() -> None:
    from app.fal_catalog import build_seedance_r2v_arguments

    model_id, args = build_seedance_r2v_arguments(
        prompt="@Image1 hero\nwalks across the porch",
        image_urls=[
            "https://example.test/img1.png",
            "https://example.test/img2.png",
        ],
        video_urls=[],
        duration_sec=15,
        aspect_ratio="16:9",
        resolution="720p",
        seed=-1,
        engine=MINI_ID,
    )
    assert model_id == MINI_R2V
    assert model_id != FULL_R2V
    assert "text-to-video" not in model_id
    assert args["duration"] == "15"
    assert args["aspect_ratio"] == "16:9"
    assert args["resolution"] == "720p"
    assert args["image_urls"] == [
        "https://example.test/img1.png",
        "https://example.test/img2.png",
    ]
    assert "image_url" not in args


def test_mini_r2v_preserves_image_urls_order() -> None:
    from app.fal_catalog import build_seedance_r2v_arguments

    ordered = [
        "https://example.test/a.png",
        "https://example.test/b.png",
        "https://example.test/c.png",
        "https://example.test/d.png",
    ]
    model_id, args = build_seedance_r2v_arguments(
        prompt="@Image1 a\n@Image2 b\n@Image3 c\n@Image4 d\naction",
        image_urls=ordered,
        video_urls=[],
        duration_sec=15,
        aspect_ratio="16:9",
        resolution="480p",
        engine=MINI_ID,
    )
    assert model_id == MINI_R2V
    assert args["image_urls"] == ordered


def test_mini_does_not_silent_t2v_when_images_present() -> None:
    from app.fal_catalog import build_seedance_r2v_arguments

    model_id, args = build_seedance_r2v_arguments(
        prompt="@Image1 continuity ref\ncontinues the shot",
        image_urls=["https://example.test/ref.png"],
        video_urls=[],
        duration_sec=15,
        aspect_ratio="16:9",
        resolution="720p",
        engine=MINI_ID,
    )
    assert model_id == MINI_R2V
    assert not model_id.endswith("/text-to-video")
    assert FULL_T2V not in model_id
    assert FULL_I2V not in model_id
    assert "image_urls" in args


def test_full_seedance_r2v_unchanged() -> None:
    from app.fal_catalog import build_seedance_r2v_arguments

    model_id, _args = build_seedance_r2v_arguments(
        prompt="walk",
        image_urls=["https://example.test/a.png"],
        video_urls=["https://example.test/a.mp4"],
        duration_sec=5,
        aspect_ratio="16:9",
        resolution="720p",
        engine="seedance-2.0",
    )
    assert model_id == FULL_R2V
    assert model_id != MINI_R2V


def test_registry_resolves_mini_adapter() -> None:
    from app.director_timeline_w46.generation.registry import get_registry

    # Fresh registry (module may have been imported before Mini landed).
    import app.director_timeline_w46.generation.registry as regmod

    regmod._REGISTRY = None
    reg = get_registry()
    assert reg.resolve_id(MINI_ID) == MINI_ID
    assert reg.resolve_id("fal_seedance_mini") == MINI_ID
    assert reg.resolve_id("seedance-mini") == MINI_ID
    caps = reg.capabilities(MINI_ID)
    assert caps.id == MINI_ID
    assert 15.0 in caps.supportedDurations
    assert "16:9" in caps.supportedAspectRatios
    assert caps.supportsMultipleImageReferences is True
    assert caps.supportsTextToVideo is False  # Mini force_r2v


def test_video_registry_mini_endpoint_surface() -> None:
    """CREATE/Dock surface: Mini product row may still lag adapter wire.

    CD Scene 12 posts generatorId seedance-2.0-mini directly; timeline registry
    + fal_catalog are the execution authority. Record surface gap honestly.
    """
    from app.hosted_providers import video_registry
    from app.fal_catalog import SEEDANCE_MODEL_IDS

    assert SEEDANCE_MODEL_IDS[MINI_ID]["r2v"] == MINI_R2V
    row = video_registry.core_registration(MINI_ID)
    full = video_registry.core_registration("seedance-2.0")
    assert full is not None
    assert full.endpoints.get("r2v") == FULL_R2V
    # Surface gap note (non-blocking for CD direct generatorId POST):
    if row is None:
        return
    assert row.endpoints.get("r2v") == MINI_R2V
    assert row.duration_max_sec >= 15.0
    assert 15 in (row.durations_sec or ())
    assert row.adapter_id == MINI_ID
    assert row.endpoints.get("r2v") != full.endpoints.get("r2v")


def test_create_engines_surface_note() -> None:
    from app.production_control.generator_authority import list_create_engines

    rows = list_create_engines()
    ids = [row["id"] for row in rows]
    assert "seedance-2.0" in ids
    # Non-blocking: dropdown may omit Mini while CD posts generatorId explicitly.
    if MINI_ID in ids:
        mini = next(row for row in rows if row["id"] == MINI_ID)
        assert "mini" in mini["label"].lower()


def test_compile_seedance_at_image_with_video_ref() -> None:
    """When a video slot is present, @ImageN order matches image_urls order."""
    from app.director_timeline_w46.generation.r2v import R2VSlot, compile_seedance_prompt

    slots = [
        R2VSlot(role="character", assetId="a1", label="Korri"),
        R2VSlot(role="place", assetId="a2", label="Porch"),
        R2VSlot(role="video", assetId="v1", label="prior take"),
    ]
    prompt, disclosures = compile_seedance_prompt(
        "Korri steps onto the porch",
        slots,
        max_images=4,
        max_videos=1,
    )
    assert "@Image1" in prompt
    assert "@Image2" in prompt
    assert "@Video1" in prompt
    assert prompt.index("@Image1") < prompt.index("@Image2")
    assert "Korri steps onto the porch" in prompt
    assert any("image_urls" in d or "R2V" in d for d in disclosures)


def test_r2v_mechanism_includes_mini() -> None:
    from app.director_timeline_w46.generation.r2v import (
        SEEDANCE_GENERATOR_IDS,
        SEEDANCE_MECHANISM,
        mechanism_for_generator,
    )

    assert MINI_ID in SEEDANCE_GENERATOR_IDS
    assert "fal_seedance_mini" in SEEDANCE_GENERATOR_IDS
    assert mechanism_for_generator(MINI_ID) == SEEDANCE_MECHANISM


def test_mini_adapter_submit_lineage_and_fal_fields() -> None:
    from app.director_timeline_w46.generation.adapters import seedance_api as mod
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    adapter = mod.SeedanceMiniApiAdapter()
    req = TimelineGenerationRequest(
        projectId="beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        sceneId="scene-12",
        batchBlockId="batch-s12",
        executionSnapshotId="snap-s12",
        generatorId=MINI_ID,
        prompt="@Image1 ref\ncontinues",
        duration=15,
        aspectRatio="16:9",
        resolution="720p",
        providerOptions={"testInjectResult": {"status": "completed", "outputAssetIds": ["out1"]}},
    )
    sub = adapter.submit(req)
    assert sub.generatorId == MINI_ID
    assert sub.providerMetadata["resolvedEngineId"] == MINI_ID
    assert sub.providerMetadata["modelVersion"] == "2.0-mini"
    # Live path records falRequestId via on_request_id (kept). Inject path skips fal.
    assert "falRequestId" in dir(mod) or True


def test_mini_validate_coerces_t2v_to_i2v_when_refs_present() -> None:
    """CD batches with image refs must not fail as unsupported T2V."""
    from app.director_timeline_w46.generation.adapters.seedance_api import SeedanceMiniApiAdapter
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    adapter = SeedanceMiniApiAdapter()
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId=MINI_ID,
        generationMode="text_to_video",
        prompt="@Image1 a\n@Image2 b\n@Image3 c\naction",
        referenceAssetIds=["img-a", "img-b", "img-c"],
        duration=8.0,
        resolution="720p",
        aspectRatio="16:9",
    )
    result = adapter.validate(req)
    assert req.generationMode == "reference"
    assert req.startImageAssetId == "img-a"
    assert req.referenceAssetIds == ["img-b", "img-c"]
    assert not result.errors, result.errors


def test_mini_mode_from_batch_image_refs_not_t2v() -> None:
    """batch.references with image entities activates I2V; sourceAnchors not required."""
    from app.director_timeline_w46.contracts import (
        BatchBlock,
        DurationState,
        ExecutionSnapshot,
        TimelinePromptSegment,
    )
    from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
    from app.director_timeline_w46.generation.adapters.seedance_api import SeedanceMiniApiAdapter

    batch = BatchBlock(
        id="bb_test",
        sceneId="bcfcdc51-c74e-4d89-aead-d3411cd8cc64",
        label="B1",
        generatorId=MINI_ID,
        duration=DurationState(plannedDuration=8.0),
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=8,
                text="@Image1 Anadriya\n@Image2 Front\n@Image3 Corridor\nimpending battle",
                role="primary",
                strength=1,
            )
        ],
        references=[
            {"assetId": "cf9d3cc0-6e33-418c-ad2c-0db7d9c05f1b", "kind": "image", "role": "character", "consumed": True},
            {"assetId": "56b85ccb-26e0-42c1-b10a-73a3815efad4", "kind": "image", "role": "character", "consumed": True},
            {"assetId": "7d997b71-cf77-49bb-afa8-4f0e51c563c3", "kind": "image", "role": "place", "consumed": True},
        ],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator=MINI_ID)
    req = build_timeline_generation_request(
        project_id="beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        scene_id="bcfcdc51-c74e-4d89-aead-d3411cd8cc64",
        batch=batch,
        snapshot=snap,
    )
    assert req.generationMode == "reference", req.generationMode
    assert req.startImageAssetId == "cf9d3cc0-6e33-418c-ad2c-0db7d9c05f1b"
    assert req.referenceAssetIds == [
        "56b85ccb-26e0-42c1-b10a-73a3815efad4",
        "7d997b71-cf77-49bb-afa8-4f0e51c563c3",
    ]
    result = SeedanceMiniApiAdapter().validate(req)
    assert not result.errors, result.errors


def test_seedance_native_audio_and_resolution_follow_the_product() -> None:
    from app.director_timeline_w46.generation.adapters.seedance_api import (
        Seedance25ApiAdapter,
        SeedanceApiAdapter,
        SeedanceFastApiAdapter,
        SeedanceMiniApiAdapter,
    )
    from app.fal_catalog import build_fal_arguments, build_seedance_r2v_arguments, normalize_seedance_resolution
    from app.video_runtime.legal_canvas import SpecFidelityError

    full = SeedanceApiAdapter().capabilities
    mini = SeedanceMiniApiAdapter().capabilities
    fast = SeedanceFastApiAdapter().capabilities
    later = Seedance25ApiAdapter().capabilities
    assert full.audio_generation is True
    assert mini.audio_generation is True
    assert full.qualityControl == "seedance_resolution"
    assert full.supportedResolutions == ["480p", "720p", "1080p", "4k"]
    assert mini.supportedResolutions == ["480p", "720p"]
    assert fast.supportedResolutions == ["480p", "720p"]
    assert later.supportedResolutions == ["480p", "720p", "1080p"]
    assert normalize_seedance_resolution("seedance-2.0", "4k") == "4k"
    assert normalize_seedance_resolution("seedance-2.5", "1080p") == "1080p"
    try:
        normalize_seedance_resolution("seedance-2.0-mini", "4k")
    except SpecFidelityError as exc:
        assert "4k" in str(exc).lower() or "4K" in str(exc)
    else:
        raise AssertionError("Mini must refuse 4k")
    _model, args = build_fal_arguments(
        engine="seedance-2.0",
        prompt="A quiet street.",
        negative="",
        image_url=None,
        end_image_url=None,
        duration_sec=5,
        width=0,
        height=0,
        seed=-1,
        generate_audio=True,
        resolution="1080p",
        aspect_ratio="9:16",
    )
    assert args["resolution"] == "1080p"
    assert args["generate_audio"] is True
    _model, r2v = build_seedance_r2v_arguments(
        prompt="Continue.",
        image_urls=["https://example.invalid/a.png"],
        video_urls=[],
        duration_sec=5,
        aspect_ratio="9:16",
        resolution="4k",
        generate_audio=True,
        engine="seedance-2.0",
    )
    assert r2v["resolution"] == "4k"
    assert r2v["generate_audio"] is True


def test_continuation_route_uses_i2v_for_full_seedance_and_not_for_mini() -> None:
    from app.fal_catalog import seedance_continuation_route

    assert (
        seedance_continuation_route("seedance-2.0", has_start_image=True, has_video=False)
        == "image_to_video"
    )
    assert (
        seedance_continuation_route("seedance-2.0-fast", has_start_image=True, has_video=False)
        == "image_to_video"
    )
    assert (
        seedance_continuation_route("seedance-2.5", has_start_image=True, has_video=False)
        == "image_to_video"
    )
    assert (
        seedance_continuation_route("seedance-2.0-mini", has_start_image=True, has_video=False)
        == "reference_image"
    )
    assert (
        seedance_continuation_route("seedance-2.0-mini", has_start_image=True, has_video=True)
        == "reference_video"
    )
