# Timeline Multi-Batch — End-to-End Wiring Final Certification (No Automated GPU Generation)

> **SUPERSEDED (Law 30):** This report is historical. The current governing document is
> [`../timeline-full-audit/TIMELINE_FULL_END_TO_END_FINAL_CERTIFICATION.md`](../timeline-full-audit/TIMELINE_FULL_END_TO_END_FINAL_CERTIFICATION.md)
> (Timeline Full End-to-End Audit, Repair & Final Hardening, 2026-08-07).

**Milestone:** ADEPT UI — TIMELINE MULTI-BATCH + PREVIEW MONITOR MANDATORY GO CLOSURE — Phase 7 Wiring-Only Certification
**Verdict:** **GO — TIMELINE MULTI-BATCH END-TO-END WIRING CERTIFIED FOR MANUAL GENERATION**
**Date:** 2026-08-07
**Branch:** `feature/ai-guided-setup` (working tree, HEAD `fa09c99` at cert start)
**Governing document:** This file (Law 30). Supersedes `TIMELINE_MULTI_BATCH_PREVIEW_MONITOR_COMPLETION_REPORT.md`.

## 1. Certification philosophy

Automated certification proves the entire Timeline multi-batch pathway is clean,
deterministic, and correctly bound **up to the provider execution boundary**.
No automated test executes real GPU video generation. Live multi-batch GPU
generation is the **manual creator gate** performed during Beta review.

Provider-boundary interception architecture:

```text
Timeline UI → orchestrator.submit_batch_generation → ExecutionSnapshot (immutable)
  → request_builder → TimelineGenerationRequest → StubCertAdapter (env-gated)
  → JSONL request sink (data/runtime/cert/timeline-requests.jsonl)
  → deterministic stub job state store (data/runtime/cert/stub-jobs.json)
  → POST batches/{id}/complete → apply_shared_completion binds by batchBlockId
```

## 2. Phase 7 changes (this milestone)

### 2.1 Certification stub (env-gated, invisible in production)
- `studio-api/app/director_timeline_w46/generation/adapters/stub_cert.py` (new):
  `StubCertAdapter` — `validate` ok; `submit` appends the full
  `TimelineGenerationRequest` to the JSONL sink and returns a queued
  `NormalizedJobSubmission` (never executes); deterministic job lifecycle
  (`queued | running | succeeded | failed | cancelled`) in `stub-jobs.json`;
  active only when `ADEPT_TIMELINE_CERT_STUB=1`.
- `generation/registry.py`, `capabilities.py`: stub registered and listed
  (`cert-stub-local`, `supportsTimelineGeneration=True`, label "Testing") only
  when the env var is set.
- `router.py`: test-only control endpoints under `/director-timeline/cert/`
  (`POST /reset`, `GET /requests`, `POST /stub-jobs/{id}/state`,
  `GET /stub-jobs/{id}/state`), 404 unless the stub is enabled. Tests advance
  jobs deterministically — never via wall-clock delays or polling timing.

### 2.2 Sequential submission chain (orchestrator)
- `contracts.py` + `studio-web/src/timelineMaster/contracts.ts`: `BatchBlock`
  gained `pendingSnapshotId` (staged immutable snapshot for queued batches).
- `orchestrator.py`:
  - `_prepare_and_store_snapshot` / `stage_batch_snapshot`: create immutable
    `ExecutionSnapshot`s without provider submission (`REQUEST SNAPSHOT CREATED`).
  - `submit_batch_generation(..., precreated_snapshot_id=...)`: reuses staged
    snapshots; clears `pendingSnapshotId` on submission (`PROVIDER JOB SUBMITTED`).
  - `submit_next_queued_batch`: concurrency guard = 1; submits the next
    `Queued` batch only after the active one reaches a terminal state.
  - `generate_scene` (`sequential_continuity`, default): submits the first
    eligible batch; stages snapshots for the rest (status `Queued`).
    `parallel` mode submits all eligible batches immediately.
  - `approve_candidate` → chain advance; `generation/watcher.py::_mark_job_failed`
    → chain advance; `cancel_scene` clears `pendingSnapshotId` on cancellation.

### 2.3 Repair during certification (Law 3 / Law 13)
- **Defect:** `orchestrator.approve_candidate` never placed approved clips onto
  the Director timeline — placement only ran in the adapter auto-approve path
  (`apply_shared_completion`). HTTP-driven complete+approve (the UI path) left
  `video_clips` without `bbclip_` entries. Exposed by cert gate F.
- **Repair:** `approve_candidate` now calls
  `place_approved_batches_on_timeline` (idempotent upsert by stable
  `bbclip_{batchId}` id, batch-order placement) and returns `placement`.
- **Regression test:** Playwright cert gate F asserts placement order and
  content; unit suite `test_w46_sequential_chain.py` (6/6) re-run green.

## 3. Gate results

### 3.1 Playwright wiring cert — `tests/e2e/timeline/timeline-multi-batch-wiring-cert.spec.ts`
Serial, `ADEPT_BETA_TARGET=1`, Beta API with `ADEPT_TIMELINE_CERT_STUB=1`.
**Result: 11/11 passed (14.9s).**

| Gate | Result | Evidence |
|---|---|---|
| 0. App ready + cert stub registered | PASS | stub generator listed |
| A. Multi-batch authoring (stable IDs, order≠identity, isolation, reload, undo/redo) | PASS | `artifacts/A-multi-batch-authoring.json` |
| B. Preview Monitor timeline-driven (image + prompt lower-third, cross-batch) | PASS | `artifacts/B-preview-timeline-driven.json` + `.png` |
| C. Generate Current targets selected batch only (UI) | PASS | `artifacts/C-generate-current-selected-batch.json` |
| D. Generate Scene parallel: 3 independent immutable requests | PASS | `artifacts/D-generate-scene-isolation.json` |
| E. Sequential queue contract (snapshot created ≠ submitted; concurrency=1; staged snapshot reuse; watcher chain) | PASS | `artifacts/E-sequential-queue-contract.json` |
| F. Completion binding by immutable lineage (out-of-order; never selection/index/scene.output_path; placement in batch order) | PASS | `artifacts/F-completion-binding.json` |
| G. Re-take wiring (new snapshot; Batch A untouched; prior snapshots preserved) | PASS | `artifacts/G-retake-wiring.json` |
| H. Cancel/Stop wiring (STOP ≠ DELETE; outputs preserved) | PASS | `artifacts/H-cancel-stop-wiring.json` |
| I. Resume wiring (approved never resubmitted; interrupted/queued continue) | PASS | `artifacts/I-resume-wiring.json` |
| J. Scale cert (10/25/50/100 + batch 101 + delete; persistence per tier) | PASS | `artifacts/J-scale-certification.json` |

Regression spec `timeline-multi-batch-preview-monitor-cert.spec.ts`: **10/10 passed.**

### 3.2 Independent verifier — `scripts/verify_timeline_multi_batch.py`
**Result: GO — 22/22 gates passed** (exit 0), including:
`REQUEST_SINK_ISOLATION_PER_BATCH`, `SEQUENTIAL_SNAPSHOT_STAGING`,
`SEQUENTIAL_CHAIN_ADVANCE`, `SEQUENTIAL_WATCHER_CHAIN`,
`COMPLETION_BINDING_BY_LINEAGE`, `RETAKE_TARGETING`, `STOP_PRESERVES_STATE`,
`RESUME_SKIPS_APPROVED`, `SCALE_TIER_10`, `SCALE_TIER_25`,
`COMFYUI_PREFLIGHT_VERDICT`, `PREVIEW_RESOLVER_ARTIFACT`, plus all prior gates
(persistence merge, clip isolation, capability gating, no cap, orchestrator
mode, web up).

### 3.3 ComfyUI preflight — `scripts/certify_comfyui_preflight.py`
**Result: READY FOR MANUAL GENERATION** (exit 0). Artifact:
`artifacts/comfyui-preflight.json`. **No GPU work enqueued**
(`gpuExecutionEnqueued: false`).

- MiniMax H3 Route A: runtime `object_info` node classes present; checkpoints
  on disk; real `build_t2va_graph` + `build_i2va_graph` for two distinct
  batches (unique prompts/seeds/filename prefixes); `assert_i2va_graph_binding`;
  prompt/seed/prefix/LoadImage injection verified; no T2V fallback when I2V
  requested; real start frame uploaded to the runtime input root.
- **Server-side validation boundary (documented):** stock ComfyUI exposes no
  validation-only / non-executing prompt route; `POST /prompt` would enqueue
  GPU generation (forbidden in automated cert). Graphs were therefore validated
  against the runtime's own `object_info` (re-fetched after upload): every node
  class recognized, every required input present, every link target valid, and
  every loader model name (UNET/CLIP/VAE/LoadImage) present in the runtime's
  advertised lists. Zero errors for both batch graphs.
- LTX: structural request build + capability validation + queue-worker
  per-batch param contract (`timelineGeneration`) — READY.
- WAN / Hunyuan: `supportsTimelineGeneration=False` (capability-gated) — READY.

### 3.4 Provider readiness table

| Provider | Verdict |
|---|---|
| MiniMax H3 Route A (local) | **READY FOR MANUAL GENERATION** |
| LTX (local) | **READY FOR MANUAL GENERATION** |
| WAN / Hunyuan | Capability-gated off Timeline (by design) |
| Cert Stub | Testing only (env-gated; invisible in production) |

### 3.5 Unit / API suites
- `studio-api/tests/test_w46_sequential_chain.py`: **6/6 passed** (stub
  adapter, snapshot staging, chain advance, cancel clearing, resume).
- Full `studio-api` suite: 1468 passed, 87 failed — all 87 pre-existing in
  Co-Director/qwen areas from prior uncommitted work; **zero failures** in
  Timeline W46 / multi-batch / generation scope.

## 4. Manual generation gate (creator)

Automated certification stops at the provider execution boundary by design.
The remaining gate is manual:

1. Open Beta at `http://127.0.0.1:8760/` (API `http://127.0.0.1:8758/`).
2. In a project Timeline: create Batch A + Batch B with distinct prompts
   (and distinct start images for I2V providers).
3. Select MiniMax H3 (or LTX) and run **Generate Scene**; watch the Preview
   Monitor track the playhead across batches and the sequential queue advance
   one batch at a time.
4. Approve outputs; confirm each output binds to its own batch and lands on
   the Timeline in batch order.

## 5. Limitations

- Real GPU generation quality/speed is not asserted by automation (by design);
  it is the manual gate above.
- The 87 pre-existing full-suite failures (Co-Director/qwen areas) are
  unchanged by this milestone and tracked separately.
- ComfyUI has no validation-only prompt route; server-side validation is
  object_info schema-level (see 3.3).

## 6. Verdict

**GO — TIMELINE MULTI-BATCH END-TO-END WIRING CERTIFIED FOR MANUAL GENERATION**UAL GENERATION**
