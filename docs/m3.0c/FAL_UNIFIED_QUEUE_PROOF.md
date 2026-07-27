# M3.0c Phase 4 — fal Unified Studio Queue Proof

**Status: SUCCESS (reconciled after worker interrupt)**

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Budget | ≤ ~$15; one intentional Seedance T2V submit |
| Script | `scripts/m30c_fal_unified_queue_proof.py` |
| Evidence | `artifacts/m30c-fal/unified_queue_proof.json` |
| API | `http://127.0.0.1:8765` (isolated data dir) |

## Workflow proven

```text
POST /api/projects/{id}/txt2vid (fal_seedance, 4s, 854×480)
→ Studio Job row created (status queued)
→ Worker submitted fal Seedance T2V
→ falRequestId stored in history_json
→ API process died mid-poll (harness lifecycle)
→ recover_interrupted marked job failed/interrupted honestly
→ Provider lookup by request_id found COMPLETED
→ MP4 downloaded (852,802 bytes) and Asset linked
→ Job status done + Co-Director inspect source=studio
```

## Identifiers (non-secret)

| Item | Value |
|------|-------|
| Project id | `fb3398dd-df7e-455b-ab0d-400e5390eb33` |
| Studio job id | `5875e029-9693-4ca9-8bb1-f0d0169f37a2` |
| fal request id | `019fa4f6-7a76-72c1-bfe3-ed8cb5200707` |
| Model | `bytedance/seedance-2.0/text-to-video` |
| Output bytes | 852802 |
| Co-Director inspect | HTTP 200, `source=studio`, unified `status=completed`, `provider_request_id` present |

## Guards honoured

- Job row existed before/at provider submit (txt2vid creates Job then enqueues).
- No automatic retry loop in the proof script.
- After interrupt, **no intentional second paid submit**; completed via provider request lookup.
- Recovery message stated the work was interrupted by restart rather than inventing success.

## Notes

1. An exploratory status-URL probe accidentally POSTed to a wrong path and returned a different `request_id` (`019fa507-…`). Cancel attempt returned HTTP 400. This was not an Adept product retry loop; document as probe error. Prefer GET on `https://queue.fal.run/bytedance/seedance-2.0/requests/{id}/status` for Seedance lookup.
2. Keep the API process alive for the full poll window in future live runs (do not attach proof to a short-lived Start-Process shell).
