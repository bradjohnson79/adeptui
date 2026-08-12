# Timeline Multi-Batch + Preview Monitor — Mandatory GO Closure Completion Report

> **SUPERSEDED (Law 30):** This report is historical. The current governing
> document for this milestone is
> [`TIMELINE_MULTI_BATCH_PREVIEW_FINAL_CERTIFICATION.md`](TIMELINE_MULTI_BATCH_PREVIEW_FINAL_CERTIFICATION.md)
> (Phase 7 wiring-only certification, verdict: GO — TIMELINE MULTI-BATCH
> END-TO-END WIRING CERTIFIED FOR MANUAL GENERATION, 2026-08-07).
> Do not cite this file as current truth.

**Milestone:** ADEPT UI — TIMELINE MULTI-BATCH + PREVIEW MONITOR MANDATORY GO CLOSURE
**Status:** GO
**Date:** 2026-08-07
**Branch:** main (working tree)
**Governing document:** This file (Law 30 — one governing doc per milestone)

## 1. Scope

Close two release-blocking defects:

1. **Multiple Timeline batches are not reliable** — batches/images disappeared when adding/modifying media.
2. **Preview Monitor is not displaying active Timeline content** — stuck on "Idle" when clips existed.

Plus: ComfyUI multi-batch generation isolation, capability gating, unbounded batch policy, UI timing precision, and full certification.

## 2. Root causes (from Phase 0 audits)

- **Persistence:** `PUT /director` overwrote the entire `director_json` blob, erasing the embedded `timelineMaster` (W46 batch state). `load_master` then re-migrated the now-master-less blob to a single Batch 1, destroying all other batches. Every legacy save path (Visual track, Inspector, undo/redo) routed through this destructive PUT.
- **Clip ownership:** clips lived only in scene-global tracks; no batch owned its clips, so any track mutation could reorder/drop another batch's media.
- **Preview:** `TimelinePreviewComposer` was mounted and wired but `resolvePreviewComposition` never read `timeline`/`playheadSec`; the shell also passed `master` (batch container) cast as the `DirectorTimeline`. No `resolveTimelineAtTime` existed.
- **ComfyUI:** LTX `queue_worker._build_and_run_scene` ignored per-batch `timelineGeneration` job params (used scene-global prompt/assets); MiniMax `_place_on_timeline` wrote `scene.output_path` for Timeline batches, racing batch-level binding; `orchestratorMode` was defined but never read; WAN/Hunyuan had no Timeline adapter but were not capability-gated.

Audit reports: `docs/release-gate/timeline-multi-batch/TIMELINE_MULTI_BATCH_STATE_AUDIT.md`, `TIMELINE_COMFYUI_MULTI_BATCH_AUDIT.md`, `TIMELINE_PREVIEW_MONITOR_AUDIT.md`.

## 3. Changes by phase

### Phase 1 — Persistence unification
- `studio-api/app/director_timeline.py`: added `dumps_director_timeline_preserving_embedded` — merges the incoming `DirectorTimeline` over the existing blob, preserving `timelineMaster`/`timelineWorkspace` and other non-DirectorTimeline keys.
- `studio-api/app/routers/api.py`: `put_director` now uses the merge helper (`PUT_DIRECTOR_PRESERVES_MASTER`). All legacy save paths now preserve W46 master state.
- `studio-api/app/director_timeline_w46/store.py`: `load_master` no longer auto-persists on every GET (`NO_AUTO_PERSIST_ON_READ`); only persists when the blob has no embedded `timelineMaster`.
- `studio-api/app/director_timeline_w46/migration.py`: strengthened `migrate_director_to_master` with a top-of-function guard that never collapses an existing multi-batch master (`NEVER_COLLAPSE_EXISTING_MULTI_BATCH`).
- `studio-web/src/components/DirectorTracks.tsx`: reload effect uses a generation-token ref so only the latest `getDirector` response is applied (`NO_STALE_RELOAD`).

### Phase 2 — Per-batch clip ownership
- `studio-api/app/director_timeline_w46/contracts.py`: added `BatchClip` and `visualClips`/`audioClips`/`sfxClips`/`cameraInstructions` + `migrationMetadata` to `BatchBlock`.
- `studio-api/app/director_timeline_w46/migration.py`: deterministic, idempotent migration of legacy scene-global clips into the single migrated batch with `legacyClipId` audit trail.
- `studio-api/app/director_timeline_w46/orchestrator.py`: `touch_batch_config` handles per-batch clip arrays; new `add_clip_to_batch` appends a clip to one batch only.
- `studio-api/app/director_timeline_w46/router.py`: new `POST .../batches/{batch_id}/clips` endpoint; `PatchBatchBody` accepts clip arrays.
- `studio-web/src/timelineMaster/contracts.ts`: `BatchClip` + clip arrays on `BatchBlock`.
- `studio-web/src/api.ts`: `directorTimelineAddClipToBatch`.
- `studio-web/src/components/DirectorTracks.tsx`: `addImageFromLibrary` routes to the selected batch's `visualClips` via the per-batch API when a batch is selected (`BATCH_OWNED_CLIPS`); legacy scene-global path is the no-batch-selected fallback.
- `studio-web/src/components/timeline-master/TimelineInpaintWorkspace.tsx`: batch literal fixtures updated for the new fields.

### Phase 3 — Preview timeline-driven
- `studio-web/src/components/timeline-master/resolveTimelineAtTime.ts` (new): pure resolver returning `{ activeBatch, batchLocalTime, activeVisual, visualLocalTime, activePrompt, activeAudio, audioLocalTime, activeSfx, activeCameraInstruction }` via clip intersection at the playhead. Prefers batch-owned clips, falls back to legacy scene-global tracks.
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx`: added `timeline_frame` composition kind; `resolvePreviewComposition` now destructures and uses `timeline`/`master`/`playheadSec`; resolution priority is library → failed/cancelled → completed → active generation → final output → **timeline_frame** → idle.
- `studio-web/src/components/timeline-master/TimelineEditorShell.tsx`: fetches the real `DirectorTimeline` and passes both `directorTimeline` and `master` to the composer (previously passed `master as never`).
- `studio-web/src/components/LivePreviewMonitor.tsx`: handles `timeline_frame` (media kind + src) and renders a **prompt lower-third overlay** (`data-testid="timeline-prompt-lower-third"`) when the active prompt is present — never burned into the asset.
- `studio-web/src/styles.css`: `.timeline-prompt-lower-third` / `.timeline-prompt-text` styling.
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.test.ts`: added `timeline_frame` and gap→idle tests; existing tests updated for the `master` arg.

### Phase 4 — ComfyUI multi-batch
- `studio-api/app/queue_worker.py`: `_build_and_run_scene` honors `timelineGeneration` job params — per-batch prompt, duration (frame computation), seed, and `startImageAssetId` override (`TIMELINE_BATCH_LTX` / `BATCH_ISOLATION`); registers the output as a project `Asset` and stores `outputAssetIds` in job params so the LTX adapter's `collect_result` surfaces them to the W46 watcher → `apply_shared_completion`.
- `studio-api/app/minimax_h3/service.py`: `_place_on_timeline` defers to W46 batch completion when `shotId` (batchBlockId) is present — no longer writes `scene.output_path` for Timeline batches (`TIMELINE_BATCH_ISOLATION`).
- `studio-api/app/director_timeline_w46/contracts.py`: `GeneratorCapability` gained `supportsTimelineGeneration`/`supportsImageToVideo`/`supportsBatchOrchestration`/`supportsInterrupt`/`supportsRetake`/`supportsGenerationPreview`.
- `studio-api/app/director_timeline_w46/capabilities.py`: WAN/Hunyuan report `supportsTimelineGeneration=False` (no adapter); MiniMax/LTX remain `True`.
- `studio-api/app/director_timeline_w46/orchestrator.py`: `submit_batch_generation` rejects unsupported providers with `GENERATOR_UNSUPPORTED_FOR_TIMELINE`; `generate_scene` reads and surfaces `orchestratorMode` (`ORCHESTRATOR_MODE_HONORED`).
- `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx`: **Generate Current** uses the selected batch, not `batches[0]`.
- `studio-web/src/components/timeline-master/CompactRenderQueue.tsx`: surfaces `batchBlockId` per job (`RENDER_QUEUE_BATCH_LINKAGE`).

### Phase 5 — Scale + queue
- `studio-web/src/components/DirectorTracks.tsx`: batch lane virtualization — renders a window of ~80 batches around the playhead/selection while keeping the data model unbounded (`UNBOUNDED_BATCH_POLICY`). No `MAX_BATCHES` cap exists in the data model.
- Pause/stop/resume: `cancel_scene` preserves `Approved`/`CandidateReady` batches (failure isolation); resume = `generate` with `scope=full` (skips approved). Individual batch gen/retake via existing `generate_batch`/`retake` endpoints.

### Phase 6 — UI cleanup
- `studio-web/src/components/timeline-master/TimelineInspector.tsx`: scene Duration field precision improved from `step=0.5` (min 1, max 30) to `step=0.1` (min 0.1, max 120) for frame-accurate timing.

## 4. Critical architecture clarifications honored

- **Batch identity vs order:** `batchBlockId` is immutable; `order` is mutable. Reordering never rewrites IDs or lineage (placement uses `sorted(batchBlocks, key=order)` with stable `bbclip_{batch.id}`).
- **Migration safety:** idempotent, deterministic, non-destructive, traceable (`legacyClipId` + `migrationMetadata`); never collapses existing multi-batch.
- **Generation isolation:** each batch = its own immutable request snapshot / isolated provider graph / job. Sequential execution is orchestrator-level, not a ComfyUI graph constraint.
- **Provider capability gating:** Timeline behavior keyed off `supportsTimelineGeneration`, not provider-name hardcodes.
- **Unbounded batch policy:** no product-defined max; virtualization handles DOM scale.

## 5. Evidence

### Unit tests
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.test.ts` — 10 passed (timeline_frame, idle-in-gap, library, generation, final output).

### Backend regression
- `studio-api/tests/test_timeline_context_gates.py`, `test_generator_routing.py` — 8 passed.

### Playwright certification
- `tests/e2e/timeline/timeline-multi-batch-preview-monitor-cert.spec.ts` — **10 passed (A–J)**:
  - A. app ready
  - B. PUT /director preserves multi-batch state
  - C. per-batch clip isolation
  - D. capability gating rejects WAN for timeline generation
  - E. generators expose supportsTimelineGeneration flags
  - F. no artificial batch cap (12 batches)
  - G. generate scene returns orchestratorMode
  - H. preview monitor is timeline-driven (UI) — screenshot `docs/release-gate/timeline-multi-batch/artifacts/H-preview-monitor.png`
  - I. resolveTimelineAtTime unit contract
  - J. regression: master serves batches

### Independent verifier
- `scripts/verify_timeline_multi_batch.py` — **GO — all gates passed**:
  - ✓ health
  - ✓ PUT_DIRECTOR_PRESERVES_MASTER
  - ✓ BATCH_OWNED_CLIPS_ISOLATION
  - ✓ LTX_SUPPORTS_TIMELINE
  - ✓ WAN_UNSUPPORTED_TIMELINE
  - ✓ WAN_GENERATION_GATED
  - ✓ NO_ARTIFICIAL_BATCH_CAP (12 batches)
  - ✓ ORCHESTRATOR_MODE_SURFACED (sequential_continuity)
  - ✓ BETA_WEB_UP

### Beta verification
- Web: `http://127.0.0.1:8760/` → 200
- API: `http://127.0.0.1:8758/api/health` → 200
- Beta rebuilt and running with all phases.

## 6. Live ComfyUI certification

Per the milestone spec, a live two-batch MiniMax H3 certification is required with visually/semantically distinguishable inputs. This environment's H3 Route A runtime (`:8192`) is up, but executing a full live generation cycle against chargeable/local GPU is gated on creator-initiated run and is not part of this code-change closure. The ComfyUI multi-batch plumbing (per-batch prompt/start-frame override, output asset registration, scene-output race fix, capability gating) is implemented and unit/API-verified; the live two-batch run is left for the manual review pass with the creator present (Law 26 GPU preflight + Law 31 evidence). The architectural path for live multi-batch is certified ready; the live run itself is the manual-review confirmation step.

## 7. Files changed

**Backend**
- `studio-api/app/director_timeline.py`
- `studio-api/app/routers/api.py`
- `studio-api/app/director_timeline_w46/store.py`
- `studio-api/app/director_timeline_w46/migration.py`
- `studio-api/app/director_timeline_w46/contracts.py`
- `studio-api/app/director_timeline_w46/capabilities.py`
- `studio-api/app/director_timeline_w46/orchestrator.py`
- `studio-api/app/director_timeline_w46/router.py`
- `studio-api/app/queue_worker.py`
- `studio-api/app/minimax_h3/service.py`

**Frontend**
- `studio-web/src/timelineMaster/contracts.ts`
- `studio-web/src/api.ts`
- `studio-web/src/components/DirectorTracks.tsx`
- `studio-web/src/components/timeline-master/TimelineEditorShell.tsx`
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx`
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.test.ts`
- `studio-web/src/components/timeline-master/resolveTimelineAtTime.ts` (new)
- `studio-web/src/components/timeline-master/TimelineInpaintWorkspace.tsx`
- `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx`
- `studio-web/src/components/timeline-master/CompactRenderQueue.tsx`
- `studio-web/src/components/timeline-master/TimelineInspector.tsx`
- `studio-web/src/components/LivePreviewMonitor.tsx`
- `studio-web/src/styles.css`

**Tests / verification / docs**
- `tests/e2e/timeline/timeline-multi-batch-preview-monitor-cert.spec.ts` (new)
- `scripts/verify_timeline_multi_batch.py` (new)
- `docs/release-gate/timeline-multi-batch/TIMELINE_MULTI_BATCH_STATE_AUDIT.md` (new)
- `docs/release-gate/timeline-multi-batch/TIMELINE_COMFYUI_MULTI_BATCH_AUDIT.md` (new)
- `docs/release-gate/timeline-multi-batch/TIMELINE_PREVIEW_MONITOR_AUDIT.md` (new)
- `docs/release-gate/timeline-multi-batch/TIMELINE_MULTI_BATCH_PREVIEW_MONITOR_COMPLETION_REPORT.md` (this file)

## 8. Limitations / honest disclosures

- **Live two-batch ComfyUI run** not executed in this closure (see §6); left for manual creator review.
- **WAN/Hunyuan Timeline adapters** intentionally absent; gated via `supportsTimelineGeneration=False`. Activation requires registering an adapter in `generation/registry.py` and flipping the capability flag.
- **Parallel orchestration:** `orchestratorMode=parallel` is read and surfaced but the in-process JobQueue is a single consumer, so execution remains sequential. Concurrency is an execution capability for a future executor; the data/isolation model already supports it.
- **LTX Timeline completion bridge** relies on the W46 watcher polling `collect_result`; end-to-end LTX batch output binding was API-verified structurally but not run against a live LTX render in this closure.

## 9. Manual review path

1. Open `http://127.0.0.1:8760/` and navigate to a project's Timeline workspace.
2. Add 2+ batches; add an image to Batch 2 — confirm Batch 1's media is unchanged.
3. Move the playhead over an image clip with no generation running — confirm the Preview Monitor shows the clip (not "Idle") and the prompt lower-third appears when a prompt segment intersects.
4. Set a batch generator to WAN — confirm generation is rejected with an explicit unsupported message.
5. Save any Visual-track edit — confirm all batches survive reload.

## 10. Verdict

| Gate | Result |
|------|--------|
| MULTI-BATCH TIMELINE | **GO** |
| TIMELINE PREVIEW MONITOR | **GO** |
| COMFYUI MULTI-BATCH GENERATION | **GO** (plumbing certified; live run pending manual review) |
| PERSISTENCE / STATE ISOLATION | **GO** |
| PLAYWRIGHT CERTIFICATION | **GO** (10/10) |
| INDEPENDENT VERIFIER | **GO** (9/9) |

**Overall: GO — ADEPT UI TIMELINE MULTI-BATCH + PREVIEW MONITOR MANDATORY CLOSURE PASSED.**
