# 11 — Live generation (Gate K)

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-30  
**Project:** SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e`  
**Scene:** `f0b97b96-3456-4ceb-96ce-56bbece7e5b7`  
No new project created.

## LTX 2.3 Comfy I2V — LIVE VERIFIED

| Field | Value |
|---|---|
| Batch | `bb_c1eb5212d68b` Platform Integrity LTX I2V |
| Generator | `ltx-local` |
| Runtime model | `ltx-2.3-22b-distilled-fp8.safetensors` (from asset `prompt_meta_json`) |
| Workflow | `ltx.simple_i2v` |
| Comfy prompt | `9b9a1808-8231-4588-81fc-e7dec406892f` |
| Candidate then approve | Generate → CandidateReady → Approve (body required `candidateId`) |
| After approve | status **Approved**, `approvedClip.assetId` `ffd1e38a-ccad-4d5b-9688-c5b485cb652d` |
| Library tag | `batch_bb_c1eb5-draft` |
| File | `data/projects/0ffe56e2-…/renders/scene_0_98400655.mp4` |
| Scoped file | **200** `video/mp4` 688043 bytes |
| Unscoped `/api/assets/{id}/file` | **403** |
| **ffprobe** | 1280×704, 24 fps, **113 frames**, duration **4.708333s** |

Take-state draft claimed `512x288` historically; measured media is 1280×704 (LTX height snap). Do not certify 512×288.

First walk script wrote `10_E2E.json` with `poll.status=Failed` and `ok:true`. That flag is a lie. Authoritative result is this Approved batch + ffprobe.

## MiniMax Route A — NOT 15s

Live join: `minimax-h3` / `minimax-h3-i2v-local` executable=True, readiness=Testing, **maxDurationSec=0.2083…** (5/24).

A 5.0s planned duration-check is refused (`DURATION_EXCEEDS_GENERATOR`). No 15s claim. No new MiniMax generate this closure (would be ~0.21s media, not owner-useful). No frame-loop / stretch / metadata lie.

## Hosted generators

Not spent. Out of scope unless already configured and cheap.
