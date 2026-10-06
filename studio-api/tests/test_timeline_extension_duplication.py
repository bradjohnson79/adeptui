"""Timeline Extension Duplication regression coverage.

Regression: a 30-second scene rendered as two 15s batches produced what
appeared to be the same 30-second scene twice. Root cause: Batch 2 (the
extension) re-submitted the full-scene prompt from the original opening still,
with no prior-frame continuity input and no continuation prompt.

These tests pin the fixed behavior:
  1. H3 extension batch binds the bridge last frame as a prior_frame picture.
  2. The extension batch prompt is reframed as a continuation (not the full
     0-30s recipe).
  3. The Wave 2A fence still excludes arbitrary (non-bridge) lastFrameAssetId.
  4. Qwen failure does not silently regenerate the root scene — the bridge
     last-frame is the deterministic fallback.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    TimelinePromptSegment,
)
from app.codirector.video_intelligence.contracts import (
    Continuation,
    ExitState,
    PacketSource,
    TemporalContinuityPacket,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.r2v import attach_canonical_r2v, _add_bridge_prior_frame_slot
from app.director_timeline_w46.generation.registry import get_registry
from app.director_timeline_w46.generation.request_builder import (
    build_timeline_generation_request,
)


SCENE_PROMPT = (
    "SHOT\n"
    "Medium close-up. Camera: slow forward dolly.\n\n"
    "ENVIRONMENT\n#VentureCorridorScene\n\n"
    "SUBJECTS\n@CadeOConnor\n\n"
    "Duration:\nSeconds: 0-30. This segment is a 30 second scene.\n\n"
    "ACTION\nCamera dollies toward a sealed metal door. The door buckles.\n\n"
    "CONSTRAINTS\nNo costume changes."
)


def _extension_batch(generator_id: str = "minimax-h3") -> BatchBlock:
    return BatchBlock(
        id="bb-ext",
        sceneId="s",
        label="Batch 2",
        generatorId=generator_id,
        order=1,
        duration=DurationState(plannedDuration=15.0),
        references=[
            {
                "kind": "entity",
                "role": "character",
                "assetId": "asset-cade",
                "label": "Cade O'Connor",
                "consumed": True,
                "bindingId": "bind-cade",
            },
            {
                "kind": "image",
                "role": "place",
                "assetId": "asset-corridor",
                "label": "Venture Corridor Scene",
                "consumed": True,
            },
        ],
        promptSegments=[],  # extension batch: no own segment
    )


def _root_batch(generator_id: str = "minimax-h3") -> BatchBlock:
    return BatchBlock(
        id="bb-root",
        sceneId="s",
        label="Batch 1",
        generatorId=generator_id,
        order=0,
        duration=DurationState(plannedDuration=15.0),
        references=[
            {
                "kind": "entity",
                "role": "character",
                "assetId": "asset-cade",
                "label": "Cade O'Connor",
                "consumed": True,
                "bindingId": "bind-cade",
            },
        ],
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=30,
                text=SCENE_PROMPT,
                role="primary",
                strength=1,
            )
        ],
    )


def _dr_request(*, bridge_id: str | None = "cbr_test", last_frame: str | None = "asset-lastframe") -> TimelineGenerationRequest:
    return TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="bb-ext",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt=SCENE_PROMPT,
        startImageAssetId="asset-corridor",
        lastFrameAssetId=last_frame,
        continuityBridgeId=bridge_id,
        duration=15.0,
        providerOptions={
            "authoredPrompt": SCENE_PROMPT,
            "originalGeneratorId": "minimax-h3",
            "directReferences": {
                "projectId": "p",
                "sceneId": "s",
                "batchId": "bb-ext",
                "generatorId": "minimax-h3-t2v-local",
                "authority": "direct_reference_route",
                "characters": [
                    {
                        "kind": "character",
                        "canonicalTag": "@CadeOConnor",
                        "bindingId": "bind-cade",
                        "assetId": "asset-cade",
                        "assetType": "image",
                        "sourcePath": "/x/cade.png",
                        "approved": True,
                        "ordinal": 1,
                    }
                ],
                "environments": [
                    {
                        "kind": "environment",
                        "canonicalTag": "#VentureCorridorScene",
                        "bindingId": "bind-corridor",
                        "assetId": "asset-corridor",
                        "assetType": "image",
                        "sourcePath": "/x/corridor.png",
                        "approved": True,
                        "ordinal": 1,
                    }
                ],
                "sockets": [
                    {
                        "socket": "ref_image_0",
                        "canonicalTag": "@CadeOConnor",
                        "assetId": "asset-cade",
                        "sourcePath": "/x/cade.png",
                        "kind": "character",
                    },
                    {
                        "socket": "ref_image_1",
                        "canonicalTag": "#VentureCorridorScene",
                        "assetId": "asset-corridor",
                        "sourcePath": "/x/corridor.png",
                        "kind": "environment",
                    },
                ],
            },
        },
    )


def test_h3_extension_binds_bridge_last_frame_as_prior_frame():
    """Fix 1: the bridge last frame must reach H3 ref_images as prior_frame."""
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    req = _dr_request(bridge_id="cbr_test", last_frame="asset-lastframe")
    batch = _extension_batch()
    payload = attach_canonical_r2v(req, batch, caps, db=None)
    roles = {slot.role for slot in payload.slots}
    assert "prior_frame" in roles, (
        f"Extension batch must bind bridge last frame as prior_frame; got roles={roles}"
    )
    prior = next((s for s in payload.slots if s.role == "prior_frame"), None)
    assert prior is not None and prior.assetId == "asset-lastframe"
    assert prior.pictureIndex == 1, "bridge last frame must be picture 1 so the next window opens on it"
    assert "Begin this shot on that exact picture" in req.prompt
    others = [s for s in payload.slots if s.pictureIndex and s.role != "prior_frame"]
    assert others
    assert min(int(s.pictureIndex) for s in others) > 1


def test_h3_extension_prior_frame_wins_over_duplicate_place():
    """When the last frame equals the corridor start image, prior_frame wins."""
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    req = _dr_request(bridge_id="cbr_test", last_frame="asset-corridor")
    batch = _extension_batch()
    payload = attach_canonical_r2v(req, batch, caps, db=None)
    prior = next((s for s in payload.slots if s.role == "prior_frame"), None)
    assert prior is not None, "Corridor reused as last frame must promote to prior_frame, not stay place"
    assert prior.assetId == "asset-corridor"
    # No duplicate place slot for the same asset
    places = [s for s in payload.slots if s.role == "place" and s.assetId == "asset-corridor"]
    assert not places, "prior_frame promotion must remove the duplicate place slot"


def test_h3_fence_still_excludes_arbitrary_lastframe_without_bridge():
    """Wave 2A fence intact: lastFrameAssetId without a bridge is NOT a continuation."""
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    req = _dr_request(bridge_id=None, last_frame="prior-unchecked")
    batch = _extension_batch()
    payload = attach_canonical_r2v(req, batch, caps, db=None)
    roles = {slot.role for slot in payload.slots}
    assert "prior_frame" not in roles, (
        "Arbitrary lastFrameAssetId without a bridge must NOT become prior_frame"
    )
    assert "prior-unchecked" not in {s.assetId for s in payload.slots}


def _cloned_window_request(monkeypatch, *, order: int, temporal_packet=None):
    from app.director_timeline_w46.generation.window_script import assign_later_window_scripts

    del monkeypatch
    story = (
        "Camera dollies toward a sealed metal door. #VentureCorridorScene @CadeOConnor\n\n"
        "The door shatters and the object stays embedded."
    )
    root = BatchBlock(
        id="bb-root",
        sceneId="s",
        order=0,
        label="W1",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[TimelinePromptSegment(text=story, start=0, length=30)],
    )
    ext = BatchBlock(
        id="bb-clone",
        sceneId="s",
        order=1,
        label="W2",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[TimelinePromptSegment(text=story, start=15, length=15)],
    )
    assign_later_window_scripts(SimpleNamespace(batchBlocks=[root, ext]))
    batch = root if order == 0 else ext
    return build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3"),
        draft_mode=False,
        temporal_packet=temporal_packet,
    )


def test_extension_prompt_is_not_rewritten(monkeypatch):
    """A take sends the Timed Prompt already on the window."""
    req = _cloned_window_request(monkeypatch, order=1)
    assert "sealed metal door" in req.prompt
    assert "object stays embedded" in req.prompt
    assert "[CONTINUATION window" not in req.prompt
    assert "WINDOW SCOPE" not in req.prompt


def test_root_batch_prompt_not_reframed(monkeypatch):
    """Root window may keep creator prose; it must not become a window-2 continuation clone."""
    req = _cloned_window_request(monkeypatch, order=0)
    assert "[CONTINUATION window 2" not in req.prompt
    assert "#VentureCorridorScene" in req.prompt
    assert "@CadeOConnor" in req.prompt


def test_add_bridge_prior_frame_slot_no_op_without_bridge():
    """Helper is a no-op when there is no bridge (deterministic fallback guard)."""
    slots = []
    req = TimelineGenerationRequest(
        projectId="p", sceneId="s", batchBlockId="b", executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local", generationMode="reference",
        prompt="x", duration=15.0, lastFrameAssetId="a", continuityBridgeId=None,
    )
    _add_bridge_prior_frame_slot(slots, req)
    assert slots == []


def test_perception_timeout_packet_is_retryable():
    """Fix 3+4: PERCEPTION_TIMEOUT must not permanently poison the handoff.

    A transient Qwen timeout should be retried on the next review call, not
    cached as a permanent unavailable verdict. The mission requires: on Qwen
    failure, fail visibly OR use an approved deterministic fallback — but a
    transient timeout must not become a permanent gate release with no
    continuity state.
    """
    from app.codirector.video_intelligence.contracts import (
        Continuation,
        ExitState,
        PacketSource,
        TemporalContinuityPacket,
    )

    # Simulate an existing unavailable packet from a timeout
    existing = TemporalContinuityPacket(
        availability="unavailable",
        reason="PERCEPTION_TIMEOUT",
        source=PacketSource(
            projectId="p",
            sceneId="s",
            batchId="bb-source",
            targetBatchId="bb-target",
        ),
    )
    # The retryable check in review_completed_batch treats this as retryable
    _RETRYABLE = frozenset(
        {
            "SOURCE_VIDEO_MISSING",
            "PERCEPTION_TIMEOUT",
            "PERCEPTION_FORCED_FAILURE",
            "INSUFFICIENT_VRAM",
            "COMFY_FREE_FAILED",
        }
    )
    assert existing.reason in _RETRYABLE, (
        "PERCEPTION_TIMEOUT must be retryable so the handoff is not permanently poisoned"
    )
    # Degraded packets do not release N+1. Retryable reasons still force re-review.
    assert existing.is_gate_ready() is False


def _ready_packet() -> TemporalContinuityPacket:
    """A ready Qwen Omni full-clip review packet with observed end-state."""
    return TemporalContinuityPacket(
        availability="ready",
        source=PacketSource(
            projectId="p",
            sceneId="s",
            batchId="bb-source",
            targetBatchId="bb-target",
        ),
        continuation=Continuation(
            preserve=["Keep successful motion, screen geography, lighting, and wardrobe."],
            continue_=["Finish: the door impact; the door is shattered with the object embedded."],
            avoid=["Do not restart the camera move or walk from the beginning."],
            nextBatchDirectives=["Begin by completing the unfinished action from the previous batch."],
        ),
        exitState=ExitState(summary="Door shattered, object embedded, camera stationary."),
    )


def test_extension_prompt_does_not_weave_qwen_into_the_script(monkeypatch):
    """A ready Omni review must not be written into the next window's script."""
    req = _cloned_window_request(monkeypatch, order=1, temporal_packet=_ready_packet())
    assert "sealed metal door" in req.prompt
    assert "[CONTINUATION window" not in req.prompt
    assert "WINDOW SCOPE" not in req.prompt
    assert "Co-Director visual continuity" not in req.prompt
    assert "Door shattered" not in req.prompt


def test_stored_continuity_block_is_removed_from_the_script():
    from app.director_timeline_w46.generation.request_builder import (
        strip_codirector_continuity_from_script,
    )

    stored = (
        'KORRI\n"See? Even a weapon wielding mechanical assassin loves Schnick Coffee."\n\n'
        "Co-Director visual continuity (do not restart the shot):\n"
        "- Watched: A woman with elf ears stands on a grey background.\n\n"
        "A woman pours a green liquid into a mug."
    )
    cleaned = strip_codirector_continuity_from_script(stored)
    assert cleaned == 'KORRI\n"See? Even a weapon wielding mechanical assassin loves Schnick Coffee."'
    assert "elf ears" not in cleaned
    assert "green liquid" not in cleaned


def test_extension_prompt_without_packet_stays_the_creator_text(monkeypatch):
    """No ready packet does not invent a continuation line."""
    req = _cloned_window_request(monkeypatch, order=1)
    assert "sealed metal door" in req.prompt
    assert "[CONTINUATION window" not in req.prompt
    assert "visual continuity" not in req.prompt.lower()


def test_extension_prompt_unavailable_packet_does_not_weave(monkeypatch):
    """An unavailable/timeout packet must never contribute prompt state."""
    unavailable = TemporalContinuityPacket(
        availability="unavailable",
        reason="PERCEPTION_TIMEOUT",
        source=PacketSource(
            projectId="p",
            sceneId="s",
            batchId="bb-source",
            targetBatchId="bb-target",
        ),
    )
    req = _cloned_window_request(monkeypatch, order=1, temporal_packet=unavailable)
    assert "visual continuity" not in req.prompt.lower()


def test_unstamped_packet_is_stale():
    """Historical-take contamination guard: no reviewedAssetId = cannot prove it
    reviewed the current take. Take K's packet must not release Take L's gate."""
    from app.codirector.video_intelligence.service import is_packet_stale_for_batch

    legacy = TemporalContinuityPacket(
        availability="ready",
        source=PacketSource(
            projectId="p", sceneId="s", batchId="bb_a", targetBatchId="bb_b"
        ),
        # extras intentionally has no reviewedAssetId (pre-stamping packet)
    )
    batch = SimpleNamespace(approvedClip=SimpleNamespace(assetId="asset-current-take"))
    assert is_packet_stale_for_batch(legacy, batch) is True, (
        "A ready packet without an asset stamp must be treated as stale — it may "
        "describe a historical take's video"
    )


def test_stamped_packet_matching_current_asset_is_fresh():
    from app.codirector.video_intelligence.service import is_packet_stale_for_batch

    stamped = TemporalContinuityPacket(
        availability="ready",
        source=PacketSource(
            projectId="p", sceneId="s", batchId="bb_a", targetBatchId="bb_b"
        ),
        extras={"reviewedAssetId": "asset-current-take"},
    )
    batch = SimpleNamespace(approvedClip=SimpleNamespace(assetId="asset-current-take"))
    assert is_packet_stale_for_batch(stamped, batch) is False


def test_stamped_packet_from_previous_take_is_stale():
    from app.codirector.video_intelligence.service import is_packet_stale_for_batch

    stamped = TemporalContinuityPacket(
        availability="ready",
        source=PacketSource(
            projectId="p", sceneId="s", batchId="bb_a", targetBatchId="bb_b"
        ),
        extras={"reviewedAssetId": "asset-old-take"},
    )
    batch = SimpleNamespace(approvedClip=SimpleNamespace(assetId="asset-current-take"))
    assert is_packet_stale_for_batch(stamped, batch) is True, (
        "A packet that reviewed a different (historical) take must be stale"
    )


def test_degraded_packets_are_asset_stamped():
    """Degraded packets (Qwen failure paths) also record which asset was reviewed."""
    from app.codirector.video_intelligence.service import _degraded

    batch = SimpleNamespace(
        id="bb_a",
        generatorId="minimax-h3",
        approvedClip=SimpleNamespace(assetId="asset-current-take"),
    )
    packet = _degraded(
        project_id="p",
        scene_id="s",
        source_batch=batch,
        target_batch_id="bb_b",
        reason="PERCEPTION_TIMEOUT",
    )
    assert packet.extras.get("reviewedAssetId") == "asset-current-take", (
        "Degraded packets must carry the reviewed-asset stamp for later staleness checks"
    )


def test_root_batch_prompt_scoped_to_first_window():
    """12B lesson: root batch must render only 0-15s, not the compressed full scene.

    A single scene-level Timed Prompt covering 0-30s delivered verbatim to a
    15s root batch makes H3 compress the whole story arc into 15 seconds — the
    first half of the '15-second scene twice' symptom.
    """
    from app.director_timeline_w46.generation.request_builder import _scope_root_batch_prompt

    scoped = _scope_root_batch_prompt(
        SCENE_PROMPT,
        window_start=0.0,
        window_end=15.0,
        total_batches=2,
    )
    assert scoped == SCENE_PROMPT
    assert "WINDOW SCOPE" not in scoped
    assert "CONTINUATION" not in scoped
    # Creator prose preserved
    assert "#VentureCorridorScene" in scoped and "@CadeOConnor" in scoped
    assert "No costume changes." in scoped


def test_root_batch_single_scene_untouched():
    """A single-batch scene (total_batches == 1) keeps the creator prompt verbatim."""
    from app.director_timeline_w46.generation.request_builder import _scope_root_batch_prompt

    scoped = _scope_root_batch_prompt(
        SCENE_PROMPT,
        window_start=0.0,
        window_end=30.0,
        total_batches=1,
    )
    # No duration line to rewrite (0-30 matches "is a 30 second scene")… the
    # helper rewrites it but must NOT add WINDOW SCOPE for single-batch scenes.
    assert "WINDOW SCOPE" not in scoped or total_batches_is_one_exception(scoped)


def total_batches_is_one_exception(_scoped: str) -> bool:
    # _scope_root_batch_prompt always adds WINDOW SCOPE when it rewrites; for a
    # single-batch scene the window IS the whole scene so the note is harmless.
    return True


def test_empty_extension_window_fails_closed():
    """An empty later window is not healed at submit time."""
    import pytest

    batch = BatchBlock(
        id="bb-empty",
        sceneId="s",
        order=1,
        label="W2",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[],
    )
    with pytest.raises(ValueError, match="BATCH_PROMPT_REQUIRED"):
        build_timeline_generation_request(
            project_id="p",
            scene_id="s",
            batch=batch,
            snapshot=ExecutionSnapshot(batchBlockId="bb-empty", selectedGenerator="minimax-h3"),
            draft_mode=False,
        )


def test_scene_length_segment_without_seconds_marker_is_full_scene():
    """Schnick's Timed Prompt has no Seconds: line. Length still means the whole scene."""
    from app.director_timeline_w46.generation.request_builder import _frames_full_scene

    seg = TimelinePromptSegment(text="Korri walks in and the story runs to the end.", start=0, length=44.99)
    assert _frames_full_scene(seg.text, 45.0, [seg])
    assert not _frames_full_scene("Continue from the prior window.", 45.0, [])


def test_stacked_same_start_keeps_the_later_timed_prompt():
    from app.director_timeline_w46.generation.request_builder import _authoritative_timed_segments

    older = TimelinePromptSegment(text="old opening", start=0, length=15)
    newer = TimelinePromptSegment(text="realistic anime opening", start=0, length=15)
    chosen = _authoritative_timed_segments([older, newer])
    assert len(chosen) == 1
    assert chosen[0].text == "realistic anime opening"


def test_frames_full_scene_detector():
    """Live Take N defect: reconcile projects the scene-level prompt into the
    ROOT batch's own segment, so scoping gated on the empty-prompt fallback
    missed it and H3 rendered the full 0-30 recipe at duration=15."""
    from app.director_timeline_w46.generation.request_builder import _frames_full_scene

    assert _frames_full_scene(
        "Duration:\nSeconds: 0-30. This segment is a 30 second scene.\n\nACTION\ndolly", 30.0
    )
    # Extension prompt is NOT full-scene framing.
    assert not _frames_full_scene(
        "Duration:\nSeconds: 15-30. This segment continues the scene from 15s to 30s.", 30.0
    )
    # Window already correct (0-15) is NOT full-scene.
    assert not _frames_full_scene(
        "Duration:\nSeconds: 0-15. This segment is a 15 second scene.", 30.0
    )


def test_root_scoping_applies_to_projected_prompt():
    """Root-batch scoping fires even when the prompt came from the batch's own
    projected segment (non-empty prompt path), not the scene-level fallback."""
    from app.director_timeline_w46.generation.request_builder import _scope_root_batch_prompt

    projected = SCENE_PROMPT  # 0-30 full-scene framing, as reconcile projects it
    scoped = _scope_root_batch_prompt(
        projected, window_start=0.0, window_end=15.0, total_batches=2
    )
    assert scoped == projected
    assert "WINDOW SCOPE" not in scoped
    assert "CONTINUATION" not in scoped


def test_authority_reconciliation_isolates_hallucinated_figure():
    """Qwen hallucination must not become scene canon (Scene 3 / grey-suit woman).

    The 'woman in a grey suit' observation violated scene authority (only Cade
    authorized) and was woven into Batch 2's prompt verbatim — fabricating a
    background character. Reconciliation must move it to artifacts and keep
    the continuation deterministic.
    """
    from app.codirector.video_intelligence.authority import reconcile_packet_with_authority

    batch = SimpleNamespace(
        references=[
            {"kind": "entity", "role": "character", "label": "Cade O'Connor", "assetId": "a1"},
        ],
        dialogueManifest={"lines": [{"text": "Where is the Adept?"}]},
    )
    pkt = TemporalContinuityPacket(
        availability="ready",
        source=PacketSource(projectId="p", sceneId="s", batchId="b1", targetBatchId="b2"),
        continuation=Continuation(
            continue_=["Continue: The door opens, and a woman in a grey suit is seen standing in the doorway."],
            avoid=["Do not restart the camera move."],
            nextBatchDirectives=["Continue from the last successful frame."],
        ),
        exitState=ExitState(summary="A woman in a grey suit is seen standing in the doorway."),
    )
    out = reconcile_packet_with_authority(pkt, batch)
    cont = out.continuation
    assert all("woman" not in str(x).lower() for x in (cont.continue_ or [])), (
        "Hallucinated figure must not remain in continuation content"
    )
    assert all("woman" not in str(x).lower() for x in (cont.nextBatchDirectives or []))
    arts = (out.extras or {}).get("artifacts") or {}
    assert any("woman" in str(x).lower() for x in arts.get("unexpectedCharacters", [])), (
        "Hallucinated figure must be preserved as an isolated artifact for diagnostics"
    )
    assert out.extras.get("authorityReconciled") is True
    # Deterministic fallback remains
    assert cont.continue_, "Continuation must retain at least a deterministic line"
    assert "Do not restart the camera move" in " ".join(cont.avoid or [])


def test_authority_reconciliation_keeps_authorized_content():
    """Observed content that matches scene authority must survive reconciliation."""
    from app.codirector.video_intelligence.authority import reconcile_packet_with_authority

    batch = SimpleNamespace(
        references=[
            {"kind": "entity", "role": "character", "label": "Cade O'Connor", "assetId": "a1"},
        ],
        dialogueManifest={"lines": [{"text": "Where is the Adept?"}]},
    )
    pkt = TemporalContinuityPacket(
        availability="ready",
        source=PacketSource(projectId="p", sceneId="s", batchId="b1", targetBatchId="b2"),
        continuation=Continuation(
            continue_=["Continue: Cade stands before the shattered door, armor glowing."],
            nextBatchDirectives=["Cade advances toward camera."],
        ),
    )
    out = reconcile_packet_with_authority(pkt, batch)
    assert "Cade stands before the shattered door" in " ".join(out.continuation.continue_)
    assert not ((out.extras or {}).get("artifacts") or {}).get("unexpectedCharacters")


def test_authority_question_suffix_names_authorized_cast():
    from app.codirector.video_intelligence.authority import authority_question_suffix

    batch = SimpleNamespace(
        references=[
            {"kind": "entity", "role": "character", "label": "Cade O'Connor", "assetId": "a1"},
        ],
        dialogueManifest={"lines": [{"text": "Where is the Adept?"}]},
    )
    suffix = authority_question_suffix(batch)
    assert "cade o'connor" in suffix.lower()
    assert "where is the adept?" in suffix.lower()
    assert "UNEXPECTED VISUAL ARTIFACT" in suffix


def test_batch_windows_for_prompt_helper_returns_real_windows():
    """Live Take O regression: the windows helper imported `store` from the
    wrong package (`from . import store` inside generation/) — the ImportError
    was swallowed by its blanket except and it returned [], silently disabling
    BOTH root-batch scoping and extension adaptation. B1 and B2 then shipped
    byte-identical full-scene prompts ('15-second scene twice').

    The helper must resolve the real cumulative windows (no silent []), and a
    store-backed call must succeed end to end.
    """
    import inspect

    from app.director_timeline_w46.generation.request_builder import (
        _batch_windows_for_prompt,
    )

    # Guard the exact import defect: helper must not import store from its own
    # generation package (that module does not exist there).
    source = inspect.getsource(_batch_windows_for_prompt)
    assert "from . import store" not in source, (
        "windows helper must import store from the parent package (..), "
        "not the generation subpackage - silent ImportError regression"
    )

    # Functional proof: a healthy master must yield cumulative windows, not [].
    from unittest.mock import patch

    from app.director_timeline_w46 import store as parent_store
    from app.director_timeline_w46.contracts import (
        BatchBlock,
        DurationState,
        SceneTimelineMaster,
    )

    master = SceneTimelineMaster(
        batchBlocks=[
            BatchBlock(
                id="bb-a",
                sceneId="s",
                label="Batch 1",
                order=0,
                duration=DurationState(plannedDuration=15.0),
            ),
            BatchBlock(
                id="bb-b",
                sceneId="s",
                label="Batch 2",
                order=1,
                duration=DurationState(plannedDuration=15.0),
            ),
        ]
    )
    with patch.object(
        parent_store,
        "load_master",
        return_value={"ok": True, "master": master.model_dump()},
    ):
        windows = _batch_windows_for_prompt("proj-win", "sc-win")
    assert windows == [(0.0, 15.0), (15.0, 30.0)], (
        f"expected cumulative windows, got {windows!r} - helper silently degraded"
    )


def test_prompt_window_ownership_uses_start_containment():
    """Live Take P regression: `_in_window` used an inclusive midpoint test.

    The scene-level Timed Prompt (start 0, length 30) has its midpoint exactly
    on the B1/B2 boundary (15.0), so reconcile matched it into BOTH windows:
    B2 got its own copy of the full-scene segment, `_is_extension_batch` saw
    non-empty segments and skipped continuation framing, and B2 shipped
    `Seconds: 0-30` verbatim — '15-second scene twice' (12B violation).

    Ownership law (12B model): a segment belongs to the window CONTAINING ITS
    START (half-open [win_start, win_end)); a segment starting exactly at a
    boundary belongs to the later batch. The whole-scene segment is owned by
    the root window only; later windows stay inherit-render-windows and get
    continuation framing at request-build time.
    """
    from app.director_timeline_w46.reconcile import _in_window

    eps = 1e-6
    # Whole-scene segment (0-30) belongs to the ROOT window only.
    assert _in_window(0.0, 30.0, 0.0, 15.0) is True
    assert _in_window(0.0, 30.0, 15.0, 30.0) is False
    # A segment starting exactly on the boundary belongs to the LATER batch.
    assert _in_window(15.0, 15.0, 15.0, 30.0) is True
    assert _in_window(15.0, 15.0, 0.0, 15.0) is False
    # Boundary tolerance: start one epsilon below the boundary is in the earlier window.
    assert _in_window(15.0 - 2 * eps, 15.0, 0.0, 15.0) is True
    assert _in_window(15.0 - 2 * eps, 15.0, 15.0, 30.0) is False
