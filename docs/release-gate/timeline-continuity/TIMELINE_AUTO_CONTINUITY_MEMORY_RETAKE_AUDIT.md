# TIMELINE AUTO-CONTINUITY + MEMORY RE-TAKE — ARCHITECTURE AUDIT

**Date:** 2026-08-14  
**Branch:** `beta`  
**Status:** APPROVED — READY TO IMPLEMENT  
**Governing for this milestone until the completion report ships.**

Labels: **CONFIRMED** unless marked **INFERENCE** or **PROPOSAL**.

---

## Timeline Architecture

**CONFIRMED.** Root UI is [`TimelineEditorShell.tsx`](../../../studio-web/src/components/timeline-master/TimelineEditorShell.tsx): toolbar, [`DirectorTracks.tsx`](../../../studio-web/src/components/DirectorTracks.tsx), [`TimelinePreviewComposer.tsx`](../../../studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx) → `LivePreviewMonitor`, [`TimelineInspector.tsx`](../../../studio-web/src/components/timeline-master/TimelineInspector.tsx), CompactRenderQueue, TimelineRetakeDrawer, AssetTray.

Backend master: `SceneTimelineMaster` in [`contracts.py`](../../../studio-api/app/director_timeline_w46/contracts.py), persisted inside `scene.director_json` via [`store.py`](../../../studio-api/app/director_timeline_w46/store.py). PUT director merges and preserves `timelineMaster`.

Generation: orchestrator → `TimelineGenerationRequest` → `VideoGeneratorAdapter` registry → per-batch watcher → `apply_shared_completion`.

Do not cite [`docs/release-gate/timeline/TIMELINE_GENERATOR_ARCHITECTURE_AUDIT.md`](../timeline/TIMELINE_GENERATOR_ARCHITECTURE_AUDIT.md) as current truth (2026-08-05 stub era).

---

## Scene and Batch Data Model

**CONFIRMED.** Scene row (`prompt`, `engine`, `duration_sec`) + embedded master. `BatchBlock` is the stable container (`id` never changes). Owns clips, prompts, anchors, jobs, candidates, `approvedClip`.

Duration is `DurationState` (planned / generated / timelineVisible / sourceMedia). Placement uses visible || generated || planned.

**INFERENCE:** scene `duration_sec` is the NLE ruler, not per-batch planned duration.

---

## Track Ownership

**CONFIRMED.** Lanes: image, video, prompt, audio, SFX, camera, lip-sync, batch, repair. Batch-owned clips are authoritative; scene-global tracks are a derived/legacy view. **No Extend track exists and none will be added.**

---

## Local Generation Path

**CONFIRMED.** Registry: MiniMax H3 T2V/I2V, LTX, Seedance API, Kling API, env-gated cert stub. WAN/Hunyuan: dock only, `supportsTimelineGeneration=False`.

MiniMax: Route A `:8192`, `supportsContinuation=False`. LTX dock claims continuation; request builder does not use a video tail today. ffmpeg last-frame extract already exists in `queue_worker._extract_last_frame`.

---

## API Generation Path

**CONFIRMED.** Seedance/Kling are in-memory ledgers; dock `executable=False`. Auto Continuity defaults **Off**. Off forbids background paid continuity work.

---

## Multi-Batch Execution Path

**CONFIRMED.** `orchestratorMode = "sequential_continuity"` means sequential **job** submission (concurrency 1), not visual continuity. Later batches are Queued with staged snapshots. `submit_next_queued_batch` fires on Approved/Failed with **no Continuity Bridge wait**.

---

## Current Re-Take Path

**CONFIRMED.** Two systems:

1. W46 `POST .../batches/{id}/retake` re-submits the same batch; completion auto-approves.
2. MiniMax `timeline_retakes` drawer: baseline/alternate/activate with a delta; shot-scoped.

**PROPOSAL (approved):** one BatchBlock take model with structured memory; drawer becomes a thin UI or is retired.

---

## Inspector / Right Pane Architecture

**CONFIRMED.** Selection-driven stacked fields, not accordions. Scene shows name, prompt, Prompt Intelligence, generator, duration, execution, preflight together.

---

## Persistence and Lineage

**CONFIRMED.** `timelineMaster` in `director_json`. `timelineGenerationLineage` on `batch.references`. Snapshots immutable. New: `ContinuityBridge`, `ContinuityPolicy`, `contextVersion=1`, structured retake memory, `continuityStrategy` actually used.

---

## Risks / Existing Defects

- Sequential mode does not carry frames between batches.
- Auto-approve fights non-destructive Re-Take.
- Two retake stores.
- LTX continuation advertised, unused.
- Watcher can advance the chain after a thrown completion.
- Configured 5s tail on a shorter clip must clamp (`effectiveTailDuration`).

---

## Recommended Extension Points

1. `ContinuityBridge` on master (internal). Extend remains the creator-facing capability.
2. Gate `submit_next_queued_batch` on bridge Ready when Auto Continuity is on.
3. Adapter-declared `continuityStrategy`; persist what was used.
4. Reuse ffmpeg last-frame extract.
5. Structured Re-Take sections on `CandidateVersion`.
6. Inspector accordions only.

---

## READY TO IMPLEMENT or BLOCKED

**READY TO IMPLEMENT.** Continuity is absent by design, not blocked by unknown ownership.

### Frozen contract notes

- `contextVersion = 1`
- `effectiveTailDuration = min(configured, actualGeneratedDuration)`
- Strategies: `native_tail | native_extend | multi_frame | last_frame_i2v | prompt_context | none`
- Re-Take memory: `sequenceMemory`, `incomingContinuity`, `originalTakeIntent`, `takeState`, `userCorrection`
- Future Extend surfaces (1 Frame / 3 Frame / Timeline Generator) share this handoff shape; they are not Timeline tracks
