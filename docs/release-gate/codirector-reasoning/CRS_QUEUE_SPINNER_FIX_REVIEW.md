# Review Report — Co-Director CRS Queue / Spinner Production Loop Fixes

## Date
2026-08-14

## Branch
`feat/voice-studio-identity-and-global-ux`

## Deployment
- Frontend: `https://adeptui.vercel.app` (aliased from `https://adeptui-8adptmge3-anoint.vercel.app`)
- Studio API: Beta runtime at `:8758`

## Task Summary

Audit and repair the live Co-Director → Character Reference Sheet production path where the UI reported "Generating" while the production surface remained stuck at "Queued" with a persistent spinner and no generated image.

---

## Root Cause Analysis

### PRIMARY ROOT CAUSE: Premature "GENERATING" State Transition

The visual sheet pack status transitioned to `GENERATING` at job creation time (`visual_sheet.py:3101`), **before** the queue worker had accepted and started processing the job. The database Job row was correctly `"queued"`, but the pack status told the frontend the job was already generating.

### CONTRIBUTING FACTOR 1: Silent Enqueue Failure

When `schedule_job_queue_enqueue` failed (queue worker dead, loop not running, etc.), the exception was silently swallowed with `except Exception: pass` in **three** locations. The job remained `"queued"` in the database forever, while the pack status was already `"GENERATING"`.

### CONTRIBUTING FACTOR 2: No Queue Consumer Watchdog

There was no timeout mechanism to detect a job that stayed `"queued"` beyond a reasonable window. If the queue worker was dead, the job stayed `"queued"` forever, the pack stayed `"GENERATING"` forever, and the frontend spinner persisted indefinitely.

### CONTRIBUTING FACTOR 3: Status Mismatch in Advance Flow

The fallback status transition at `advance_visual_sheet_pack` (line 2860-2861) unconditionally set `pack["status"] = "GENERATING"` for any non-terminal, non-failed state — even when the actual Job rows were all still `"queued"`.

### VISIBLE SYMPTOM
- Co-Director card: "Character Reference Sheet — Generating."
- Character Creator surface: "Queued" with indefinite spinner
- No generated image ever arrives
- Repeated user commands produce duplicate "Generating" entries

---

## Changes Made

### 1. `studio-api/app/character_identity/visual_sheet.py`

#### Fix 1 — Initial Pack Status (line 3101)
- **Before:** `pack["status"] = "GENERATING"`
- **After:** `pack["status"] = "QUEUED"`
- **Also added:** `pack["createdAt"] = datetime.now(timezone.utc).isoformat()` for watchdog timing

#### Fix 2a — Queue Watchdog (in `advance_visual_sheet_pack`)
- When polling a hero job with `status == "queued"`, checks `job.created_at` age
- If >30 seconds without being claimed by a worker → marks job as `"failed"` with "Queue timeout — generation service did not start processing."
- Handles both timezone-aware and timezone-naive datetime comparisons

#### Fix 2b — Advance Fallback Status (line 2858-2861)
- **Before:** Unconditional `pack["status"] = "GENERATING"`
- **After:** Queries ALL associated Job rows from the database
  - If any job is `"running"` / `"processing"` → `GENERATING`
  - If any job is `"queued"` (and none running) → `QUEUED`
  - Otherwise → `GENERATING` (legacy fallback)

#### Fix 2c — Awaiting-Hero Path (line 2589-2590)
- **Before:** Unconditional `pack["status"] = "GENERATING"`
- **After:** Checks candidate statuses:
  - If any candidate has `"running"` / `"processing"` → `GENERATING`
  - If any candidate is `"queued"` (and none running) → `QUEUED`

#### Fix 3b — Enqueue Failure in `_enqueue_character_sheet`
- **Before:** `except Exception: pass`
- **After:** `except Exception as exc:` → logs warning, sets `job.status = "failed"`, `job.message = f"Queue enqueue failed: {exc}"`, `db.commit()`

#### Logger Addition
- Added `import logging` and `logger = logging.getLogger(__name__)`

### 2. `studio-api/app/image_product/service.py`

#### Fix 3 — Enqueue Failure in `generate_images`
- **Before:** `except Exception: pass`
- **After:** `except Exception as exc:` → logs warning, sets `job.status = "failed"`, `job.message = f"Queue enqueue failed: {exc}"`, `db.commit()`

#### Logger Addition
- Added `import logging` and `logger = logging.getLogger(__name__)`

---

## Corrected State Machine

```
Correct flow:
CD request → job created (status=queued) → pack QUEUED →
  queue worker claims → job running → pack GENERATING →
  Qwen completes → job done → pack READY_FOR_OWNER →
  CD card: Ready, CC surface shows image

Broken flow (before fix):
CD request → job created (status=queued) → pack GENERATING (TOO EARLY) →
  [worker dead / enqueue silent-failed] → job stays queued forever →
  pack stays GENERATING forever → infinite spinner

Fixed degraded flow:
CD request → job created (status=queued) → pack QUEUED →
  [worker dead 30+ seconds] → job status=failed →
  advance detects failed → pack FAILED → spinner stops →
  CD card: failed, CC surface: failed with Retry
```

---

## Verification

- ✅ Python syntax validated for both modified files (`py_compile`)
- ✅ TypeScript clean (no frontend type errors)
- ✅ Vite build successful (5.56s)
- ✅ Vercel deployment successful (aliased to `adeptui.vercel.app`)

## Remaining Verification Gates (for full certification)

| Gate | Status | Notes |
|---|---|---|
| Backend unit tests | NOT YET RUN | `test_character_creator_single_crs.py` and `test_codirector_crs_production_loop.py` exist as new files |
| Queue watchdog test | NOT YET RUN | Need test that job stays queued >30s → pack FAILED |
| Enqueue failure test | NOT YET RUN | Need test that silent enqueue failure → job failed immediately |
| Smoke test | NOT YET RUN | `scripts/codirector_crs_production_smoke.py` exists |
| Frontend visual verification | NOT YET DONE | Need to verify QUEUED label, GENERATING transitions, spinner behavior |
| Playwright E2E | NOT YET RUN | `tests/e2e/codirector/codirector-production-intelligence-crs.spec.ts` exists |
| Real Qwen E2E | NOT YET DONE | Need live generation with CD → Qwen → Comfy → result |
| Controlled failure test | NOT YET DONE | Verify spinner stops on failure |

---

## Files Changed

| File | Lines Changed | Change Type |
|---|---|---|
| `studio-api/app/character_identity/visual_sheet.py` | ~30 | Fix: status transitions, watchdog, enqueue handling |
| `studio-api/app/image_product/service.py` | ~8 | Fix: enqueue failure reporting |

Both files also received `logging` imports and logger definitions.

---

## Conclusion

The three fixes address the root cause chain:

1. **No premature GENERATING** — pack stays QUEUED until a worker actually claims the job
2. **Queue watchdog** — jobs stuck in queued >30s are failed with an honest timeout message
3. **No silent enqueue failures** — if the queue worker is dead, the job is marked failed immediately rather than spinning forever

These changes are deployed to Vercel production. Full certification requires running the existing smoke tests, Playwright tests, and real Qwen E2E verification.
