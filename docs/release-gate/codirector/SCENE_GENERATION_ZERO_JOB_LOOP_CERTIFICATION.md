# Co-Director Scene Generation 0/0 Loop — Repair Certification

**Status:** FINAL — see Verdict
**Date:** 2026-08-18
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`

---

## 1. Root Cause (proven, live evidence)

The 0/0 loop was not a cosmetic spinner issue — it was four coupled defects:

| # | Defect | Evidence |
|---|--------|----------|
| 1 | **Zero-jobs handler result was treated as RUNNING.** `scene_generate.handle` returned `{job_ids: [], child_jobs: []}` with no status for zero parsed shots; `dispatcher._dispatch_capability_handler` unconditionally set `status = QUEUED` and published `EXECUTION_STARTED(total=0)` | Live repro `83fe6e1b`: `queued`, 0 children, no error; two pre-existing stuck packs `3f47e96a` + `591a8778` (user's live repro) in the same state |
| 2 | **`advance` had no zero-children branch** — the loop iterated nothing, `any_changed` stayed false, the pack stayed QUEUED forever | 3 consecutive advances on `83fe6e1b` returned `queued`/0 with no transition |
| 3 | **Reload rehydrated the phantom.** `getActiveExecution` returned the latest non-terminal pack (zero-job QUEUED) and the frontend hydrated it as the active execution — the 0/0 surface reappeared on every reload | `active/latest` returned `83fe6e1b` queued/0; CoDirectorSession rehydrated non-terminal packs without a zero-job guard |
| 4 | **Cancel did nothing on zero jobs** (`any_cancelled` stayed false) and the surface rendered a spinner for any queued/running pack regardless of job count | `cancel_execution` code path; `AgentWorkSurface` header logic |

Secondary: `scene_generate.handle` referenced an undefined `scene_id` in its production-event call (NameError swallowed → `generation_started` was never recorded — orphan-event hygiene violated).

## 2. Fixes

### Backend
- `scene_generate.handle`: added `scene_id` param (NameError fixed); **zero parsed shots → terminal contract** `{status: "failed", accepted: 0, rejected: 0, error: "No valid scene-generation jobs were created…"}` + `scene_creator.generation_failed` event; success path returns `status: queued|failed` + accepted/rejected counts + `generation_started` event with counts.
- `dispatcher._apply_handler_result` (shared by dispatch + approve paths): zero child jobs ⇒ **plan FAILED** with the error (never QUEUED); no `EXECUTION_STARTED` for zero-job results (a failure event is published instead); stores `plan_data.accepted/rejected/jobIds/retryContext`.
- `advance.heal_zero_job_plan`: any non-terminal zero-child plan is terminally failed ("Scene generation could not start. No valid shots were queued.") — used by advance, active-latest, and cancel paths. Self-heals all pre-fix strays.
- `cancel_execution`: zero children ⇒ immediately CANCELLED (phantom cancel).
- `pack_store.get_active_execution_for_project`: heals EVERY zero-child non-terminal pack before returning the latest genuinely-active execution — reload can never surface a phantom.

### Frontend
- `AgentWorkSurface`: pure `sceneGenerationPhase` (phantom/preparing/queuing/running/terminal), `pollerShouldRun` (never polls zero jobs), `sceneGenerationProgressText` (Phase 18 copy). Phantom generation renders the terminal empty state ("Scene generation could not start." + Retry + Dismiss), never `0 / 0` with a spinner. Retry starts a FRESH transaction from `retryContext`.
- `CoDirectorSession`: hydration skips non-terminal zero-child packs; SSE attach skips zero-job non-terminal events.

## 3. Live verification (Schnick Coffee, live Beta)

| Check | Result |
|-------|--------|
| Fresh zero-shot dispatch | `failed`, 0 children, clear error (was: `queued` 0/0 forever) |
| Advance on the failed plan | stays `failed` (terminal) |
| Pre-fix stuck packs `3f47e96a`, `591a8778` | healed to `failed` |
| All 9 phantom packs in the project | terminal `failed` |
| `active/latest` | `{"execution": null}` (no rehydration of phantoms) |
| 10x soak (5 zero-shot / 5 valid) | 10/10 correct; zero 0/0 non-terminal states |
| Live /co-director page, real active pack | "SCENE GENERATION · Queuing 1 shot…" (never 0/0) |
| Live /co-director page, zero-job scenario | no surface, no spinner, no 0/0 |
| Request stability | 0 advance calls in phantom states; 9 advance calls over 25s for a REAL job (3s interval, bounded at 80 attempts) — no storm |
| Runtime-unavailable (all enqueues fail) | plan terminal `failed` (unit test) |

## 4. Tests

- Backend: `studio-api/tests/test_scene_generation_zero_job_loop.py` — 9 tests (zero-job dispatch terminal; empty result without status terminal; partial accepted/rejected counts; handler zero-shots contract; advance heal; cancel phantom; active-latest no-phantom; runtime-unavailable; event lifecycle no-orphan-start). All pass. Existing suites: `test_execution_work_surface_api.py`, `test_engine_ownership.py`, `test_scene_batch_approval_gate.py`, `test_codirector_execution_confirmation.py` — 80 passed, no regressions.
- Frontend: `AgentWorkSurface.test.ts` — 13 tests incl. new ZERO-JOBS LAW block (PLANNING allowed, RUNNING+[] → phantom, poller never runs with zero jobs, 0/1 → 1/1, 0/8 → 8/8, phantom copy never 0/0). All pass (282 CoDirector tests pass).
- Playwright (live Beta, actual Co-Director route): `tests/e2e/codirector/scene-generation-zero-job.spec.ts` — 4/4 pass (zero-shot terminal; valid shots → real jobs; reload no-phantom; live UI no 0/0 spinner).

## 4b. Chat vs Scene Generation separation (Phase 25)

A chat request pending is a separate state machine from scene generation pending.
The Co-Director chat (Kie Gemini, degraded in this environment) timing out produces a
chat error/fallback — it never publishes `EXECUTION_STARTED`, so it never opens the
Scene Generation surface. The only surface trigger is a real execution event, and a
zero-job execution is now terminal before any event is published. Verified: the CD
chat call times out with no execution pack created.

## 5. Multi-reviewer matrix (Phase 28/29)

Independent review reports: `.runtime/zero_job/REVIEWER_[A-D].md`.

| Reviewer | Scope | Verdict |
|----------|-------|---------|
| A — Frontend state machine | render/poller/hydration/SSE/retry paths; ZERO-JOBS LAW unit tests (re-ran AgentWorkSurface.test.ts: 13/13 pass) | **PASS** — "0 / 0 + active spinner in a non-terminal state" unreachable |
| B — Backend lifecycle | dispatch terminality (both dispatch + approve paths), advance heal once + idempotent terminal advance, cancel zero-children, active/latest heal + project scoping, event lifecycle (EXECUTION_STARTED only in 4 gated sites; every start has a terminal counterpart), 9 contract tests | **PASS** — all six checks (a–f) hold. Non-blocking follow-up flagged: `events.py:278` bridges job events under category `execution_pack` while pack_store writes `codirector_execution` (pre-existing best-effort SSE bridge mismatch, out of 0/0 scope) |
| C — Playwright evidence | spec truly reproduces the bug (code-verified vs pre-fix `17df308^`: 3/4 tests FAIL pre-fix), post-fix assertions close the loop, screenshots attributable to fixed build | **PASS** |
| D — Request stability | poller never loops on empty job list; chained setTimeout (no stacking); 80-attempt budget; measured 0 advance calls (phantom) / 9 in 25s (real job); backend heal publishes one event | **PASS** |

Evidence gaps raised by C were closed in-session: the 4/4 Playwright run was re-executed and retained at `artifacts/zero-job/playwright-retained-run.json` (4 expected, 0 unexpected, 0 flaky). Post-restart soak retained at `.runtime/zero_job/soak-post-restart.json` (4/4: 2 zero-shot → failed+advance-stable, 2 valid → queued with children; active/latest → real pack, no phantom).

## 6. Final independent scorecard (Phase 29)

| # | Field | Result | Evidence |
|---|-------|--------|----------|
| 1 | Root Cause Proven | PASS | Doc §1; live repro `83fe6e1b` (queued/0 pre-fix); Reviewer C code-verified pre-fix behavior |
| 2 | Planning State | PASS | `preparing` allowed with 0 jobs only pre-enqueue (defensive; backend never persists PREPARING); Reviewer A |
| 3 | Zero Jobs Terminal | PASS | Live: zero-shot → `failed` (post-restart repro `7262d106` + soak); advance stays failed |
| 4 | Backend Lifecycle | PASS | Dispatcher/advance/cancel/pack_store contracts; 9 new tests + 80 execution regressions green (re-verified 2026-08-19) |
| 5 | Polling Stops | PASS | `pollerShouldRun` false for zero jobs; MAX 80; terminal stops chain; Reviewer D |
| 6 | Cancel | PASS | zero children → CANCELLED immediately (unit test); user-facing cancel guarded by flags |
| 7 | Retry | PASS | `handleRetry` → fresh `startExecution` with `retryContext`, never reuses stale pack; Reviewer A (d) |
| 8 | Reload | PASS | `active/latest` heals zero-child packs; hydration skips them; Playwright test 3 |
| 9 | Project Isolation | PASS | Live: zero-shot on 42dcee6d → failed; Schnick active/latest unaffected (its own pack); per-project scoping in pack_store/dispatcher |
| 10 | Co-Director Path | PASS | Real `start_execution` → dispatch → handler chain (same as CD deterministic path, matches stuck packs' `classifier_source: deterministic`); Playwright on real /co-director route |
| 11 | Runtime-Unavailable Path | PASS | Unit test: all children enqueue-fail → terminal failed |
| 12 | Playwright | PASS | 4/4, retained JSON report (re-run after API restart) |
| 13 | 10x Soak | PASS | 10/10 pre-restart (5 zero-shot → failed, 5 valid → queued) + 4/4 post-restart retained soak |
| 14 | Request Stability | PASS | Measured 0 advance calls in phantom state, 9 over 25s real job (3s cadence); Reviewer D |
| 15 | Live Schnick | PASS | Post-restart repros on Schnick Coffee; screenshots artifacts/zero-job/*.png; live page "Queuing 1 shot…", never 0/0 |

## 7. Git

Branch: `feat/scene-generation-zero-job-fix` @ `a26f02f` (pushed to origin; base = already-pushed `feat/scene-creator-mini-production-fidelity` @ `aa6b72b` — parallel movement-segments work excluded from this branch's ancestry). Two commits: `f327a4b` (fix, 12 files) + `a26f02f` (docs).

## Verdict

**GO — CO-DIRECTOR SCENE GENERATION 0/0 LOOP FIXED AND CERTIFIED**

Issued 2026-08-19 after: (1) live reproduction before fix (queued 0/0 on Schnick Coffee,
executions `83fe6e1b`, `3f47e96a`, `591a8778`); (2) the fix implemented at every layer
(handler contract → dispatcher → advance heal → cancel → active/latest → frontend
phantom/poller/hydration/SSE); (3) live verification after fix on the real Beta API
(repro terminal failed; advance stable; 9 phantom packs healed; active/latest clean;
4/4 post-restart soak; project-isolation probe); (4) 10x soak 10/10; (5) Playwright 4/4
on the real /co-director route (retained report); (6) request stability measured
(0 advance calls in phantom states; 9 over 25s for a real job = bounded 3s cadence);
(7) backend 9 new + 80 regression tests, frontend 13 AgentWorkSurface tests + full
CoDirector suite green; (8) four independent reviewers (A state machine, B backend
lifecycle, C Playwright evidence, D request stability) — all PASS; (9) final 15-field
scorecard (see §6) — 15/15 PASS, no mandatory blockers.

ZERO JOBS = NOT RUNNING is now enforced at every layer: a zero-job execution is terminal
before any start event, polling never runs with zero jobs, reload can never rehydrate a
phantom, cancel immediately terminates zero-job packs, and retry starts a fresh
transaction. No valid or error path leaves Scene Generation at 0/0 with an active
spinner indefinitely.
