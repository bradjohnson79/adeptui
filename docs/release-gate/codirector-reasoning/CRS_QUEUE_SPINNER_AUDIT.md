# Co-Director CRS Queue / Spinner Production Loop — Audit & Repair

## Root Cause Analysis

### PRIMARY ROOT CAUSE: Premature "GENERATING" state transition

The pack status transitions from the initial state to `GENERATING` (visual_sheet.py:3101) at job creation time — BEFORE the queue worker has accepted and started processing the job. The job is created with `status="queued"` (execute.py:206), but the pack immediately reports `GENERATING`.

This means the Co-Director card shows "Generating" while the actual job row is still "queued" and may never be consumed by the queue worker.

### CONTRIBUTING FACTOR 1: Queue worker may not consume jobs

The `schedule_job_queue_enqueue` function (imagegen_adapter.py:55) attempts to enqueue onto the `job_queue` asyncio queue. If the queue worker's `_loop` task is dead or its event loop is not running, the enqueue silently fails (the `try/except` at line 98 catches and logs, but the CRS creation path doesn't check the result).

### CONTRIBUTING FACTOR 2: No queue consumer watchdog

There is no bounded timeout between "job queued" and "job dispatched". If the queue worker is dead, the job stays "queued" forever, and the pack stays "GENERATING" forever.

### CONTRIBUTING FACTOR 3: CD action status is independent of job status

The Co-Director's action state (shown in the CD card) is set by the `production_intent/execute.py` flow, which transitions to `execution_state="queued"` (line 223) at job creation. The `advance_visual_sheet_pack` then polls the Job row, but the CD card uses a separate polling mechanism that may not be synchronized.

### SYMPTOM:
- CD card: "Character Reference Sheet — Generating"
- CC surface: "Queuing 1 Shot... / Queued" with spinner
- Job row: "queued" (never transitions to "running")
- Pack status: "GENERATING" (never transitions to "READY_FOR_OWNER")

---

## State Machine Diagram

```
Correct flow:
CD request → job created (queued) → pack QUEUED/STARTING → 
  worker claims → job running → pack GENERATING →
  provider completes → job done → pack READY_FOR_OWNER →
  CD card: Ready

Current broken flow:
CD request → job created (queued) → pack GENERATING (TOO EARLY) →
  [worker never claims] → job stays queued forever →
  pack stays GENERATING forever →
  CD card: Generating (FALSE)
  CC surface: spinner (FOREVER)
```

---

## Required Fixes

### Fix 1: Pack status should not transition to GENERATING until job is actually running

The pack status should be:
- `QUEUED` / `REQUESTED` immediately after job creation
- `GENERATING` only after the job row transitions to "running" or the provider accepts

### Fix 2: Add queue consumer watchdog

If the job stays "queued" for more than a bounded timeout (e.g., 30 seconds), the pack should transition to `FAILED` with a clear reason (e.g., "Generation service unavailable — queue not processing jobs").

### Fix 3: Ensure CD card status comes from authoritative job state

The CD card should read the Job row status (or the pack status, which should reflect the Job row), not an independent action_state.

### Fix 4: Verify queue worker is alive at enqueue time

`schedule_job_queue_enqueue` should verify the worker loop is alive and the enqueue succeeded. If it fails, the CRS job should be marked failed immediately with an honest error.

---

## Implementation

### visual_sheet.py changes

1. Change the initial pack status from `GENERATING` to `QUEUED` (or keep the initial/started state)
2. In `advance_visual_sheet_pack`, when polling the job:
   - If job status is "queued" and the job was created more than 30 seconds ago: mark pack FAILED with "Queue timeout"
   - If job status is "running": transition pack to GENERATING
   - If job status is "done": transition pack to READY_FOR_OWNER
   - If job status is "failed": transition pack to FAILED

### Queue worker monitoring

The `schedule_job_queue_enqueue` function should check if the worker loop is running before attempting to enqueue. If the worker is dead, the function should return an error that the caller can use to mark the job failed immediately.

---

## Files Changed

- `studio-api/app/character_identity/visual_sheet.py` — Fix pack status transitions
- `studio-api/app/codirector/executive/imagegen_adapter.py` — Add enqueue failure reporting
- `studio-api/app/codirector/production_intent/execute.py` — Handle enqueue failures

## Tests Required

- Pack status starts at QUEUED, not GENERATING
- Pack transitions to GENERATING only when job is running
- Pack transitions to FAILED when job stays queued too long
- Queue worker dead → job fails immediately
- CD card status matches pack/job status
