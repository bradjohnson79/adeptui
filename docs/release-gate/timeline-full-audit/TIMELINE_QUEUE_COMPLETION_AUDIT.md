# Timeline Queue & Completion Audit

- **Date:** 2026-08-07
- **Auditor:** Read-only subagent (GLM 5.2)
- **Scope:** State-transition integrity, stop/resume boundaries, retake isolation, failure isolation, out-of-order completion binding, sequential-chain edge cases.
- **Method:** Read code end-to-end. No repo/DB/service mutation. Runtime-only items marked `NEEDS RUNTIME VERIFICATION`.
- **Verdict scope:** Findings only. No GO/NO-GO. Final certification belongs to the primary agent.

## Per-Area Verdict Table

| # | Area | Verdict | Evidence |
|---|------|---------|----------|
| 5 | Authoring vs Execution separation; Stop never deletes authored data | **OK** | `orchestrator.py:584-661`, `contracts.py:204-243` |
| 6 | Resume never regenerates approved/completed unless explicitly requested | **OK** | `orchestrator.py:637-642`, `orchestrator.py:929` |
| 7 | Retake affects only Batch N; prior snapshots preserved | **OK** | `router.py:309-321`, `orchestrator.py:183-360` |
| 8 | Failure in Batch N does not corrupt N-1/N+1 | **DEFECT** (watcher clobber) | `watcher.py:95-124` |
| 9 | Out-of-order completion binds by batchBlockId lineage | **OK** | `completion.py:178-226` |
| 10a | Approve-fails edge case | **DEFECT** (unhandled exception stalls chain) | `orchestrator.py:443-452`, `watcher.py:44-70` |
| 10b | Watcher fires for unknown job | **OK** (silent no-op) | `watcher.py:95-119` |
| 10c | generate_scene while a batch is Generating (concurrency guard) | **OK** | `orchestrator.py:932-933,936-944` |
| 10d | Double-submission risk in submit_next_queued_batch | **NEEDS RUNTIME VERIFICATION** | `orchestrator.py:852-887` |
| 10e | pendingSnapshotId staleness after config edits on a Queued batch | **DEFECT** | `orchestrator.py:455-537`, `orchestrator.py:852-887` |

## Defect Details

### DEFECT-Q1 — `_mark_job_failed` clobbers already-terminal (Approved/CandidateReady) batch status

- **Root cause:** The watcher's failure path unconditionally sets `batch.status = "Failed"` and `job.status = "failed"` without checking whether the batch already reached a terminal `Approved`/`CandidateReady` state via another path (HTTP approve, auto-approve). The completed path has an idempotency guard (`completion.py:54-68`); the failed path has none.
- **File:line:** `studio-api/app/director_timeline_w46/generation/watcher.py:95-119`
- **Severity:** High. Scenario: a batch is approved via HTTP (`router.py:208-216`) while the watcher thread is still polling. If the provider subsequently reports a transient/stale `failed` status (or the watcher timeout fires `TIMELINE_GEN_TIMEOUT` at `watcher.py:75-85`), `_mark_job_failed` overwrites `Approved` -> `Failed`. The approved clip and `bbclip_` timeline placement are not deleted, but the batch status now lies — `Failed` while a playable approved clip exists. Violates Build Laws #8 (no silent behavior), #10 (persistence survives reload), #18 (one source of truth).
- **Fix direction:** Guard `_mark_job_failed` against already-terminal batches: `if batch.status in ("Approved", "CandidateReady"): return`. Also skip jobs already `completed`/`cancelled`.

### DEFECT-Q2 — Unhandled exception in approve/placement path kills the watcher thread and stalls the chain

- **Root cause:** `approve_candidate` calls `place_approved_batches_on_timeline` and `submit_next_queued_batch` outside any try/except. The watcher's `_run` wraps `adapter.get_status` in try/except (`watcher.py:38-42`) but the terminal-status branch (`watcher.py:44-70`) only has a `finally` to close the DB — no `except`. If `apply_shared_completion` (-> `approve_candidate` -> placement -> chain) raises, the exception propagates out of `_run` and the daemon thread dies silently. The batch is left `Approved` (saved at `orchestrator.py:440-442` before placement) but placement may be incomplete and the next Queued batch is never submitted.
- **File:line:** `studio-api/app/director_timeline_w46/generation/watcher.py:44-70`; `studio-api/app/director_timeline_w46/orchestrator.py:443-452`
- **Severity:** Medium-High. On retry (re-approve via HTTP), `place_approved_batches_on_timeline` is idempotent (upsert by `bbclip_` id, `completion.py:214-223`) and would recover. But the sequential chain (`submit_next_queued_batch`) is never called when the exception fires, so subsequent Queued batches stall until manual action. The watcher thread is a daemon and dies silently — no error surfaced to the creator. Violates Laws #11 (failure recovery) and #8 (no silent behavior).
- **Fix direction:** Wrap the terminal-status branch in try/except; on exception, surface the error and still attempt `submit_next_queued_batch` so the chain advances. Or move `submit_next_queued_batch` into a `finally`.

### DEFECT-Q3 — Staged `pendingSnapshotId` goes stale when a Queued batch's config is edited

- **Root cause:** `touch_batch_config` updates the batch's live config (label, generatorId, plannedDuration, promptSegments, sourceAnchors, references, repairRanges, owned clips) and recomputes `configFingerprint`, but does NOT invalidate or regenerate `pendingSnapshotId` when the batch is `Queued`. The staged `ExecutionSnapshot` remains the one built from the OLD config at `stage_batch_snapshot` time. When the sequential slot frees, `submit_next_queued_batch` reuses the stale snapshot via `precreated_snapshot_id`.
- **File:line:** `studio-api/app/director_timeline_w46/orchestrator.py:455-537` (no pendingSnapshotId handling); `orchestrator.py:852-887` (reuses stale id); `orchestrator.py:246-261` (reuses snapshot without re-validation).
- **Impact (verified by reading `request_builder.py:10-95`):**
  - The provider REQUEST is built from the LIVE batch — so the provider executes the NEW config. The output is what the creator expects.
  - The immutable PROVENANCE record (`ExecutionSnapshot`) reflects the OLD config: `compiledPrompts`, `duration`, `sourceAnchors`, `selectedGenerator`, `providerId`, `runtime` are stale. The candidate's `executionSnapshotId` and `approvedClip.executionSnapshotId` point to this stale snapshot.
  - Result: **provenance integrity violation.** Lineage claims the output came from config A, but it was produced from config B. If the creator changed `generatorId` (e.g., LTX -> MiniMax H3) while Queued, the snapshot says LTX but the job ran on MiniMax H3.
  - Worse case: if the creator changes `generatorId` to a `supportsTimelineGeneration=False` generator (e.g., `wan-local`) while Queued, `submit_batch_generation` rejects with `GENERATOR_UNSUPPORTED_FOR_TIMELINE` (`orchestrator.py:217-223`), `submit_next_queued_batch` returns `submitted: False`, and the batch stays `Queued` with a stale snapshot and unsupported generator — **stuck state**, chain stalls.
- **Severity:** High. Violates immutable provenance, Law #8 (no silent behavior), Law #18 (one source of truth). The `configFingerprint` on the batch (updated) disagrees with the snapshot's implied fingerprint, but nothing detects the disagreement.
- **Fix direction:** In `touch_batch_config`, when `batch.status == "Queued"` and the fingerprint changed, either (a) clear `pendingSnapshotId` and reset status to `Ready`/`Draft` so the next Generate Scene re-stages a fresh snapshot (safer — preserves immutability; old snapshot stays as an orphan audit record), or (b) regenerate the staged snapshot in place. Also re-validate `generatorId` capability gating on edit.

## Confirmations

### C-Q1 — Stop never deletes authored data (Authoring vs Execution separation)

- `orchestrator.py:584-661` `cancel_scene`: every action mutates only `batch.status`, `batch.pendingSnapshotId`, and `job.status` — never `promptSegments`, `sourceAnchors`, `references`, `repairRanges`, `visualClips`/`audioClips`/`sfxClips`/`cameraInstructions`, `candidateVersions`, or `approvedClip`.
- `orchestrator.py:597-604`: `Approved`/`CandidateReady` batches are preserved for `stop_remaining_scene_jobs`, `preserve_completed_batches`, `resume_incomplete_only`, `cancel_pending_batch`.
- `orchestrator.py:627-636` `stop_remaining_scene_jobs`: only `Queued`/`Generating`/`Ready`/`Draft` are set to `Cancelled` and `pendingSnapshotId` cleared; completed outputs are explicitly preserved.
- `contracts.py:204-243`: authored fields are independent of execution fields; `pendingSnapshotId` is documented as a transient staging pointer (`contracts.py:240-243`).

### C-Q2 — Resume never regenerates approved/completed unless explicitly requested

- `orchestrator.py:637-642` `resume_incomplete_only`: only `Cancelled`/`Failed` reset to `Ready`; `Approved`/`CandidateReady` preserved.
- `orchestrator.py:929` `generate_scene` scope `full`: skips `Approved`/`CandidateReady` — never regenerated unless explicitly selected.
- `orchestrator.py:932-933`: `Generating` batches skipped (no double-submit).
- `completion.py:54-68`: idempotency — re-completion for an already-`Approved` batch only re-runs placement.

### C-Q3 — Retake affects only Batch N; prior snapshots preserved

- `router.py:309-321`: `retake_batch` calls `submit_batch_generation` with NO `precreated_snapshot_id`, so a NEW snapshot is built (`orchestrator.py:252-261`).
- `orchestrator.py:178-180`: `master.executionSnapshots[snap.id] = snap` only adds a new entry — prior snapshots never overwritten or deleted.
- `router.py:320`: explicitly returns `priorSnapshotsPreserved = True`.
- Retake targets only the requested `batch_id`; no other batch touched.

### C-Q4 — Failure isolation (modulo DEFECT-Q1)

- `watcher.py:95-119`: scopes mutation by `batch_id` and `executionSnapshotId` — only the matching batch/jobs touched. N-1 and N+1 not iterated.
- `watcher.py:120-124`: after marking failed, calls `submit_next_queued_batch` to advance the chain — N+1 submitted, not skipped.
- `orchestrator.py:852-887`: picks only the lowest-order `Queued` batch; a `Failed` N does not re-submit itself.
- Caveat: see DEFECT-Q1 — the failure path can clobber an already-Approved batch but does not corrupt *other* batches' data.

### C-Q5 — Out-of-order completion binds by batchBlockId lineage

- `completion.py:178-226`: iterates `sorted(master.batchBlocks, key=lambda b: b.order)` — placement order is batch `order`, NOT completion order.
- `completion.py:214`: `clip_id = f"{managed_prefix}{batch.id}"` — stable id keyed by immutable `batchBlockId`, not completion index or `scene.output_path`.
- `completion.py:202`: manual (non-`bbclip_`) clips preserved; only `bbclip_`-prefixed clips replaced.
- `completion.py:49-51`: batch lookup by `batch_id`, never by index.
- `completion.py:54-68`: idempotency keyed by `assetId` + `executionSnapshotId` + `status`.
- `orchestrator.py:416-452` `approve_candidate`: candidate lookup by `candidate_id`; `approvedClip.executionSnapshotId = cand.executionSnapshotId` — lineage bound to the producing snapshot.

### C-Q6 — Concurrency guard: generate_scene while a batch is Generating

- `orchestrator.py:932-933`: eligible-batch filter skips any `Generating` batch.
- `orchestrator.py:936-944`: if `any_generating` is true AND sequential mode, ALL eligible batches (including idx 0) route to `stage_batch_snapshot` (status `Queued`) — enforces concurrency = 1 even mid-flight.
- `orchestrator.py:868-869` `submit_next_queued_batch`: returns early (`generation_in_progress`) if any batch is `Generating`.

### C-Q7 — Watcher fires for unknown job -> silent no-op (no corruption)

- `watcher.py:28-30`: if the adapter can't be resolved, the watcher returns without touching any batch.
- `watcher.py:95-113` `_mark_job_failed`: loads master, finds batch by `batch_id`; if `not batch`, returns silently. Unknown job -> no batch mutation.
- `watcher.py:115-118`: only jobs whose `executionSnapshotId` matches are marked `failed` — no cross-batch contamination.

## Items Needing Runtime Verification

- **Q-RT1 (10d):** Double-submission race in `submit_next_queued_batch`. The guard at `orchestrator.py:868-869` checks `any(b.status == "Generating")` then calls `submit_batch_generation` which loads master fresh (`orchestrator.py:194`) and submits without re-checking. In sequential mode (concurrency=1) only one watcher completion fires at a time, so the race window is narrow. But two concurrent callers (HTTP `approve_candidate` at `router.py:208` AND watcher auto-approve at `completion.py:102`) could both call `submit_next_queued_batch`. `apply_shared_completion` idempotency (`completion.py:54-68`) guards the double-approve path, but the double-`submit_next` path is not idempotency-guarded. Static read cannot prove the race is unreachable; needs runtime/concurrency verification.
- **Q-RT2:** Whether the watcher timeout (1200s default, `watcher.py:23`) interacts correctly with long MiniMax H3 / LTX jobs was not exercised — needs a live runtime run.
