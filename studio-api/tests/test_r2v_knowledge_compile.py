"""Same creator R2V intent must compile differently per generator .md."""

from __future__ import annotations

from app.codirector.knowledgebase.video_generators import (
    PROFILE_FILES,
    load_video_generator_knowledge,
)
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    TimelinePromptSegment,
    TimelineVisualAnchor,
)
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request


AUTHORED = "Anadriya points down the corridor. Korri answers."
EXPOSED = [
    "minimax-h3",
    "minimax-h3-i2v-local",
    "ltx-2.5-full",
    "ltx-2.5-distilled",
    "ltx-2.5-comfy",
    "kling-kie",
    "kling-fal",
    "seedance-fal",
    "seedance-kie",
    "veo-fal",
    "veo-kie",
]

# Retired generators that MUST NOT be in PROFILE_FILES (active compile contract).
# Their .md files stay on disk for archival readability via get_document(), but
# load_video_generator_knowledge() must not map them as active generators.
RETIRED_IDS = [
    "ltx-local",
    "ltx",
    "ltx_2_3",
    "wan-local",
    "wan",
    "wan_2_2",
    "optional-wan",
    "hunyuan-video-1.5-local",
    "hunyuan15",
    "hunyuan-video-15",
    "hunyuan-video-13b-local",
    "hunyuan13b",
]


def _batch(generator_id: str, *, video: bool = False) -> BatchBlock:
    refs = [
        {
            "kind": "image",
            "role": "character",
            "assetId": "crs-a",
            "label": "Anadriya",
            "identityId": "id-a",
            "consumed": True,
        },
        {
            "kind": "image",
            "role": "character",
            "assetId": "crs-k",
            "label": "Korri",
            "identityId": "id-k",
            "consumed": True,
        },
        {
            "kind": "image",
            "role": "place",
            "assetId": "ers-1",
            "label": "VentureCorridorScene",
            "consumed": True,
        },
    ]
    if video:
        refs.append(
            {
                "kind": "video",
                "role": "motion",
                "assetId": "walk-1",
                "label": "WalkCycle",
                "consumed": True,
            }
        )
    return BatchBlock(
        id="b1",
        sceneId="s",
        label="R2V",
        generatorId=generator_id,
        duration=DurationState(plannedDuration=5.0),
        references=refs,
        sourceAnchors=[TimelineVisualAnchor(kind="image", assetId="ers-1", label="VentureCorridorScene")],
        promptSegments=[
            TimelinePromptSegment(id="ps1", start=0, length=5, text=AUTHORED, role="primary", strength=1)
        ],
    )


def _req(generator_id: str, *, video: bool = False):
    batch = _batch(generator_id, video=video)
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator=generator_id)
    return build_timeline_generation_request(project_id="p", scene_id="s", batch=batch, snapshot=snap)


def test_every_exposed_pc_row_has_a_knowledge_file():
    for gid in EXPOSED:
        assert gid in PROFILE_FILES, gid
        kb = load_video_generator_knowledge(gid)
        assert kb.loaded, gid
        assert kb.compile.dialect, gid


def test_retired_generators_are_not_in_active_profile_files():
    """Retired generators MUST NOT be mapped as active compile targets."""
    for gid in RETIRED_IDS:
        assert gid not in PROFILE_FILES, (
            f"{gid} is retired and must not be in PROFILE_FILES (active compile contract)"
        )


def test_retired_generators_do_not_load_as_active_knowledge():
    """load_video_generator_knowledge must not map retired generators to active compile files."""
    for gid in RETIRED_IDS:
        kb = load_video_generator_knowledge(gid)
        assert not kb.loaded, (
            f"{gid} is retired and must not load as an active generator knowledge file"
        )


def test_h3_compile_emits_picture_tokens_from_md():
    req = _req("minimax-h3-t2v-local")
    assert req.providerOptions["r2vKnowledge"]["spec"] == "minimax-h3.md"
    # Phase A: Timed Prompt stays on request.prompt; synthesized dialect lives in r2v diagnostics.
    assert req.prompt == AUTHORED
    assert (req.providerOptions or {}).get("authoredPrompt") == AUTHORED
    prefix = ((req.providerOptions or {}).get("r2v") or {}).get("promptPrefix") or ""
    assert prefix == AUTHORED
    assert req.prompt == AUTHORED
    assert "@Image1" not in req.prompt
    assert "[R2V]" not in req.prompt
    assert "CHARACTER IDENTITY" not in req.prompt
    assert "subject_definitions:" not in req.prompt
    assert not prefix.rstrip().endswith("<Picture 1> <Picture 2>")


def test_ltx25_compile_uses_r2v_prefix_not_picture():
    req = _req("ltx-2.5-distilled")
    assert req.providerOptions["r2vKnowledge"]["spec"] == "ltx-2.5.md"
    # LTX 2.5 Prompt Cleanup Law: creative prompt must not leak Adept [R2V] prose.
    assert "[R2V]" not in req.prompt
    assert "Opening picture is" not in req.prompt
    assert "<Picture" not in req.prompt
    assert "@Image" not in req.prompt
    assert "Anadriya" in req.prompt


def test_seedance_emits_at_tokens_only_with_video_ref():
    bare = _req("seedance-fal")
    assert bare.providerOptions["r2vKnowledge"]["spec"] == "seedance-2.0.md"
    assert "@Image1" not in bare.prompt
    assert "<Picture" not in bare.prompt
    assert AUTHORED in bare.prompt

    r2v = _req("seedance-fal", video=True)
    assert "@Image1" in r2v.prompt
    assert "@Image2" in r2v.prompt
    assert "@Video1" in r2v.prompt
    assert "@Audio" not in r2v.prompt
    assert "<Picture" not in r2v.prompt


def test_same_intent_changes_strategy_per_generator():
    prompts = {
        "minimax-h3-t2v-local": ((_req("minimax-h3-t2v-local").providerOptions.get("r2v") or {}).get("promptPrefix") or _req("minimax-h3-t2v-local").prompt),
        "ltx-2.5-distilled": _req("ltx-2.5-distilled").prompt,
        "seedance-fal": _req("seedance-fal", video=True).prompt,
        "kling-api": _req("kling-api").prompt,
        "veo-kie": _req("veo-kie").prompt,
    }
    assert (( _req("minimax-h3-t2v-local").providerOptions.get("r2v") or {}).get("promptPrefix") or "") == AUTHORED
    assert "[R2V]" not in prompts["ltx-2.5-distilled"]
    assert "@Video1" in prompts["seedance-fal"]
    assert "@Image1" not in prompts["kling-api"]
    assert "<Picture" not in prompts["kling-api"]
    assert "3 reference images of one subject" in " ".join(
        (_req("veo-kie").providerOptions.get("r2v") or {}).get("disclosures") or []
    )
    unique = {text for text in prompts.values()}
    assert len(unique) >= 4


def test_unknown_generator_does_not_invent_single_cond_r2v():
    from app.director_timeline_w46.generation.r2v import R2VSlot, map_canonical_r2v

    payload = map_canonical_r2v(
        slots=[
            R2VSlot(role="character", assetId="crs-k", label="Korri"),
            R2VSlot(role="place", assetId="ers-1", label="the corridor"),
        ],
        generator_id="seedance-1.5-pro",
        mapped_start="ers-1",
        authored_prompt=AUTHORED,
    )
    assert payload.mechanism == "unmapped"
    assert payload.promptPrefix == AUTHORED
    assert "[R2V]" not in payload.promptPrefix
    assert "<Picture" not in payload.promptPrefix
    assert any("not a mapped Timeline R2V dialect" in note for note in payload.disclosures)


def test_seedance_kie_stays_unavailable_not_fal():
    from app.director_timeline_w46.generation.r2v import R2VSlot, map_canonical_r2v

    payload = map_canonical_r2v(
        slots=[R2VSlot(role="character", assetId="crs-k", label="Korri")],
        generator_id="seedance-kie",
        mapped_start=None,
        authored_prompt=AUTHORED,
    )
    assert payload.mechanism in {"", "unmapped"}
    assert payload.promptPrefix == AUTHORED
    assert "@Image" not in payload.promptPrefix
    assert "<Picture" not in payload.promptPrefix
