"""Minimal Re-Take inheritance: ESTABLISHED + TARGET BEAT + USER DELTA.

Evidence/support for Gen RetakeContextPackage wire. Does not rebuild UI.
LAW: range retake must NOT wipe master Timed Prompt.
"""
from __future__ import annotations

from app.director_timeline_w46.contracts import (
    BatchBlock,
    CandidateVersion,
    DurationState,
    ExecutionSnapshot,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.generation.retake_context_package import (
    build_retake_context_package,
    compile_retake_prompt,
)

DELTA = "Full close-up on Korri. Korri says the line, not Anadriya."

MASTER = """Semi-realistic anime scene with cinematic anime lighting and color grading.

Anadriya and Korri are sitting on the couch inside Anadriya's Quarters. There is a documentary film crew with them and a male interviewer behind the camera. Anadriya and Korri are being interviewed by the film crew.

[SHOT 1: Wide 2 Shot on Anadriya and Korri]

The Male Interviewer Out of Shot asks:
\"Who was the Adept before you, Anadriya?\"

Anadriya is about to answer, but Korri interrupts.

[SHOT 2: Full Close Up on Korri]

Korri says abrasively:
\"Renkoka obviously! She was such a hottie. Gorgeous assets if you catch my drift!\"

[SHOT 3: Over the Shoulder shot on Anadriya.]

Anadriya snaps and says
\"Korri!\"

[SHOT 4: Over the Shoulder Shot on Korri]

Korri replies with a smile on her face
\"Have you seen her cheeks? I mean 'damn', son!\"

[SHOT 5: Wide 2 shot on both Anadriya and Korri]

Anadriya is embarrassed and whispers to Korri saying
\"You're so rude.\"

[SHOT 6: Full Close Up on Anadriya]

Anadriya looks toward Korri with an annoyed expression and says:
\"He asked me a question and you won't even let me talk!\""""


def _batch(*, batch_id: str = "bb_a2da11efffe7") -> BatchBlock:
    return BatchBlock(
        id=batch_id,
        sceneId="6a7a8a8b-71a1-41e2-8900-871c1b3d71db",
        label="Batch 1",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        candidateVersions=[
            CandidateVersion(
                id="cand_f2dc1624cef5",
                executionSnapshotId="snap_991eb36062df",
                assetId="d722e6fb-c292-47ed-bf0d-384eb2f82726",
                label="Take A",
                takeId="take_bc2f52901b0a",
                originalTakeIntent={"prompt": MASTER, "generatorId": "minimax-h3", "plannedDuration": 15.0},
            )
        ],
        references=[
            {
                "kind": "entity",
                "role": "character",
                "assetId": "7e5a01f4-19cc-4b6b-b323-1b2e01bbf4ad",
                "bindingId": "b034058d-0014-4f1c-877d-5fa0c4458d9c",
                "label": "Anadriya",
                "tag": "@Anadriya",
                "consumed": True,
            },
            {
                "kind": "entity",
                "role": "character",
                "assetId": "a97963c4-09b3-402b-8341-8f0539b4bc0b",
                "bindingId": "16ce0150-ba8b-4b85-8bbd-0af56902b737",
                "label": "Korri",
                "tag": "@Korri",
                "consumed": True,
            },
        ],
        promptSegments=[
            TimelinePromptSegment(
                id="ps_e0f7e1b2e0f5",
                start=0.0,
                length=15.0,
                text=MASTER,
                role="primary",
                strength=1.0,
                referenceBindingIds=[
                    "b034058d-0014-4f1c-877d-5fa0c4458d9c",
                    "16ce0150-ba8b-4b85-8bbd-0af56902b737",
                    "c8af54a5-e462-4eea-9d97-57e4b6be0c69",
                ],
                referenceNameBindings=[
                    {
                        "binding_id": "b034058d-0014-4f1c-877d-5fa0c4458d9c",
                        "prompt_name": "Anadriya",
                        "type": "character",
                        "tag": "@Anadriya",
                    },
                    {
                        "binding_id": "16ce0150-ba8b-4b85-8bbd-0af56902b737",
                        "prompt_name": "Korri",
                        "type": "character",
                        "tag": "@Korri",
                    },
                    {
                        "binding_id": "c8af54a5-e462-4eea-9d97-57e4b6be0c69",
                        "prompt_name": "Anadriya's Quarters",
                        "type": "environment",
                        "tag": "#AnadriyasQuarters",
                    },
                ],
            )
        ],
    )


def _snap(batch: BatchBlock, *, start: float = 3.0, length: float = 4.0) -> ExecutionSnapshot:
    return ExecutionSnapshot(
        batchBlockId=batch.id,
        selectedGenerator="minimax-h3-t2v-local",
        continuityState={
            "userCorrection": {"delta": DELTA, "prompt": DELTA, "start": start, "length": length},
            "rangeReplacement": {
                "start": start,
                "length": length,
                "prompt": DELTA,
                "sourceAssetId": "d722e6fb-c292-47ed-bf0d-384eb2f82726",
            },
        },
    )


def test_package_master_survives_alongside_delta():
    batch = _batch()
    pkg = build_retake_context_package(
        batch=batch,
        range_rep={"start": 3.0, "length": 4.0, "prompt": DELTA, "sourceAssetId": "d722e6fb-c292-47ed-bf0d-384eb2f82726"},
        supports_image_to_video=False,
    )
    assert "couch" in pkg["establishedScene"].lower()
    assert "documentary" in pkg["establishedScene"].lower()
    assert pkg["userDelta"] == DELTA
    assert "[ESTABLISHED SCENE" in pkg["compiledPrompt"]
    assert "[USER DELTA]" in pkg["compiledPrompt"]
    assert "[TARGET BEAT" in pkg["compiledPrompt"]
    assert "HARD CONSTRAINTS" in pkg["compiledPrompt"]
    assert DELTA in pkg["compiledPrompt"]
    assert "couch" in pkg["compiledPrompt"].lower()
    # Crew-present prose neutralized in bound prompt
    assert "being interviewed by the film crew" not in pkg["compiledPrompt"].lower()
    assert pkg.get("effectiveH3Exclusions")
    assert (pkg.get("debug") or {}).get("actualH3BoundPrompt") == pkg["compiledPrompt"]
    assert pkg["boundaryContinuity"]["supportsImageToVideo"] is False
    assert pkg["boundaryContinuity"]["i2vAttached"] is False
    assert pkg["currentTake"]["currentTakeId"] == "take_bc2f52901b0a"


def test_request_builder_range_retake_does_not_wipe_master():
    """BEFORE bug: prompt == DELTA only. AFTER: compiled contains master + delta."""
    batch = _batch()
    snap = _snap(batch)
    req = build_timeline_generation_request(
        project_id="beffd3d8-791d-4adf-9c4d-681ec9d4efb0",
        scene_id="6a7a8a8b-71a1-41e2-8900-871c1b3d71db",
        batch=batch,
        snapshot=snap,
    )
    # Generator-bound prompt must keep master setup
    assert "couch" in (req.prompt or "").lower()
    assert "documentary" in (req.prompt or "").lower() or "film crew" in (req.prompt or "").lower()
    assert DELTA in (req.prompt or "")
    assert req.prompt != DELTA  # must NOT be delta-only replace
    opts = req.providerOptions or {}
    assert opts.get("authoredPrompt") and "couch" in str(opts.get("authoredPrompt")).lower()
    pkg = opts.get("retakeContextPackage") or {}
    assert pkg.get("userDelta") == DELTA
    assert "couch" in str(pkg.get("establishedScene") or "").lower()
    dbg = pkg.get("debug") or {}
    assert dbg.get("userDelta") == DELTA
    assert "couch" in str(dbg.get("compiledPrompt") or dbg.get("generatorRequestPrompt") or "").lower()


def test_multi_batch_same_master_truth():
    """Same master truth regardless of batch id."""
    b1 = _batch(batch_id="bb_a2da11efffe7")
    b2 = _batch(batch_id="bb_617543d40ff7")
    p1 = build_retake_context_package(batch=b1, range_rep={"start": 0, "length": 5, "prompt": DELTA}, supports_image_to_video=False)
    p2 = build_retake_context_package(batch=b2, range_rep={"start": 0, "length": 5, "prompt": DELTA}, supports_image_to_video=False)
    assert p1["establishedScene"] == p2["establishedScene"]
    assert p1["userDelta"] == p2["userDelta"] == DELTA
    assert "[ESTABLISHED SCENE" in p1["compiledPrompt"] and "[ESTABLISHED SCENE" in p2["compiledPrompt"]


def test_compile_retake_prompt_labels():
    text = compile_retake_prompt(established="SETUP couch", local_beat="SHOT 2 Korri", user_delta=DELTA, range_start=3, range_length=4)
    assert text.startswith("[ESTABLISHED SCENE")
    assert "SETUP couch" in text
    assert "[TARGET BEAT" in text
    assert "[USER DELTA]" in text
    assert DELTA in text
    assert "HARD CONSTRAINTS" in text
    assert "OUT OF FRAME" in text
    assert "T1 > T2 > T3 > T4" in text or "T1>T2>T3>T4" in text
    assert "[PREV BEAT" in text
    assert "[NEXT BEAT" in text
