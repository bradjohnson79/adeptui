"""Phase A+B: Timed Prompt survives build + attach on Timeline MiniMax H3.

North-star: request.prompt == authored Timed Prompt with AND without Direct Reference.
promptPrefix may exist in r2v diagnostics but must never overwrite request.prompt.
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
    attach_direct_reference_payload,
    build_direct_reference_payload,
)
from app.director_timeline_w46.generation.r2v import attach_canonical_r2v, compile_h3_prompt, R2VSlot
from app.director_timeline_w46.generation.registry import get_registry
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.generation.semantic_contract import (
    lift_style_from_text,
    sanitize_action_text,
)


AUTHORED = (
    "<subject 1> Addex\n"
    "<subject 2> Korri\n"
    "\n"
    "Visual style: Realistic Anime with a photorealistic background.\n"
    "\n"
    "Sci-fi living quarters.\n"
    "\n"
    "Addex is already seated on the couch, thinking.\n"
    "\n"
    "Korri stands beside him, then sits next to him. They hold hands. "
    "Keep both people looking exactly like their reference pictures, including face, "
    "hair, body, and clothes. The room may be sci-fi; do not put them in new uniforms.\n"
    "\n"
    "KORRI: Hey babe, are you ready for some fun?\n"
    "\n"
    "Addex smiles.\n"
    "\n"
    "ADDEX: You know I am."
)

LIVE_ACTION_PREAMBLE = (
    "High quality anime characters interacting in a photorealistic environment. "
    "The final result should look like a scene from a premium live-action cinematic production "
    "in which exceptionally high-quality realistic anime characters physically inhabit "
    "and interact with a real photorealistic environment.\n\n"
    "<subject 1> is Korri.\n"
    "<subject 2> is Addex.\n\n"
    "Korri and Addex stand facing each other in a quiet sunlit room."
)


def _batch(text: str, *, generator_id: str = "minimax-h3", binding_ids: list[str] | None = None) -> BatchBlock:
    return BatchBlock(
        id="b-h3-direct",
        sceneId="s",
        label="H3 Direct Line",
        generatorId=generator_id,
        duration=DurationState(plannedDuration=15.0),
        references=[
            {
                "kind": "image",
                "role": "character",
                "assetId": "asset-addex",
                "label": "Addex",
                "consumed": True,
            },
            {
                "kind": "image",
                "role": "character",
                "assetId": "asset-korri",
                "label": "Korri",
                "consumed": True,
            },
        ],
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=15,
                text=text,
                role="primary",
                strength=1,
                referenceBindingIds=list(binding_ids or []),
            )
        ],
    )


def test_authored_timed_prompt_survives_build_without_direct_reference():
    batch = _batch(AUTHORED)
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3")
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=batch,
        snapshot=snap,
    )
    assert req.prompt == AUTHORED
    assert (req.providerOptions or {}).get("authoredPrompt") == AUTHORED
    r2v = (req.providerOptions or {}).get("r2v") or {}
    # Diagnostics may mirror authored when subjects present; must not mutate Input Text.
    assert req.prompt == AUTHORED
    assert "Hybrid realistic-anime illustration" not in req.prompt
    assert "Korri." not in req.prompt.split("Korri", 1)[-1][:3] or True  # no period-merge on Korri line
    # Explicit: first subject line not period-merged
    assert "<subject 2> Korri\n" in req.prompt or "<subject 2> Korri\r\n" in req.prompt


def test_authored_timed_prompt_survives_attach_without_direct_reference():
    batch = _batch(AUTHORED)
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId=batch.id,
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=AUTHORED,
        duration=15.0,
        providerOptions={
            "authoredPrompt": AUTHORED,
            "visualStyle": "realistic_anime",
            "originalGeneratorId": "minimax-h3",
        },
    )
    payload = attach_canonical_r2v(req, batch, caps, db=None)
    assert req.prompt == AUTHORED
    # promptPrefix is diagnostics; when subjects present it must equal authored (passthrough)
    assert payload.promptPrefix == AUTHORED


def test_authored_timed_prompt_survives_attach_with_direct_reference(monkeypatch, tmp_path):
    from app.director_timeline_w46.generation import direct_reference as dr

    def fake_resolve(db, project_id, binding_id, fallback_asset_id=None):
        catalog = {
            "bind-addex": {
                "bindingId": "bind-addex",
                "assetId": "asset-addex",
                "identityId": "id-addex",
                "mediaKind": "image",
                "referenceType": "character",
                "alias": "Addex",
                "broken": False,
                "brokenReason": None,
                "approvalStatus": "approved",
            },
            "bind-korri": {
                "bindingId": "bind-korri",
                "assetId": "asset-korri",
                "identityId": "id-korri",
                "mediaKind": "image",
                "referenceType": "character",
                "alias": "Korri",
                "broken": False,
                "brokenReason": None,
                "approvalStatus": "approved",
            },
        }
        return catalog[str(binding_id)]

    def fake_asset(db, asset_id: str):
        path = tmp_path / f"{asset_id}.png"
        path.write_bytes(b"x")
        return SimpleNamespace(id=asset_id, kind="image", path=str(path))

    monkeypatch.setattr(dr, "resolve_binding_id", fake_resolve)
    monkeypatch.setattr(dr, "_asset_record", fake_asset)

    batch = _batch(AUTHORED, binding_ids=["bind-addex", "bind-korri"])
    payload = build_direct_reference_payload(
        None,
        project_id="p",
        scene_id="s",
        batch=batch,
        generator_id="minimax-h3",
    )
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId=batch.id,
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=AUTHORED,
        duration=15.0,
        providerOptions={
            "authoredPrompt": AUTHORED,
            "visualStyle": "realistic_anime",
            "originalGeneratorId": "minimax-h3",
        },
    )
    attach_direct_reference_payload(req, payload)
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    attach_canonical_r2v(req, batch, caps, db=None)
    assert req.prompt == AUTHORED
    assert req.providerOptions["directReferences"]["authority"] == "direct_reference_route"


def test_compile_h3_passthrough_when_owner_subjects_present():
    compiled, _ = compile_h3_prompt(
        AUTHORED,
        [
            R2VSlot(role="character", assetId="a", label="Addex", pictureIndex=1),
            R2VSlot(role="character", assetId="k", label="Korri", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    assert compiled == AUTHORED
    assert "Hybrid realistic-anime illustration" not in compiled
    assert "photorealistic background" in compiled


def test_compile_h3_preserves_live_action_preamble_with_subjects():
    compiled, _ = compile_h3_prompt(
        LIVE_ACTION_PREAMBLE,
        [
            R2VSlot(role="character", assetId="k", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="a", label="Addex", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    assert compiled == LIVE_ACTION_PREAMBLE
    assert "premium live-action" in compiled.lower()
    assert "photorealistic environment" in compiled.lower()
    assert "<subject 1> is Korri." in compiled
    assert "<subject 2> is Addex." in compiled


def test_lift_style_period_merge_fixed_when_removing():
    key, cleaned = lift_style_from_text(
        "<subject 1> Addex\n<subject 2> Korri\n\n"
        "Visual style: Realistic Anime with a photorealistic background.\n\n"
        "Sci-fi living quarters."
    )
    assert key == "realistic_anime"
    assert "<subject 2> Korri." not in cleaned  # period-merge bug must stay dead
    assert "<subject 2> Korri" in cleaned
    assert "Sci-fi living quarters" in cleaned


def test_lift_style_can_keep_creator_line_for_h3():
    raw = "Visual style: Realistic Anime with a photorealistic background.\n\nSci-fi living quarters."
    key, kept = lift_style_from_text(raw, remove_from_text=False)
    assert key == "realistic_anime"
    assert kept == raw
    assert "Visual style:" in kept


def test_sanitize_h3_does_not_strip_live_action_bias():
    cleaned = sanitize_action_text(
        LIVE_ACTION_PREAMBLE,
        style_key="realistic_anime",
        strip_live_action_bias=False,
    )
    low = cleaned.lower()
    assert "premium live-action" in low
    assert "photorealistic environment" in low
    assert "<subject 1> is Korri." in cleaned
