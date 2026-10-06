"""Wave 2A — Timeline H3 generate call-fences (pass-through purity).

Hard-fences only. Does NOT claim LIVE H3 IDENTITY GO. Does NOT force canvas rewrite.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.direct_reference import (
    DirectReferenceItem,
    DirectReferencePayload,
    DirectSocketBinding,
    attach_direct_reference_payload,
)
from app.director_timeline_w46.generation.r2v import (
    H3_MECHANISM,
    attach_canonical_r2v,
    collect_slots_from_batch,
)
from app.director_timeline_w46.generation.registry import get_registry
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request


TIMED = (
    "<subject 1> Korri\n"
    "\n"
    "Visual style: Realistic Anime with a photorealistic background.\n"
    "\n"
    "Korri sits on a stool in crew quarters."
)


def _batch(text: str = TIMED, *, production_prompt: str = "") -> BatchBlock:
    return BatchBlock(
        id="b-wave2a",
        sceneId="s-wave2a",
        label="Wave2A",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=12.0),
        references=[
            {
                "kind": "entity",
                "role": "character",
                "assetId": "asset-korri",
                "label": "Korri",
                "consumed": True,
                "bindingId": "bind-korri",
            }
        ],
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=12,
                text=text,
                productionPrompt=production_prompt,
                role="primary",
                strength=1,
                referenceBindingIds=["bind-korri"],
            )
        ],
    )


def test_wave2a_production_prompt_never_owns_h3_input_text():
    batch = _batch(production_prompt="ILLEGAL productionPrompt authority")
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s-wave2a",
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3"),
        draft_mode=False,
    )
    assert req.prompt == TIMED
    assert "ILLEGAL productionPrompt" not in req.prompt
    assert (req.providerOptions or {}).get("authoredPrompt") == TIMED


def test_wave2a_knowledge_compiled_prompt_cannot_overwrite_h3(monkeypatch):
    from app.director_timeline_w46.generation import request_builder as rb

    monkeypatch.setattr(
        rb,
        "_compile_generator_knowledge",
        lambda **kwargs: {"compiledPrompt": "ILLEGAL knowledge rewrite", "compiledNegative": ""},
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s-wave2a",
        batch=_batch(),
        snapshot=ExecutionSnapshot(batchBlockId="b-wave2a", selectedGenerator="minimax-h3"),
        draft_mode=False,
    )
    assert req.prompt == TIMED
    assert "ILLEGAL knowledge rewrite" not in req.prompt


def test_wave2a_temporal_pose_movement_fence_permanent():
    batch = _batch()
    packet = SimpleNamespace(
        packetId="pkt-illegal",
        continuation=SimpleNamespace(creatorRejected=False),
    )
    import app.codirector.video_intelligence.compile as temporal_mod

    original = getattr(temporal_mod, "compile_temporal_continuation", None)
    temporal_mod.compile_temporal_continuation = lambda *a, **k: {
        "applied": True,
        "promptPrefix": "TEMPORAL PREFIX MUST NOT APPEAR",
    }
    try:
        req = build_timeline_generation_request(
            project_id="p",
            scene_id="s-wave2a",
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
    tc = (req.providerOptions or {}).get("temporalContinuation") or {}
    assert tc.get("applied") is False
    assert tc.get("reason") == "H3_DIRECT_LINE_FENCE"


def test_wave2a_prompt_prefix_residual_cannot_overwrite_h3_request_prompt():
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s-wave2a",
        batchBlockId="b-wave2a",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=TIMED,
        duration=12.0,
        providerOptions={"authoredPrompt": TIMED, "originalGeneratorId": "minimax-h3"},
    )
    payload = attach_canonical_r2v(req, _batch(), caps, db=None)
    assert req.prompt == TIMED
    assert payload.mechanism == H3_MECHANISM
    assert (req.providerOptions or {}).get("h3PromptAuthority") == "timed_prompt_direct_line"
    # Even if diagnostics promptPrefix differs, Input Text stays Timed Prompt.
    req.providerOptions["r2v"]["promptPrefix"] = "ILLEGAL PREFIX OVERWRITE"
    # Re-attach must still refuse overwrite
    attach_canonical_r2v(req, _batch(), caps, db=None)
    assert req.prompt == TIMED


def test_wave2a_dr_only_sockets_no_place_prior_auto():
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s-wave2a",
        batchBlockId="b-wave2a",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=TIMED,
        startImageAssetId="place-not-checked",
        lastFrameAssetId="prior-not-checked",
        providerOptions={
            "authoredPrompt": TIMED,
            "originalGeneratorId": "minimax-h3",
            "planningStartImageAssetId": "place-not-checked",
        },
    )
    payload = attach_canonical_r2v(req, _batch(), caps, db=None)
    ids = {slot.assetId for slot in payload.slots}
    assert "place-not-checked" not in ids
    assert "prior-not-checked" not in ids
    assert not any(slot.role in {"place", "prior_frame"} for slot in payload.slots)
    assert "asset-korri" in ids


def test_wave2a_empty_dr_payload_does_not_invent_place_prior():
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    direct = DirectReferencePayload(
        projectId="p",
        sceneId="s-wave2a",
        batchId="b-wave2a",
        generatorId="minimax-h3-t2v-local",
        characters=[],
        sockets=[],
    )
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s-wave2a",
        batchBlockId="b-wave2a",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=TIMED,
        startImageAssetId="place-x",
        lastFrameAssetId="prior-x",
        providerOptions={"authoredPrompt": TIMED, "originalGeneratorId": "minimax-h3"},
    )
    attach_direct_reference_payload(req, direct)
    payload = attach_canonical_r2v(req, _batch(), caps, db=None)
    # The fallback collector still yields the batch's own checked character
    # slots (sibling fence test_wave2a_collect_slots_h3_auto_continuity_off).
    # The Wave 2A fence is: H3 with no bridge must NOT invent place/prior
    # slots from request.startImageAssetId / request.lastFrameAssetId.
    ids = {(s.role, s.assetId) for s in payload.slots}
    assert ("place", "place-x") not in ids
    assert ("prior_frame", "prior-x") not in ids
    assert "place-x" not in {s.assetId for s in payload.slots}
    assert "prior-x" not in {s.assetId for s in payload.slots}


def test_wave2a_collect_slots_h3_auto_continuity_off():
    batch = _batch()
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId=batch.id,
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        prompt=TIMED,
        startImageAssetId="anchor-place",
        lastFrameAssetId="prior-y",
    )
    slots = collect_slots_from_batch(batch, req, auto_continuity_slots=False)
    ids = {s.assetId for s in slots}
    assert "asset-korri" in ids
    assert "anchor-place" not in ids
    assert "prior-y" not in ids


def test_wave2a_does_not_claim_identity_go():
    # Explicit sentinel for PART XXIV — fences ≠ IDENTITY GO.
    assert "LIVE_H3_IDENTITY_GO" != "WAVE2A"
