# M3.0d fal Motion Proof

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Status | **SUCCESS (reconciled — reused from M3.0c)** |
| New paid fal spend in M3.0d | **None** |
| Primary evidence | `docs/m3.0c/FAL_UNIFIED_QUEUE_PROOF.md` |
| Machine evidence | `artifacts/m30c-fal/unified_queue_proof.json` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Certification statement

Production motion for Manual User Beta is the **fal Seedance queue path** through the Studio Job system. LTX and WAN native Comfy video routes are **NOT_PRODUCTION_READY** (B20). This document certifies the fal path only, by reference to the M3.0c live proof.

## Workflow proven (M3.0c Phase 4)

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

## M3.0d reuse in production situations

All twelve production situations (S01–S12) attach the reconciled Seedance MP4 as motion media. Stills are fresh local Z-Image ComfyUI outputs per situation. Audio is imported PCM WAV — generative audio is honestly unavailable.

Validation: `artifacts/m30-situations/phase18-final-validation.json` — every pack contains non-empty PNG, WAV, and MP4.

## fal image boundary (UJ-3)

fal image models are not registered (`FAL_IMAGE_MODELS` empty under manifest lock). Stills are **local Z-Image** only. Do not claim fal image generation in production messaging.

## Probe note (documented, not a product retry)

An exploratory status-URL probe accidentally POSTed to a wrong path and returned a different `request_id` (`019fa507-…`). Cancel attempt returned HTTP 400. This was not an Adept product retry loop. Prefer GET on `https://queue.fal.run/bytedance/seedance-2.0/requests/{id}/status` for Seedance lookup.

## Operational guidance

Keep the API process alive for the full poll window in future live runs. M3.0d intentionally avoids new fal spend; re-run `scripts/m30c_fal_unified_queue_proof.py` only when budget and keys are explicitly authorized.
