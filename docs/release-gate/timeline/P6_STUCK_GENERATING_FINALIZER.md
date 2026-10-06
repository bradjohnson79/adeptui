# P6 stuck Generating finalizer (separate from audio mute)

**When:** 2026-09-18 18:42 PT  
**Lane:** Gen / Timeline completion reconcile  
**Severity:** Blocks regenerate until heal; not the speech root cause.

## Symptom

Job can reach Comfy/done while Timeline batch stays **Generating** with generationJobs[].status=running and **no new candidate**. UI Generate then no-ops (jobs: []) because atch.status == "Generating" → BATCH_ALREADY_IN_FLIGHT.

Seen after API bounce mid-finalize (example family: job 86909b79… / job_c31ef0c76379 class during P6 reburns).

## Workaround used (manual heal)

1. Cancel/interrupt Comfy prompt if still running.
2. PUT master heal: job → cancelled, batch status → Approved (or prior terminal).
3. Then regenerate.

## Likely root (hypothesis — not proven live)

Watcher/reconcile path after API process restart drops in-flight finalize handoff: job row updates to done but batch generationJobs / candidate attach never completes. Bounce amplifies.

## Ask

Chief: track as separate Gen/runtime defect. Not blocking audio-mute CODE_READY, but Systems bounce during prove should avoid killing mid-finalize; if it recurs, capture master+job+Comfy prompt ids before heal.
