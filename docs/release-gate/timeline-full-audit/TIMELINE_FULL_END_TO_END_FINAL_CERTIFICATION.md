# Timeline Full End-to-End Audit, Repair & Final Hardening — Final Certification

**Milestone:** ADEPT UI — TIMELINE FULL END-TO-END AUDIT, REPAIR & FINAL HARDENING
**Verdict:** **GO — TIMELINE FULL END-TO-END WIRING CERTIFIED FOR CREATOR MANUAL BETA**
**Date:** 2026-08-07
**Branch:** `feature/ai-guided-setup` (working tree, HEAD `fa09c99`)
**Governing document (Law 30):** This file. Supersedes
`../timeline-multi-batch/TIMELINE_MULTI_BATCH_PREVIEW_FINAL_CERTIFICATION.md`
(marked SUPERSEDED in place).

## 1. Certification philosophy

No automated test executes real GPU video generation. Automated certification proves the
entire Timeline pathway — state, preview, workflow construction, queue, completion, UI,
navigation, server stability — is clean, deterministic, persistent, batch-safe,
provider-safe, preview-safe, and recoverable **up to the provider execution boundary**
(env-gated `StubCertAdapter` + request sink). Live multi-batch GPU generation remains the
**manual creator gate** during Beta review.

## 2. Centerpiece: WORKFLOW_GRAPH_DRIFT root cause and contract split

**Root cause (evidence: `TIMELINE_COMFYUI_WORKFLOW_DRIFT_AUDIT.md`).** The certified
`graphHash` redacted volatile keys (prompt/seed/image/filenames/model names) but hashed
per-job geometry scalars. Empirical diff of two legitimate LTX builds showed exactly six
drifting inputs: `LTXVImgToVideo.width/.height/.length`, `LTXVConditioning.frame_rate`,
`VHS_VideoCombine.frame_rate`, `BasicScheduler.steps`. Every batch whose
duration/resolution/fps/steps differed from the single certified reference build drifted —
**legitimate dynamic substitution incorrectly included in the fingerprint** (Cause class A).

**Repair — topology/bindings split (drift detection never weakened):**
- `video_runtime/fingerprints.py`: `canonicalize_topology` (Weisfeiler-Lehman-style
  canonicalization over node classes + link structure; invariant to node-ID relabeling),
  `topology_hash`, `assert_no_topology_drift`, `validate_dynamic_bindings`
  (type/range/consistency checks for prompt/seed/frames/fps/dims/prefix/LoadImage).
  Legacy `graph_hash` retained for provenance.
- `video_runtime/workflow_execute.py` `prepare_executable_graph`: prefers `topologyHash`,
  falls back to legacy `graphHash` only for unmigrated entries; returns
  `{topologyMatch, bindingsValid, bindingsReport}`. Topology mismatch still **blocks**
  generation with `WorkflowGraphDriftError`; invalid bindings fail fast.
- Registry migration (additive, non-destructive): `fingerprints.topologyHash` computed for
  all 9 offline-buildable video entries; legacy `graphHash` untouched; `image_runtime`
  intentionally out of scope (not implicated; Law 6).
- Developer export (env-gated `ADEPT_TIMELINE_WORKFLOW_EXPORT=1`):
  `POST .../batches/{id}/workflow-export` builds the real request+graph without queueing
  and writes `timeline_<scene>_<batch>_<provider>_{workflow,api,bindings,fingerprints}.json`
  under `data/runtime/exports/`, including the topology/bindings report. Export never
  uploads to ComfyUI.

**Before/after:**

| Job variation | Before (graphHash) | After (topologyHash + bindings) |
|---|---|---|
| prompt / seed / start-image filename | drift (blocked) | topology match, bindings valid |
| duration → frames (5s vs 8s) | drift (blocked) | topology match, framesSnapped differs in bindings |
| resolution / fps / steps | drift (blocked) | topology match, bindings validated |
| node class changed | drift (blocked) | **drift (blocked)** |
| link changed | drift (blocked) | **drift (blocked)** |
| model node missing | drift (blocked) | **drift (blocked)** |
| I2V→T2V downgrade | drift (blocked) | **drift (blocked)** |

## 3. Repairs by area (all verify-as-regression first; only actual defects fixed)

### 3.1 State / persistence (audit: `TIMELINE_STATE_PERSISTENCE_AUDIT.md`)
- **D1/D2 — `timelineMaster` wiped by non-PUT writers:** four backend paths
  (`assistant.apply_scene_setup`, M29 editing/timeline/audio services) used the plain
  `dumps_director_timeline` serializer. All now use
  `dumps_director_timeline_preserving_embedded`; M29 undo/redo snapshots preserve embedded
  keys. Regression: `studio-api/tests/test_w46_embedded_master_preservation.py`.
- **Stale-fetch race:** `TimelineEditorShell.refreshMaster` guarded by a load token so
  superseded responses never overwrite newer state.

### 3.2 Preview Monitor (audit: `TIMELINE_PREVIEW_AUDIT.md`)
- **Video playhead:** Timeline video clips now seek to clip-local time; `onTimeUpdate`
  translates back to global playhead time.
- **Scene-switch leak:** generation preview state resets on `scene.id` change.
- **Failed/cancelled drafts:** `PreviewComposition` carries `previewSrc` for failed and
  cancelled jobs; the monitor renders the last draft frame with a proper overlay
  (cancelled overlay added; empty message lines suppressed).

### 3.3 Queue / completion (audit: `TIMELINE_QUEUE_COMPLETION_AUDIT.md`)
- **Q1 — terminal-status guard:** a late/stale provider failure can no longer clobber an
  Approved/CandidateReady batch.
- **Q2 — watcher resilience:** completion/failure handlers wrapped; exceptions logged and
  the sequential chain still advances (no silent thread death).
- **Q3 — staged-snapshot invalidation:** editing a Queued batch's config clears
  `pendingSnapshotId` and returns it to Ready, so the next submission builds a fresh
  ExecutionSnapshot. Regression: `studio-api/tests/test_w46_queue_hardening.py`.

### 3.4 Generation wiring (audit: `TIMELINE_GENERATION_WIRING_AUDIT.md`)
- **W1/W2 — Generate Current/Selected:** no silent fallback to `batches[0]`; both buttons
  act strictly on the selected batch and are disabled with reasons when none is selected.
- **W3 — capability-driven generator dropdown:** `/generators` now exposes
  `timelineAdapters` (full capability records); the Inspector dropdown is built from live
  capabilities instead of hardcoded entries.

### 3.5 Timeline UX (audit: `TIMELINE_UI_INTERACTION_AUDIT.md` + `TIMELINE_UI_REPAIR_NETWORK_CONSOLE_AUDIT.md`)
- Shared `formatDurationSeconds` (frame-aware `5.00 s`) applied to panel/inspector/repair
  displays — raw `5.004000000000001` floats eliminated.
- `formatBatchStatus` humanizes status enums everywhere; batch clips carry status badges;
  render queue shows human batch labels; all disabled buttons explain why.
- Scroll-aware batch lane windowing (no blank lanes when scrolled away from playhead).
- Clip overlap guard: same-lane moves/trims clamp against neighbors.
- Polling loops visibility-gated; `getTimelineReferences` prefetch debounced (600ms).
- **L1:** misleading "Scene not found" readiness blocker replaced with "Readiness not
  assessed yet — run Co-Director Preflight…".
- **L2:** `/api/codirector/providers/active/health` 500 (`MODEL_NOT_FOUND` NameError)
  fixed — now returns 200 with an accurate degraded payload.
- Network/console audit: **0 Timeline-critical** console errors / failed requests;
  `ERR_NETWORK_CHANGED` bursts classified client-side (see §3.7).

### 3.6 Navigation / workspace memory (audit: `PROJECT_WORKSPACE_ROUTING_AUDIT.md`)
Routing contract implemented and certified:
- Open Project → bare `/project/<id>` landing, **no silent workspace resume**
  (`requested || "home"`; the `loadLastWorkspace` fallback is removed from the default
  path). Resume-last-workspace survives only as the intentional "Continue Production"
  action on the landing page.
- Workspace memory is a **per-project map** (`lastWorkspaceByProject`) — cross-project
  contamination is impossible.
- Stale-render guard: a project switch never renders the previous project's data under the
  new URL; foreign scene selection cannot leak across projects.
- User-initiated workspace switches push history (Back/Forward coherent); only legacy-alias
  canonicalization replaces.
- Playwright `tests/e2e/navigation/project-workspace-routing.spec.ts`: **NAV-1…NAV-7 all
  PASS** (artifact `nav-routing-cert.json`).

### 3.7 Beta server stability (audit: `BETA_SERVER_STABILITY_AUDIT.md`)
- Historical flicker signature = supervisor auto-restart-after-crash (Jul 28/29, Aug 2
  log evidence). Today: zero unintended exits across 8 intentional Stop/Start cycles and
  multi-hour HEALTHY windows.
- **S1:** `_stop_stale_owned` now actually stops stale owned processes + orphaned port
  listeners at startup (previously log-only → port-bind crash-loop risk).
- **S2:** Start script duplicate-supervisor guard — a live supervisor mid-startup is
  attached to, never duplicated.
- **S3:** pid files reconciled to the real port listeners (venv shim re-executes the base
  interpreter); restarts clear lingering listeners before respawn.
- Logging hardened: every service log line timestamped; exits log code+pid; intentional
  shutdowns labelled.
- `ERR_NETWORK_CHANGED`: six unrelated endpoints failed simultaneously while supervisor
  logs show zero restarts — Chrome NetworkChangeNotifier reacting to Windows network-stack
  events (VPN/Parsec/adapters). Client-side, app recovers via retry. Not a server defect.
- **30-minute dual-metric soak (23:02:10Z→23:32:10Z):** 536 health samples,
  **processRestartCount=0 AND failedHealthSampleCount=0** (neither metric substitutes for
  the other) → CONTINUOUSLY HEALTHY. Playwright creator-surface driver: 471 circuits
  (landing, switching, Timeline, Preview, Inspector, Co-Director, save/reload, multi-batch
  authoring, preflight, browser refresh), 0 step failures, 0 Timeline-critical console or
  request failures → SOAK CLEAN. Soak project deleted afterwards.

## 4. Test evidence

| Suite | Result |
|---|---|
| `test_w46_sequential_chain.py` | PASS |
| `test_w46_embedded_master_preservation.py` | PASS |
| `test_w46_queue_hardening.py` | PASS |
| `test_video_runtime_topology_drift.py` (7 mandated categories, 11 tests) | PASS 11/11 |
| `certify_comfyui_preflight.py` (H3 + LTX fingerprint contract) | PASS — READY FOR MANUAL GENERATION, gpuEnqueued=False |
| `timeline-multi-batch-wiring-cert.spec.ts` (incl. new gates Q fingerprint stability, S export artifacts, T console cleanliness) | PASS 14/14 |
| `timeline-multi-batch-preview-monitor-cert.spec.ts` | PASS 10/10 |
| `project-workspace-routing.spec.ts` (NAV-1…7) | PASS 7/7 |
| `timeline-master` web unit tests | PASS 13/13 |
| `workspacePrefs` unit tests | PASS 7/7 |
| `studio-web` typecheck (`tsc -b`) | clean |
| **Independent verifier `scripts/verify_timeline_multi_batch.py`** | **GO — 49/49 gates** (22 wiring + 5 drift contract + 2 UI/console + 9 navigation + 11 stability) |

Artifacts: `docs/release-gate/timeline-full-audit/artifacts/` (soak JSON ×2,
nav-routing-cert.json, network/console audit JSON, UI screenshots) and
`docs/release-gate/timeline-multi-batch/artifacts/` (wiring cert gates A–T).

## 5. Provider readiness

ComfyUI preflight verdict **READY FOR MANUAL GENERATION** (H3 and LTX), fingerprint
contract asserted for both graph builds, no GPU work enqueued by any automated step.
Live multi-batch GPU generation is the creator's manual Beta gate.

## 6. Limitations (honest)

- Real GPU generation, provider latency, and VRAM behavior under load are not covered by
  automated certification (by design); they are the manual Beta gate.
- The Jul 28/29 + Aug 2 crash proximate causes are not recoverable (service logs rotated
  before per-line timestamp hardening); the supervisor hardening makes any recurrence
  observable and non-cascading.
- `ERR_NETWORK_CHANGED` bursts may still appear in the browser during Windows network
  events; they are client-side, transient, and self-healing.

## 7. Manual review path

Beta is running clean (no cert stub, no export env) at:
- Creator UI: http://127.0.0.1:8760/
- Studio API: http://127.0.0.1:8758/ (`/api/health` → 200)

Suggested creator pass: open a project from the selector (lands on the Project page),
Continue Production → Timeline, configure 2–3 batches with different durations/prompts,
Generate Current / Generate Selected, watch the Live Preview Monitor through completion,
approve outputs, reload the browser, and confirm all state persists.

## 8. Final verdict

**GO — TIMELINE FULL END-TO-END WIRING CERTIFIED FOR CREATOR MANUAL BETA**

- Navigation addendum: all 9 navigation gates PASS.
- Stability addendum: all 11 stability gates PASS (dual-metric: 0 restarts AND 0 failed
  health samples over 30 minutes).

---

# Addendum 3 — Live Drift False-Positive Closure (2026-08-08)

## A3.1 Trigger and root cause

After the milestone GO, the Live Preview Monitor again displayed
`WORKFLOW_GRAPH_DRIFT: ltx.simple_i2v@1.0.0 graphHash mismatch`. Investigation
(call-path trace, registry dump, live process inspection, live DB query) proved the
banner was a **stale persisted job message**: three `render_scene` jobs that failed at
2026-08-07 07:19–07:20 UTC — *before* the topology/bindings split was applied — remained
the latest failed jobs for their scenes, and the monitor faithfully re-displayed their
messages. Zero `WORKFLOW_GRAPH_DRIFT` jobs were created after the fix; the running API
process (started after the repairs) provably resolves the topology path.

The drift gate itself was never bypassed or weakened. The residual defects were
**observability** defects:

1. The fingerprint gate's path selection was invisible at runtime — a live failure could
   not explain *why* `graphHash` was selected.
2. The failed-job overlay showed no timestamp, so a hours-old failure looked current.
3. The verifier had no gate binding "zero legacy failures" to the *current* API process
   instance, leaving room for ambiguity with appended historical log lines.

## A3.2 Repairs

| Change | File | Detail |
|---|---|---|
| Fingerprint-path instrumentation | [workflow_execute.py](../../../studio-api/app/video_runtime/workflow_execute.py) | Every `prepare_executable_graph` invocation emits one structured `workflowFingerprint` line (workflow@version, registryEntry, topologyHashCertified, legacyGraphHashCertified, selectedPath, topologyMatch, bindingsValid, legacyGraphHashCheck, reason, all four hashes). Dual-emitted to the app logger and stdout so the supervisor pump timestamps it into `api.log`. |
| Self-explaining legacy drift error | same | If the legacy `graphHash` fallback is ever selected, the raised `WorkflowGraphDriftError` now appends `legacy graphHash selected because: <reason>` (e.g. registry entry has no `fingerprints.topologyHash`). |
| Production-path regression test | [test_queue_worker_drift_gate.py](../../../studio-api/tests/test_queue_worker_drift_gate.py) | Drives the exact QueueWorker sequence (`resolve_from_scene_params` → `build_leaf_graph` → `prepare_executable_graph(enforce_certified_fingerprint=True)`): Batch A (5s/24fps/8 steps) and Batch B (8s/30fps/20 steps, different prompt/seed/start-image/prefix) both PASS via `selectedPath=topology`, `legacyGraphHashCheck=false`; node-addition and link-rewire mutations that survive static validation are BLOCKED with `topologyHash mismatch`; legacy-fallback error message explains its selection reason. 4/4 PASS. |
| Failed-overlay timestamp | [LivePreviewMonitor.tsx](../../../studio-web/src/components/LivePreviewMonitor.tsx), [formatDuration.ts](../../../studio-web/src/lib/formatDuration.ts) | "Render failed" overlay now shows the job's failure time (`formatJobTimestamp`, naive-UTC → creator-local, e.g. "Render failed · Aug 7, 12:20 AM") so stale failures are visibly old. Unit tests 4/4 PASS. |
| Process-instance-bound evidence gate | [verify_timeline_multi_batch.py](../../../scripts/verify_timeline_multi_batch.py) | New `DRIFT_LIVE_EVIDENCE` gate: reads the API listener PID from `data/runtime/beta/pids/api.pid`, resolves the process start timestamp, scans only `api.log` records at/after that start (pump-prefixed ISO timestamps), requires ≥1 `workflowFingerprint … selectedPath=topology topologyMatch=true legacyGraphHashCheck=false` line and asserts **zero** `graphHash mismatch` lines in the interval. |

## A3.3 Live evidence (current API process instance)

```text
[2026-08-08T01:16:32Z] workflowFingerprint workflow=ltx.simple_i2v@1.0.0 registryEntry=true
  topologyHashCertified=true legacyGraphHashCertified=true selectedPath=topology
  topologyMatch=true bindingsValid=true legacyGraphHashCheck=false reason=""
  certifiedTopology=sha256:1bb8b7b4… actualTopology=sha256:1bb8b7b4…
  certifiedGraph=None actualGraph=None
```

Verifier gate on the certification run:
`DRIFT_LIVE_EVIDENCE — apiPid=28828 apiStart=2026-08-08T01:22:27Z intervalLines=960 topologyEvidence=1 legacyGraphHashFailures=0`

## A3.4 Test evidence

| Suite | Result |
|---|---|
| `test_queue_worker_drift_gate.py` (production-path, new) | PASS 4/4 |
| `test_video_runtime_topology_drift.py` | PASS 11/11 |
| Adjacent API suites (m41 certified workflows, w46 queue/chain/master-preservation) | PASS 40/40 combined |
| `formatDuration.test.ts` (new) + timeline-master + workspacePrefs web units | PASS 24/24 |
| `studio-web` typecheck (`tsc -b`) | clean |
| `timeline-multi-batch-wiring-cert.spec.ts` (gates A–T) | PASS 14/14 |
| **Independent verifier** | **GO — 50/50 gates** (49 prior + DRIFT_LIVE_EVIDENCE) |

## A3.5 Final statement

**GO — LIVE TIMELINE WORKFLOW FINGERPRINT PATH USES TOPOLOGY + BINDINGS CONTRACT**

The pre-fix red Preview message is historical evidence of the repaired defect, not a live
failure; the overlay timestamp now makes that visible to creators. Drift detection remains
at full strength: true structural changes block with `WORKFLOW_GRAPH_DRIFT` /
`topologyHash mismatch`, and any future legacy-path selection is self-explaining in both
the log line and the raised error.

Beta is running clean (no cert stub, no export env) at http://127.0.0.1:8760/
(API http://127.0.0.1:8758/ — `/api/health` → 200).

---

# Addendum 4 — Stale-Failure Dismissal Repair (2026-08-08)

## A4.1 Trigger and root cause

With the timestamp fix live, the creator still saw **"Render failed · Aug 7, 9:04 AM"** on
Scene 1 — correctly labeled as stale, but with **no way to clear it**. DB evidence: zero
jobs created or updated after the drift fix; the scene's latest job remained the pre-fix
failure, and the Preview Monitor (by design) pins the scene to its latest terminal failure
until a successful re-render replaces it. The batch itself (`bb_e2414bffafd0`, status
Failed) remained regenerable — `generate_scene` never excludes Failed batches — so the
sole remaining defect was the **missing creator-facing acknowledgment path**: clearing a
read-and-understood failure required a chargeable GPU re-render. That is the confusion
vector that made a historical message look like a live bug.

## A4.2 Repair

| Change | File | Detail |
|---|---|---|
| Master contract field | [contracts.py](../../../studio-api/app/director_timeline_w46/contracts.py) | `SceneTimelineMaster.dismissedFailureJobIds: list[str]` — server-persisted, project-isolated, survives reload. |
| Dismiss service + endpoint | [service.py](../../../studio-api/app/director_timeline_w46/service.py), [router.py](../../../studio-api/app/director_timeline_w46/router.py) | `POST …/dismiss-failure {jobId}` — idempotent append; job row and batch status deliberately untouched (history stays honest). |
| Composer skip logic | [TimelinePreviewComposer.tsx](../../../studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx) | A dismissed failure no longer pins the monitor (falls through to final output / timeline frame); a NEW failure (different job id) re-shows the overlay; the cancelled overlay is never suppressed. |
| Dismiss control | [LivePreviewMonitor.tsx](../../../studio-web/src/components/LivePreviewMonitor.tsx) | Failed overlay gains **Dismiss** ("Clear this failure message and return to the preview — the job history is kept"). |
| Overlay clickability fix | [styles.css](../../../studio-web/src/styles.css) | `.live-preview-overlay` is `pointer-events: none` by design (stage stays interactive); its buttons now re-enable pointer events — without this the Dismiss control was unreachable (found by the new E2E). |
| Cert-only seed endpoint | [router.py](../../../studio-api/app/director_timeline_w46/router.py) | `POST /cert/seed-failed-job` (only mounted with `ADEPT_TIMELINE_CERT_STUB=1`) inserts a terminal failed `render_scene` Job row so E2E can drive the REAL monitor failure path. The stub adapter intentionally never creates Job rows (queue_worker would execute them for real), so stub generation alone cannot reach the failed overlay. |

## A4.3 Test evidence

| Suite | Result |
|---|---|
| `test_w46_dismiss_failure.py` (persist / idempotent / accumulate / validation / default) | PASS 5/5 |
| `TimelinePreviewComposer.test.ts` (dismissed falls through, new failure re-shows, cancelled never suppressed) | PASS 20/20 file total |
| `timeline-multi-batch-wiring-cert.spec.ts` incl. new **gate U** (overlay → dismiss → persists across reload → new failure re-shows) | PASS 15/15 |
| `studio-web` typecheck (`tsc -b`) | clean |
| **Independent verifier** | **GO — 50/50 gates** |

## A4.4 Creator path for the existing stale failure

On Scene 1 of the affected project: click **Dismiss** on the red overlay once — the
monitor returns to the timeline-driven preview immediately and stays cleared across
reloads. The failed batch can then be re-taken at will (select the batch → Generate
Current); ComfyUI is up and preflight remains READY FOR MANUAL GENERATION.

## A4.5 Second-pass review (GLM 5.2) and hardening resolutions

Independent second-pass review returned READY FOR PRIMARY REVIEW with no blocking
issues; all four hardening findings were resolved and re-verified:

| Finding | Resolution |
|---|---|
| LOW — dismissal save touched every batch's `updatedAt` provenance | `save_master` gained `touch_batches: bool = True`; `dismiss_failure` passes `False`. Regression test pins batch timestamps unchanged across a dismiss. |
| LOW — failed-overlay correctness implicitly coupled to `listJobs` ordering | `useGenerationState` now selects the newest terminal job by explicit `created_at` sort — self-contained, order-independent. |
| LOW — cert seed endpoint used a manual session | `cert_seed_failed_job` now uses the request-scoped `Depends(get_db)` session like the other cert endpoints. |
| INFO — dismiss accepted arbitrary job ids | `dismiss_failure` validates the job row (exists for this project+scene, status `failed`); rejects with `JOB_NOT_FOUND` / `JOB_NOT_FAILED`. Tests cover unknown, foreign-scene, and non-failed ids. |

Post-hardening evidence: API suites 23/23 (incl. 7 dismiss tests), web units 20/20,
`tsc -b` clean, wiring cert **15/15** (gate U included), independent verifier
**GO — 50/50 gates**.

## A4.6 Final statement

**GO — STALE FAILURE IS CREATOR-DISMISSIBLE; MONITOR FAILURE PATH CERTIFIED END-TO-END**

Beta is running clean (no cert stub, no export env) at http://127.0.0.1:8760/
(API http://127.0.0.1:8758/ — `/api/health` → 200).
