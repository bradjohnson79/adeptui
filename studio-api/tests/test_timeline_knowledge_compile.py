"""W46 generate path must compile through generator knowledge, not Inspector-only."""

from __future__ import annotations

from app.codirector.generator_knowledge.compiler import bind_minimax_subject_tags, compile_for_generator
from app.codirector.model_intelligence.schemas import NormalizedGenerationIntent
from app.director_timeline_w46.contracts import BatchBlock, DurationState, ExecutionSnapshot, TimelinePromptSegment
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request


def _batch(generator_id: str, text: str, *, refs: list | None = None) -> BatchBlock:
    return BatchBlock(
        id="b1",
        sceneId="s",
        label="Knowledge",
        generatorId=generator_id,
        duration=DurationState(plannedDuration=5.0),
        references=refs or [],
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=5,
                text=text,
                role="primary",
                strength=1,
                anchorIds=[],
                executionStrategy="compiled",
                versionId="psv1",
            )
        ],
    )


def test_w46_minimax_compile_has_no_decorative_subjects():
    batch = _batch("minimax-h3-t2v-local", "Korri walks the porch at dusk")
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-t2v-local")
    req = build_timeline_generation_request(project_id="p", scene_id="s", batch=batch, snapshot=snap)
    assert "Korri walks the porch at dusk" in req.prompt
    assert "<subject" not in req.prompt.lower()
    knowledge = req.providerOptions.get("generatorKnowledge") or {}
    assert knowledge.get("status") == "ok"
    assert knowledge.get("dialect") == "h3_frame_roles"
    assert knowledge.get("subjectTagsEmitted") is False
    assert req.providerOptions.get("authoredPrompt")


def test_w46_ltx_compile_does_not_leak_minimax_syntax():
    batch = _batch("ltx-2.5-distilled", "Natural tracking shot down the hall")
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-2.5-distilled")
    req = build_timeline_generation_request(project_id="p", scene_id="s", batch=batch, snapshot=snap)
    assert "Natural tracking shot down the hall" in req.prompt
    assert "<subject" not in req.prompt.lower()
    knowledge = req.providerOptions.get("generatorKnowledge") or {}
    assert knowledge.get("status") == "ok"
    assert knowledge.get("dialect") == "pack_rules"


def test_w46_kling_keeps_authored_prompt_without_foreign_tokens():
    batch = _batch("kling-api", "A quiet street")
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="kling-api")
    req = build_timeline_generation_request(project_id="p", scene_id="s", batch=batch, snapshot=snap)
    assert "A quiet street" in req.prompt
    assert "<Picture" not in req.prompt
    assert "@Image" not in req.prompt
    knowledge = req.providerOptions.get("generatorKnowledge") or {}
    assert knowledge.get("status") == "ok"
    assert knowledge.get("knowledgeLoaded") is True
    assert "kling.md" in str(knowledge.get("knowledgeSpecPath") or "")


def test_subject_tags_only_from_wired_slots():
    # Unwired + no owner subjects → not emitted by this binder
    decorative = bind_minimax_subject_tags(
        "Korri walks",
        dialect="h3_frame_roles",
        slots=[{"entityId": "e1", "assetId": "a1", "routeASlot": "ref_images", "wired": False}],
    )
    assert decorative[2] is False
    assert "<Picture" not in decorative[0]

    # H3 preserves owner-dialect lowercase subjects; does not append orphan Pictures
    preserved = bind_minimax_subject_tags(
        "Korri <subject 1> walks",
        dialect="h3_frame_roles",
        slots=[{"entityId": "e1", "assetId": "a1", "routeASlot": "ref_images", "wired": True}],
    )
    assert preserved[2] is True
    assert "<subject 1>" in preserved[0]
    assert not preserved[0].rstrip().endswith("<Picture 1>")

    # Wired without subjects: signal downstream R2V will bind; still no orphan Pictures
    real = bind_minimax_subject_tags(
        "Korri walks",
        dialect="h3_frame_roles",
        slots=[{"entityId": "e1", "assetId": "a1", "routeASlot": "ref_images", "wired": True}],
    )
    assert real[2] is True
    assert "<Picture 1>" not in real[0]

    ltx = bind_minimax_subject_tags(
        "Korri <subject 1> walks",
        dialect="pack_rules",
        slots=[{"entityId": "e1", "assetId": "a1", "routeASlot": "ref_images", "wired": True}],
    )
    assert ltx[2] is False
    assert "<subject" not in ltx[0].lower()


def test_compile_emits_subject_only_when_intent_has_wired_slots():
    bare = compile_for_generator(
        "minimax-h3",
        NormalizedGenerationIntent(userPrompt="Korri walks", mediaType="video"),
    )
    assert "<subject" not in (bare.compiledPrompt or "").lower()
    bound = compile_for_generator(
        "minimax-h3",
        NormalizedGenerationIntent(
            userPrompt="Korri walks",
            mediaType="video",
            subjects=[{"entityId": "e1", "assetId": "a1", "routeASlot": "ref_images", "wired": True}],
        ),
    )
    # Knowledge binder no longer appends orphan <Picture N>; R2V render_h3 owns binding.
    assert "<Picture 1>" not in (bound.compiledPrompt or "")
    assert bound.parameters.get("subjectTagsEmitted") is True
