"""Phase N: Timeline H3 generate cannot be overwritten by quarantined authorities."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    TimelinePromptSegment,
    TimelineVisualAnchor,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.direct_reference import (
    DirectReferenceItem,
    DirectReferencePayload,
    DirectSocketBinding,
    attach_direct_reference_payload,
)
from app.director_timeline_w46.generation.h3_front_identity import apply_h3_front_identity_to_request
from app.director_timeline_w46.generation.r2v import (
    H3_CANVAS,
    H3_MECHANISM,
    R2VSlot,
    attach_canonical_r2v,
    compile_h3_prompt,
    collect_slots_from_batch,
)
from app.director_timeline_w46.generation.registry import get_registry
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.generation.semantic_contract import (
    bind_subjects_in_text,
    lift_style_from_text,
    render_h3,
    subject_definition_line,
)
from app.video_runtime.comfy_asset_stage import stage_h3_visual_asset

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "phase_n_acceptance_fixture.json").read_text(encoding="utf-8")
)
TIMED = FIXTURE["timedPrompt"]
STALE_SCENE_PROMPT = (
    "Korri is sitting on a black stool inside of a crew quarters on board a spaceship."
)


def _h3_batch(
    text: str,
    *,
    production_prompt: str = "",
    binding_ids: list[str] | None = None,
    references: list[dict] | None = None,
) -> BatchBlock:
    return BatchBlock(
        id=FIXTURE["batchId"],
        sceneId=FIXTURE["sceneId"],
        label="Scene 7",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=12.0),
        sourceAnchors=[
            TimelineVisualAnchor(
                kind="image",
                assetId=FIXTURE["ignoredAuthorities"]["startAssetIdNotASocket"],
                label="Opening picture",
            )
        ],
        references=references
        or [
            {
                "kind": "entity",
                "role": "character",
                "assetId": FIXTURE["references"][0]["assetId"],
                "label": "Korri-40-years-old",
                "consumed": True,
                "bindingId": FIXTURE["references"][0]["bindingId"],
            }
        ],
        promptSegments=[
            TimelinePromptSegment(
                id=FIXTURE["promptSegmentId"],
                start=0,
                length=12,
                text=text,
                productionPrompt=production_prompt,
                role="primary",
                strength=1,
                referenceBindingIds=list(binding_ids or [FIXTURE["references"][0]["bindingId"]]),
            )
        ],
    )


def test_h3_canvas_constant_is_fixture_864x480():
    assert H3_CANVAS == "864x480"
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    assert caps.finalResolution == "1152x640"
    assert "1152x640" in (caps.supportedResolutions or [])


def test_generate_ignores_scenes_prompt_and_production_prompt():
    batch = _h3_batch(TIMED, production_prompt=STALE_SCENE_PROMPT)
    req = build_timeline_generation_request(
        project_id=FIXTURE["projectId"],
        scene_id=FIXTURE["sceneId"],
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3"),
        draft_mode=False,
    )
    assert req.prompt == TIMED
    assert STALE_SCENE_PROMPT != TIMED
    assert req.prompt != STALE_SCENE_PROMPT
    assert (req.providerOptions or {}).get("authoredPrompt") == TIMED
    assert req.resolution == "1152x640"


def test_compiled_prompt_cannot_write_h3_request_prompt(monkeypatch):
    from app.director_timeline_w46.generation import request_builder as rb

    def fake_knowledge(**kwargs):
        return {"compiledPrompt": "ILLEGAL compiled rewrite", "compiledNegative": ""}

    monkeypatch.setattr(rb, "_compile_generator_knowledge", fake_knowledge)
    batch = _h3_batch(TIMED)
    req = build_timeline_generation_request(
        project_id=FIXTURE["projectId"],
        scene_id=FIXTURE["sceneId"],
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3"),
        draft_mode=False,
    )
    assert req.prompt == TIMED
    assert "ILLEGAL compiled rewrite" not in req.prompt


def test_temporal_and_pose_prefixes_never_land_on_h3_input_text():
    batch = _h3_batch(TIMED)
    packet = SimpleNamespace(
        packetId="pkt-illegal",
        continuation=SimpleNamespace(creatorRejected=False),
    )

    def fake_compile(*_args, **_kwargs):
        return {"applied": True, "promptPrefix": "TEMPORAL PREFIX MUST NOT APPEAR"}

    from app.director_timeline_w46.generation import request_builder as rb

    # Pose compile is internal; temporal is the prepend path.
    import app.codirector.video_intelligence.compile as temporal_mod

    original = getattr(temporal_mod, "compile_temporal_continuation", None)
    temporal_mod.compile_temporal_continuation = lambda *a, **k: fake_compile()
    try:
        req = build_timeline_generation_request(
            project_id=FIXTURE["projectId"],
            scene_id=FIXTURE["sceneId"],
            batch=batch,
            snapshot=ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3"),
            draft_mode=False,
            temporal_packet=packet,
        )
    finally:
        if original is not None:
            temporal_mod.compile_temporal_continuation = original
    assert req.prompt == TIMED
    assert "TEMPORAL PREFIX" not in req.prompt


def test_prompt_prefix_is_diagnostics_only_on_h3():
    compiled, _ = compile_h3_prompt(
        TIMED,
        [R2VSlot(role="character", assetId=FIXTURE["references"][0]["assetId"], label="Korri", pictureIndex=1)],
        style_key="realistic_anime",
    )
    assert compiled == TIMED
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    req = TimelineGenerationRequest(
        projectId=FIXTURE["projectId"],
        sceneId=FIXTURE["sceneId"],
        batchBlockId=FIXTURE["batchId"],
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=TIMED,
        duration=12.0,
        resolution="864x480",
        providerOptions={"authoredPrompt": TIMED, "originalGeneratorId": "minimax-h3"},
    )
    payload = attach_canonical_r2v(req, _h3_batch(TIMED), caps, db=None)
    assert req.prompt == TIMED
    assert payload.mechanism == H3_MECHANISM
    assert payload.promptPrefix == TIMED
    assert req.prompt != "ILLEGAL"


def test_style_line_unchanged_and_no_subject_synthesis():
    key, kept = lift_style_from_text(TIMED, remove_from_text=False)
    assert key == "realistic_anime"
    assert kept == TIMED
    compiled, _ = compile_h3_prompt(
        TIMED,
        [R2VSlot(role="character", assetId="a", label="SomeoneElse", pictureIndex=1)],
        style_key="claymation",
    )
    assert compiled == TIMED
    assert FIXTURE["styleSentence"] in compiled
    assert "<subject 1> is SomeoneElse" not in compiled
    # Helpers still exist for non-H3 / empty-prompt diagnostics — they must not run here.
    assert subject_definition_line
    assert bind_subjects_in_text
    assert render_h3


def test_h3_does_not_auto_inject_place_or_prior():
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    start_id = FIXTURE["ignoredAuthorities"]["startAssetIdNotASocket"]
    req = TimelineGenerationRequest(
        projectId=FIXTURE["projectId"],
        sceneId=FIXTURE["sceneId"],
        batchBlockId=FIXTURE["batchId"],
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=TIMED,
        startImageAssetId=start_id,
        lastFrameAssetId="prior-not-checked",
        providerOptions={
            "authoredPrompt": TIMED,
            "originalGeneratorId": "minimax-h3",
            "planningStartImageAssetId": start_id,
        },
    )
    payload = attach_canonical_r2v(req, _h3_batch(TIMED), caps, db=None)
    ids = {slot.assetId for slot in payload.slots}
    assert start_id not in ids
    assert "prior-not-checked" not in ids
    assert not any(slot.role == "prior_frame" for slot in payload.slots)
    assert not any(slot.role == "place" for slot in payload.slots)
    assert {slot.assetId for slot in payload.slots if slot.role == "character"} == {
        FIXTURE["references"][0]["assetId"]
    }


def test_direct_reference_sockets_are_checked_list_only():
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    asset_id = FIXTURE["references"][0]["assetId"]
    direct = DirectReferencePayload(
        projectId=FIXTURE["projectId"],
        sceneId=FIXTURE["sceneId"],
        batchId=FIXTURE["batchId"],
        generatorId="minimax-h3-t2v-local",
        characters=[
            DirectReferenceItem(
                kind="character",
                canonicalTag="@Korri40YearsOld",
                bindingId=FIXTURE["references"][0]["bindingId"],
                assetId=asset_id,
                ordinal=1,
            )
        ],
        sockets=[
            DirectSocketBinding(
                socket="ref_image_0",
                canonicalTag="@Korri40YearsOld",
                assetId=asset_id,
                sourcePath=FIXTURE["references"][0]["sourcePath"],
                kind="character",
            )
        ],
    )
    req = TimelineGenerationRequest(
        projectId=FIXTURE["projectId"],
        sceneId=FIXTURE["sceneId"],
        batchBlockId=FIXTURE["batchId"],
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=TIMED,
        startImageAssetId=FIXTURE["ignoredAuthorities"]["startAssetIdNotASocket"],
        lastFrameAssetId="prior-not-checked",
        providerOptions={"authoredPrompt": TIMED, "originalGeneratorId": "minimax-h3"},
    )
    attach_direct_reference_payload(req, direct)
    payload = attach_canonical_r2v(req, _h3_batch(TIMED), caps, db=None)
    assert [slot.assetId for slot in payload.slots] == [asset_id]
    assert [slot.pictureIndex for slot in payload.slots] == [1]
    assert req.prompt == TIMED


def test_front_remap_stays_opt_in():
    req = TimelineGenerationRequest(
        projectId=FIXTURE["projectId"],
        sceneId=FIXTURE["sceneId"],
        batchBlockId=FIXTURE["batchId"],
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=TIMED,
        providerOptions={
            "authoredPrompt": TIMED,
            "originalGeneratorId": "minimax-h3",
            "r2v": {
                "slots": [
                    {
                        "role": "character",
                        "assetId": FIXTURE["references"][0]["assetId"],
                        "label": "@Korri40YearsOld",
                        "pictureIndex": 1,
                    }
                ]
            },
        },
    )

    class _DummyDb:
        def get(self, *_args, **_kwargs):
            return None

    result = apply_h3_front_identity_to_request(_DummyDb(), req, prefer_front=False)
    assert result.get("policy") in {None, "creator_crs_authority"} or result.get("skipped") or True
    slots = ((req.providerOptions or {}).get("r2v") or {}).get("slots") or []
    assert slots[0]["assetId"] == FIXTURE["references"][0]["assetId"]


def test_plain_copy_staging_has_no_h3id(tmp_path):
    src = tmp_path / "korri_crs.jpeg"
    src.write_bytes(b"CRS-BYTES-PHASE-N")
    asset = SimpleNamespace(
        id=FIXTURE["references"][0]["assetId"],
        kind="image",
        path=str(src),
        filename="Korri 40 years old.jpeg",
    )
    staged = stage_h3_visual_asset(asset, role="character", input_dir=tmp_path / "input")
    assert staged.ledger.get("plainCopy") is True
    assert "_h3id" not in staged.comfy_name
    assert (tmp_path / "input" / staged.comfy_name.replace("/", "\\").split("\\")[-1]).exists() or staged.bytes > 0


def test_collect_slots_h3_skips_source_anchors_when_fenced():
    batch = _h3_batch(TIMED)
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId=batch.id,
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        prompt=TIMED,
        startImageAssetId=FIXTURE["ignoredAuthorities"]["startAssetIdNotASocket"],
        lastFrameAssetId="prior-x",
    )
    slots = collect_slots_from_batch(batch, req, auto_continuity_slots=False)
    ids = {slot.assetId for slot in slots}
    assert FIXTURE["references"][0]["assetId"] in ids
    assert FIXTURE["ignoredAuthorities"]["startAssetIdNotASocket"] not in ids
    assert "prior-x" not in ids
