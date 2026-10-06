"""Timeline local generators emit one canonical R2V contract."""

from __future__ import annotations

from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    TimelinePromptSegment,
    TimelineVisualAnchor,
)
from app.director_timeline_w46.generation.adapter import validate_against_capabilities
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.r2v import (
    H3_MECHANISM,
    LTX25_MECHANISM,
    TIMELINE_R2V_REQUIRED,
    attach_canonical_r2v,
)
from app.director_timeline_w46.generation.registry import get_registry
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.workflows.h3_ref2v_builder import (
    H3_FAST_CACHE_NODE,
    H3_FAST_CACHE_NODE_ID,
    H3_NODE_CONDITIONER,
    H3_NODE_GUIDER,
    H3_NODE_SCHEDULER,
    H3_NODE_SAGE,
    H3_NODE_UNET,
    H3_REF2VA_UNET,
    assert_h3_ref2v_graph,
    build_h3_ref2v,
    h3_ref_audio_links,
    h3_ref_image_links,
)


def _batch(generator_id: str, **kwargs) -> BatchBlock:
    body = {
        "sceneId": "scene",
        "generatorId": generator_id,
        "duration": DurationState(plannedDuration=5.0),
        "promptSegments": [TimelinePromptSegment(text="Korri walks the porch", start=0, length=5)],
        "sourceAnchors": [TimelineVisualAnchor(kind="image", assetId="place-1", label="Porch")],
        "references": [
            {"kind": "image", "role": "character", "assetId": "hero-k", "label": "Korri", "consumed": True},
            {"kind": "image", "role": "character", "assetId": "hero-a", "label": "Anadriya", "consumed": True},
        ],
    }
    body.update(kwargs)
    return BatchBlock(**body)


def test_local_request_is_reference_not_t2v_or_i2v():
    snap = ExecutionSnapshot(batchBlockId="bb", selectedGenerator="ltx-2.5-distilled")
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=_batch("ltx-2.5-distilled"),
        snapshot=snap,
        aspect_ratio="16:9",
    )
    assert req.generationMode == "image_to_video"
    r2v = req.providerOptions["r2v"]
    assert r2v["mechanism"] == LTX25_MECHANISM
    ids = {slot["assetId"] for slot in r2v["slots"]}
    assert {"place-1", "hero-k", "hero-a"} <= ids
    assert req.startImageAssetId == "place-1"
    assert "[R2V]" not in req.prompt
    assert "Opening picture is" not in req.prompt
    assert "Anadriya" in req.prompt



def test_ltx25_does_not_promote_a_reference_into_the_start_image():
    """A Library reference is not an LTX start frame unless the shot selects it."""
    snap = ExecutionSnapshot(batchBlockId="bb", selectedGenerator="ltx-2.5-distilled")
    batch = _batch(
        "ltx-2.5-distilled",
        sourceAnchors=[],
        references=[
            {
                "kind": "image",
                "role": "reference",
                "assetId": "0c7d967f-eb3b-4003-a4d6-a4a562a38ee0",
                "label": "AnadriyaFront",
                "consumed": True,
            }
        ],
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=batch,
        snapshot=snap,
        aspect_ratio="16:9",
    )
    assert req.generationMode == "text_to_video"
    assert req.startImageAssetId is None


def test_h3_request_uses_ref2va_tags_not_first_frame():
    snap = ExecutionSnapshot(batchBlockId="bb", selectedGenerator="minimax-h3-t2v-local")
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=_batch("minimax-h3-t2v-local"),
        snapshot=snap,
        aspect_ratio="16:9",
    )
    assert req.generationMode == "reference"
    r2v = req.providerOptions["r2v"]
    assert r2v["mechanism"] == H3_MECHANISM
    # Phase A: dialect compile stays diagnostics-only. Additive subject binds
    # prepend onto request.prompt; authoredPrompt stays the Timed Prompt.
    assert "Korri walks the porch" in req.prompt
    assert "<subject 1> is Korri." in req.prompt
    assert (req.providerOptions or {}).get("authoredPrompt") == "Korri walks the porch"
    prefix = r2v.get("promptPrefix") or ""
    assert prefix == "Korri walks the porch"
    assert req.startImageAssetId == "place-1"
    assert req.resolution == "864x480"
    result = get_registry().get("minimax-h3-t2v-local").validate(req)
    assert result.ok is True


def test_h3_merge_replaces_front_still_character_slots():
    from app.director_timeline_w46.generation.r2v import merge_identity_slots

    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt="Walk",
        providerOptions={
            "originalGeneratorId": "minimax-h3",
            "authoredPrompt": "Walk",
            "r2v": {
                "slots": [
                    {"role": "character", "assetId": "front-k", "label": "Korri"},
                    {"role": "place", "assetId": "place-1", "label": "Corridor"},
                ]
            },
        },
    )
    merge_identity_slots(
        req,
        characters=[{"assetId": "crs-k", "name": "Korri", "characterId": "char-k"}],
        place_asset_id="place-1",
        method="h3_ref2va",
    )
    slots = req.providerOptions["r2v"]["slots"]
    char_ids = [slot["assetId"] for slot in slots if slot["role"] == "character"]
    assert char_ids == ["crs-k"]
    assert "front-k" not in {slot["assetId"] for slot in slots}


def test_h3_bind_order_is_crs_ers_prs_then_prior():
    from app.director_timeline_w46.generation.r2v import R2VSlot, map_canonical_r2v

    payload = map_canonical_r2v(
        slots=[
            R2VSlot(role="prior_frame", assetId="last-1", label="Previous take"),
            R2VSlot(role="prop", assetId="prs-mug", label="CoffeeMug"),
            R2VSlot(role="place", assetId="ers-1", label="VentureCorridorScene"),
            R2VSlot(role="character", assetId="crs-a", label="Anadriya"),
            R2VSlot(role="character", assetId="crs-k", label="Korri"),
        ],
        generator_id="minimax-h3",
        mapped_start="ers-1",
        authored_prompt="They talk in the corridor.",
        joining=False,
    )
    visual = [slot for slot in payload.slots if slot.pictureIndex]
    assert [(slot.role, slot.label, slot.pictureIndex) for slot in visual] == [
        ("character", "Anadriya", 1),
        ("character", "Korri", 2),
        ("place", "VentureCorridorScene", 3),
        ("prop", "CoffeeMug", 4),
        ("prior_frame", "Previous take", 5),
    ]


def test_h3_same_cast_last_frame_stays_prior_not_place():
    from app.director_timeline_w46.generation.r2v import R2VSlot, map_canonical_r2v

    last = "cbr-last"
    payload = map_canonical_r2v(
        slots=[
            R2VSlot(role="character", assetId="hero-k", label="Korri"),
            R2VSlot(role="character", assetId="hero-a", label="Anadriya"),
            R2VSlot(role="place", assetId="place-1", label="Corridor"),
            R2VSlot(role="place", assetId=last, label="Scene"),
            R2VSlot(role="prior_frame", assetId=last, label="Previous take"),
        ],
        generator_id="minimax-h3",
        mapped_start=last,
        authored_prompt="Continue the walk",
        joining=False,
    )
    prior = next(slot for slot in payload.slots if slot.assetId == last)
    assert prior.role == "prior_frame"
    assert prior.pictureIndex is not None
    assert not any(slot.role == "place" and slot.assetId == last for slot in payload.slots)
    assert payload.promptPrefix == "Continue the walk"
    corridor = next(slot for slot in payload.slots if slot.assetId == "place-1")
    assert corridor.role == "place"
    assert corridor.pictureIndex is not None


def test_h3_attach_maps_last_frame_to_prior_when_start_matches():
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt="Continue the walk",
        startImageAssetId="cbr-last",
        lastFrameAssetId="cbr-last",
        providerOptions={"originalGeneratorId": "minimax-h3", "authoredPrompt": "Continue the walk"},
    )
    batch = _batch(
        "minimax-h3",
        sourceAnchors=[TimelineVisualAnchor(kind="image", assetId="place-1", label="Place")],
    )
    payload = attach_canonical_r2v(req, batch, caps)
    # Phase N: H3 does not auto-inject last-frame / opening picture sockets.
    assert not any(slot.assetId == "cbr-last" for slot in payload.slots)
    assert not any(slot.role == "prior_frame" for slot in payload.slots)
    assert "Continue the walk" in req.prompt
    assert (req.providerOptions or {}).get("authoredPrompt") == "Continue the walk"
    assert payload.promptPrefix == "Continue the walk"


def test_h3_prompt_binds_approved_audio_slots():
    from app.director_timeline_w46.generation.r2v import R2VSlot, compile_h3_prompt

    prompt, _ = compile_h3_prompt(
        "Korri says hello",
        [
            R2VSlot(role="character", assetId="hero-k", label="Korri", pictureIndex=1),
            R2VSlot(role="audio", assetId="voice-k", label="Korri", audioIndex=1),
        ],
    )
    assert prompt == "Korri says hello"


def test_h3_joining_keeps_prior_slot_without_picture_index():
    from app.director_timeline_w46.generation.r2v import R2VSlot, map_canonical_r2v

    payload = map_canonical_r2v(
        slots=[
            R2VSlot(role="character", assetId="hero-k", label="Korri"),
            R2VSlot(role="character", assetId="hero-a", label="Anadriya"),
            R2VSlot(role="place", assetId="place-1", label="Corridor"),
            R2VSlot(role="prior_frame", assetId="leak-last", label="Previous take"),
        ],
        generator_id="minimax-h3",
        mapped_start="place-1",
        authored_prompt="Korri and Anadriya walk the corridor",
        joining=True,
    )
    assert payload.tensorSlotCount == 3
    assert payload.promptOnlyCount == 1
    prior = next(slot for slot in payload.slots if slot.role == "prior_frame")
    assert prior.pictureIndex is None
    assert prior.assetId == "leak-last"
    assert payload.promptPrefix == "Korri and Anadriya walk the corridor"
    assert "<Picture 4>" not in payload.promptPrefix
    assert any("joining" in note.lower() for note in payload.disclosures)


def test_stale_third_identity_does_not_become_a_picture():
    from app.director_timeline_w46.generation.r2v import collect_slots_from_batch

    batch = BatchBlock(
        sceneId="scene",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="Korri sits beside Addex", start=0, length=5)],
        references=[
            {
                "kind": "entity",
                "role": "character",
                "assetId": "korri-crs",
                "label": "Korri",
                "identityId": "korri-id",
                "consumed": True,
            },
            {
                "kind": "entity",
                "role": "character",
                "assetId": "addex-crs",
                "label": "Addex",
                "identityId": "addex-id",
                "consumed": True,
            },
            {
                "kind": "characterIdentity",
                "consumed": True,
                "identityIds": ["korri-id", "addex-id", "extra-id"],
                "identityAssetIds": ["korri-crs", "addex-crs", "anadriya-crs"],
                "identityNames": ["Korri", "Addex", "Anadriya"],
            },
            {
                "kind": "characterVoice",
                "consumed": True,
                "assetId": "anadriya-wav",
                "label": "Anadriya",
                "identityId": "extra-id",
            },
        ],
    )
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        prompt="Korri sits beside Addex",
    )
    slots = collect_slots_from_batch(batch, req)
    picture_ids = {s.assetId for s in slots if s.role == "character"}
    audio_ids = {s.identityId for s in slots if s.role == "audio"}
    assert picture_ids == {"korri-crs", "addex-crs"}
    assert "anadriya-crs" not in picture_ids
    assert "extra-id" not in audio_ids


def test_empty_character_label_resolves_from_profile_name():
    from types import SimpleNamespace

    from app.director_timeline_w46.generation.r2v import _resolve_character_label

    db = SimpleNamespace()
    profile = SimpleNamespace(name="Anadriya")
    db.get = lambda _cls, ident: profile if ident == "char-1" else None
    assert _resolve_character_label(db, "asset-1", "char-1", "") == "Anadriya"
    assert _resolve_character_label(db, "asset-1", "char-1", "this character") == "Anadriya"
    assert _resolve_character_label(None, "asset-1", "char-1", "Addex") == "Addex"


def test_h3_prompt_does_not_replace_identity_with_appearance_prose():
    from app.director_timeline_w46.generation.r2v import R2VSlot, compile_h3_prompt

    prompt, _ = compile_h3_prompt(
        "Korri walks",
        [
            R2VSlot(
                role="character",
                assetId="hero-k",
                label="Korri",
                pictureIndex=1,
                appearance="dark pigtails; pointed ears",
            )
        ],
    )
    assert prompt == "Korri walks"
    assert "dark pigtails" not in prompt
    assert "CHARACTER IDENTITY" not in prompt
    assert "the person defined by <Picture" not in prompt


def test_h3_fast_uses_easycache_not_teacache():
    from app.workflows.h3_ref2v_builder import (
        H3_FAST_CACHE_NODE,
        H3_FAST_CACHE_NODE_ID,
        H3_NODE_CONDITIONER,
        H3_NODE_GUIDER,
        H3_NODE_SCHEDULER,
        H3_NODE_SAGE,
        build_h3_ref2v,
        assert_h3_ref2v_graph,
        h3_ref_image_links,
    )

    graph = build_h3_ref2v(
        prompt="<Picture 1> Korri\nwalks",
        ref_comfy_names=["studio/korri.png"],
        filename_prefix="studio/h3",
        seed=1,
        length=5,
        fast=True,
    )
    assert_h3_ref2v_graph(graph, expected_names=["studio/korri.png"], expect_fast=True)
    assert graph[H3_FAST_CACHE_NODE_ID]["class_type"] == H3_FAST_CACHE_NODE
    assert graph[H3_NODE_SAGE]["inputs"]["model"] == [H3_FAST_CACHE_NODE_ID, 0]
    assert graph[H3_NODE_SCHEDULER]["inputs"]["model"] == [H3_NODE_SAGE, 0]
    assert graph[H3_NODE_GUIDER]["inputs"]["model"] == [H3_NODE_SAGE, 0]
    assert graph[H3_NODE_CONDITIONER]["class_type"] == "MiniMaxH3ReferenceToVideo"
    assert not any(
        isinstance(node, dict) and node.get("class_type") in {"TeaCache", "WanVideoTeaCache", "HyVideoTeaCache"}
        for node in graph.values()
    )


def test_local_without_pictures_refuses_t2v():
    batch = BatchBlock(
        sceneId="scene",
        generatorId="ltx-2.5-distilled",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="fog rolls in", start=0, length=5)],
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-2.5-distilled"),
        aspect_ratio="16:9",
    )
    assert req.generationMode == "text_to_video"
    result = get_registry().get("ltx-2.5-distilled").validate(req)
    assert not any("Reference-to-Video only" in err for err in result.errors)
    assert not any(err.startswith("LTX_START_FRAME_REQUIRED") for err in result.errors)


def test_h3_adapter_refuses_plain_t2v_and_i2v():
    adapter = get_registry().get("minimax-h3-t2v-local")
    t2v = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="text_to_video",
        prompt="fog",
    )
    assert adapter.validate(t2v).ok is False
    i2v = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="image_to_video",
        prompt="fog",
        startImageAssetId="img",
    )
    assert adapter.validate(i2v).ok is False


def test_h3_ref2v_graph_is_not_i2v():
    graph = build_h3_ref2v(
        prompt="<Picture 1> Korri\nwalks",
        ref_comfy_names=["studio/korri.png"],
        filename_prefix="studio/h3",
        seed=1,
        length=5,
        ref_audio_comfy_names=["studio/korri.wav"],
    )
    assert_h3_ref2v_graph(
        graph,
        expected_names=["studio/korri.png"],
        expected_audio_names=["studio/korri.wav"],
    )
    assert graph[H3_NODE_CONDITIONER]["class_type"] == "MiniMaxH3ReferenceToVideo"
    assert graph[H3_NODE_UNET]["inputs"]["unet_name"] == H3_REF2VA_UNET
    assert "first_frame" not in graph[H3_NODE_CONDITIONER]["inputs"]
    assert h3_ref_image_links(graph)["ref_image_0"] == ["137", 0]
    assert h3_ref_audio_links(graph)["ref_audio_0"][1] == 0
    assert any(
        isinstance(node, dict)
        and node.get("class_type") == "LoadAudio"
        and (node.get("inputs") or {}).get("audio") == "studio/korri.wav"
        for node in graph.values()
    )


def test_h3_fast_keeps_every_voice_when_four_pictures_are_bound():
    from app.workflows.h3_ref2v_builder import (
        H3_FAST_CACHE_NODE,
        H3_FAST_CACHE_NODE_ID,
        assert_h3_ref2v_graph,
        build_h3_ref2v,
    )

    pictures = [f"studio/pic_{i}.png" for i in range(4)]
    voices = ["studio/voice_a.wav", "studio/voice_b.wav"]
    graph = build_h3_ref2v(
        prompt="<Picture 1> one",
        ref_comfy_names=pictures,
        filename_prefix="studio/h3",
        seed=1,
        length=5,
        fast=True,
        ref_audio_comfy_names=voices,
    )
    assert_h3_ref2v_graph(graph, expected_names=pictures, expected_audio_names=voices, expect_fast=True)
    assert graph[H3_FAST_CACHE_NODE_ID]["class_type"] == H3_FAST_CACHE_NODE
    bound_audio = [
        str((node.get("inputs") or {}).get("audio") or "")
        for node in graph.values()
        if isinstance(node, dict) and node.get("class_type") == "LoadAudio"
    ]
    assert bound_audio == voices
    assert graph[H3_FAST_CACHE_NODE_ID]["class_type"] != "LoadAudio"


def test_hosted_seedance_stays_on_existing_modes():
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="seedance-api",
        generationMode="text_to_video",
        prompt="hosted clip",
        duration=5.0,
    )
    assert validate_against_capabilities(get_registry().capabilities("seedance-api"), req).ok is True


def test_attach_keeps_every_slot():
    caps = get_registry().capabilities("ltx-2.5-distilled")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="ltx-2.5-distilled",
        generationMode="reference",
        prompt="walk",
        startImageAssetId="place-1",
        providerOptions={"originalGeneratorId": "ltx-2.5-distilled", "authoredPrompt": "walk"},
    )
    payload = attach_canonical_r2v(req, _batch("ltx-2.5-distilled"), caps)
    assert payload.tensorSlotCount == 1
    assert payload.promptOnlyCount >= 2
    assert len(payload.slots) >= 3
