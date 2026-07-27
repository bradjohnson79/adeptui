# M3.0d Failure and Recovery Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Register items | B14, PW-S3, B12 (cancel) |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Executive summary

| Scenario | Status | Evidence |
|----------|--------|----------|
| Studio job restart recovery | **Closed** | e2e seed/recover + pytest recovery tests |
| Playwright restart journey (PW-S3) | **Closed** | `production-executive-m27.spec.ts` |
| Executive cancel determinism (B12) | **Closed** | executive tests + PW idempotency |
| fal interrupt reconcile | **Closed** | M3.0c fal proof (no re-submit) |
| Full fault-injection matrix | **Partial** | Not every timeout/retry variant live-captured |

## B14 / PW-S3 — Real Playwright restart recovery (Closed)

### Problem

M3.0b carried a hard `test.skip(true, "restart recovery documented in pytest")` stub — no browser assertion.

### Fix

E2E control endpoints (STUDIO_E2E=1):

- `POST /api/e2e/seed-running-job` — inserts running Studio Job
- `POST /api/e2e/recover-jobs` — runs `job_queue.recover_interrupted()`

Implementation: `studio-api/app/routers/e2e.py`

### Playwright test

`tests/e2e/codirector/production-executive-m27.spec.ts`:

```typescript
test("restart recovery closes running Studio jobs as interrupted", async ({ request }) => {
  const seed = await request.post("/api/e2e/seed-running-job", { data: { kind: "render_scene" } });
  const recovered = await request.post("/api/e2e/recover-jobs");
  expect(body.recovered?.interrupted || []).toContain(seeded.job_id);
  expect(job.status).toBe("failed");
  expect(String(job.message || "").toLowerCase()).toMatch(/interrupt|restart|recover/);
});
```

PW-S3 is **Closed**. The skip stub is replaced by a real assertion.

## Backend recovery paths

| Path | Behavior |
|------|----------|
| `JobQueue.recover_interrupted` | Marks running jobs interrupted/failed; no silent paid re-submit |
| Executive `recover_running_jobs` | Executive store recovery |
| API lifespan | Recovers stale setup operations on startup |
| fal proof interrupt | Honest failure then provider lookup reconcile |

Pytest: `studio-api/tests/test_job_queue_recovery.py` (delegated coverage referenced from M3.0c Playwright report).

## B12 — Cancel race (Closed)

Executive cancel and closed-loop idempotency specs pass in the captured Playwright run (111 passed). Cancel returns deterministic terminal status.

## M3.0c fal recovery (reused)

Worker/API interrupt during fal poll → `recover_interrupted` marks job honestly → completed via `falRequestId` lookup without second paid submit. Documented in `M30D_FAL_MOTION_PROOF.md`.

## Residual (honest)

Not every Phase 13–14 fault-injection scenario (provider timeout exhaustion, worker SIGKILL mid-render, retry budget depletion) was re-captured in M3.0d with fresh artifacts. The **restart/interrupt contract** is proven; exhaustive chaos testing is out of scope for this gate pass.

## Status

| ID | Status |
|----|--------|
| B14 | **Closed** |
| PW-S3 | **Closed** |
| B12 | **Closed** |
